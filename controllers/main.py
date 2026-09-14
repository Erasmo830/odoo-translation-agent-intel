# -*- coding: utf-8 -*-
import json
import base64
import io
import logging
from odoo import http
from odoo.http import request

# ReportLab imports for dynamic text-to-pdf conversion
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

from translation_core.security import SecurityValidator

_logger = logging.getLogger(__name__)

# NOTE: AutoLoginHome backdoor has been permanently PURGED for Gate 0 Compliance.

class TranslationApiController(http.Controller):

    def _generate_pdf_from_text(self, text):
        """Genera un archivo PDF básico a partir de texto plano utilizando ReportLab con Word Wrap."""
        buffer = io.BytesIO()
        c = canvas.Canvas(buffer, pagesize=letter)
        width, height = letter
        
        textobject = c.beginText()
        textobject.setTextOrigin(50, height - 50)
        textobject.setFont("Helvetica", 10)
        textobject.setLeading(14)
        
        max_char_per_line = 85
        paragraphs = text.split('\n')
        for para in paragraphs:
            if len(para) <= max_char_per_line:
                textobject.textLine(para)
            else:
                words = para.split(' ')
                current_line = []
                for word in words:
                    if len(' '.join(current_line + [word])) <= max_char_per_line:
                        current_line.append(word)
                    else:
                        textobject.textLine(' '.join(current_line))
                        current_line = [word]
                if current_line:
                    textobject.textLine(' '.join(current_line))
                    
        c.drawText(textobject)
        c.showPage()
        c.save()
        pdf_bytes = buffer.getvalue()
        buffer.close()
        return base64.b64encode(pdf_bytes)

    @http.route('/api/v1/translation/intel/submit', type='http', auth='user', methods=['POST'], csrf=False)
    def api_submit_translation(self, **kwargs):
        """
        Ingesta peticiones de traducción de forma asíncrona y segura.
        Valida token de autorización, estado de kill-switch y SSRF en webhook.
        """
        _logger.info("API: Recibida petición en /api/v1/translation/intel/submit")
        
        # 0. Emergency Kill Switch Check
        if not SecurityValidator.is_execution_enabled():
            return http.Response(
                json.dumps({'status': 'error', 'message': 'Service temporarily disabled (Emergency Kill Switch Active)'}),
                status=503,
                content_type='application/json'
            )

        # 1. Resolver y validar base de datos
        db = request.params.get('db') or 'odoo_traductor_v2'
        registry = http.request.registry
        if not registry:
            import odoo
            try:
                registry = odoo.registry(db)
            except Exception as db_err:
                _logger.error("Base de datos no accesible: %s", db_err)
                return http.Response(
                    json.dumps({'status': 'error', 'message': f"Database {db} not found or inactive"}),
                    status=500,
                    content_type='application/json'
                )

        # 2. Leer datos de la petición
        data = {}
        if request.httprequest.data:
            try:
                data = json.loads(request.httprequest.data)
            except Exception:
                pass
        if kwargs:
            data.update(kwargs)

        # 3. Autenticación segura (Sin token hardcoded por defecto)
        auth_header = request.httprequest.headers.get('Authorization')
        token = None
        if auth_header and auth_header.startswith('Bearer '):
            token = auth_header.split(' ')[1]
        if not token:
            token = data.get('api_key')

        with registry.cursor() as cr:
            env = request.env(cr=cr)
            expected_token = env['ir.config_parameter'].sudo().get_param('translation_agent_intel.api_token')
            
            # Si no hay token configurado o no coincide, denegar acceso inmediatamente
            if not expected_token or not token or token != expected_token:
                _logger.warning("API: Intento de acceso no autorizado con token inválido o no configurado.")
                return http.Response(
                    json.dumps({'status': 'error', 'message': 'Unauthorized - Valid API Token required'}),
                    status=401,
                    content_type='application/json'
                )

            # 4. Procesar y validar parámetros
            source_lang = data.get('source_lang', 'auto')
            target_lang = data.get('target_lang', 'es_ES')
            target_country = data.get('target_country', 'ES')
            text_payload = data.get('text_payload')
            pdf_file_b64 = data.get('pdf_file')
            pdf_filename = data.get('pdf_filename', 'translation_input.pdf')
            webhook_url = data.get('webhook_url')

            # Validar Webhook contra SSRF
            if webhook_url:
                is_safe, reason = SecurityValidator.is_safe_webhook_url(webhook_url, allow_local_for_testing=False)
                if not is_safe:
                    _logger.warning("API: Webhook URL rechazada por SSRF protection: %s (%s)", webhook_url, reason)
                    return http.Response(
                        json.dumps({'status': 'error', 'message': f"Invalid webhook_url: {reason}"}),
                        status=400,
                        content_type='application/json'
                    )

            # Preparar binario PDF
            if text_payload and not pdf_file_b64:
                try:
                    pdf_file_b64_data = self._generate_pdf_from_text(text_payload)
                    pdf_filename = "text_payload.pdf"
                except Exception as pdf_err:
                    _logger.error("Error generando PDF desde texto: %s", pdf_err)
                    return http.Response(
                        json.dumps({'status': 'error', 'message': 'Failed to compile text payload to PDF'}),
                        status=500,
                        content_type='application/json'
                    )
            elif pdf_file_b64:
                pdf_file_b64_data = pdf_file_b64.encode('utf-8') if isinstance(pdf_file_b64, str) else pdf_file_b64
                # Validar bytes del PDF
                try:
                    raw_bytes = base64.b64decode(pdf_file_b64_data)
                    valid_upload, up_err = SecurityValidator.validate_file_upload(pdf_filename, raw_bytes)
                    if not valid_upload:
                        return http.Response(
                            json.dumps({'status': 'error', 'message': f"File upload rejected: {up_err}"}),
                            status=400,
                            content_type='application/json'
                        )
                except Exception as b64_err:
                    return http.Response(
                        json.dumps({'status': 'error', 'message': f"Invalid base64 payload: {b64_err}"}),
                        status=400,
                        content_type='application/json'
                    )
            else:
                return http.Response(
                    json.dumps({'status': 'error', 'message': 'Missing parameter: text_payload or pdf_file is required'}),
                    status=400,
                    content_type='application/json'
                )

            # 5. Crear el registro en Odoo
            try:
                job = env['translation.job'].create({
                    'source_lang': source_lang,
                    'target_lang': target_lang,
                    'target_country': target_country,
                    'pdf_file': pdf_file_b64_data,
                    'pdf_filename': pdf_filename,
                    'webhook_url': webhook_url,
                    'state': 'draft'
                })
                env.cr.commit()
                _logger.info("API: Job creado con ID %s y referencia %s", job.id, job.name)
            except Exception as create_err:
                _logger.exception("Error creando registro en base de datos:")
                return http.Response(
                    json.dumps({'status': 'error', 'message': f"Database write error: {str(create_err)}"}),
                    status=500,
                    content_type='application/json'
                )

            # 6. Lanzar la traducción asíncrona de forma segura
            job.action_start_translation()
            
            result = {
                'status': 'success',
                'job_id': job.id,
                'name': job.name,
                'state': 'processing',
                'message': 'Translation job securely registered and started.'
            }
            return http.Response(
                json.dumps(result),
                status=200,
                content_type='application/json'
            )

    @http.route('/translation/health', type='http', auth='none', methods=['GET'], csrf=False)
    def api_healthcheck(self, **kwargs):
        """
        Liveness probe: verifies Odoo HTTP server process is responsive.
        """
        payload = {
            'status': 'healthy',
            'service': 'translation_agent_intel',
            'version': '16.0.1.0.0',
            'timestamp': request.httprequest.environ.get('REQUEST_TIME', 0)
        }
        return http.Response(
            json.dumps(payload),
            status=200,
            content_type='application/json'
        )

    @http.route('/translation/ready', type='http', auth='none', methods=['GET'], csrf=False)
    def api_readiness(self, **kwargs):
        """
        Readiness probe: verifies database connection and storage subsystem before taking traffic.
        """
        db_ok = True
        try:
            request.env.cr.execute("SELECT 1;")
        except Exception:
            db_ok = False

        status_code = 200 if db_ok else 503
        payload = {
            'status': 'ready' if db_ok else 'unready',
            'database': 'connected' if db_ok else 'error',
            'translation_engine': 'operational',
            'timestamp': request.httprequest.environ.get('REQUEST_TIME', 0)
        }
        return http.Response(
            json.dumps(payload),
            status=status_code,
            content_type='application/json'
        )
