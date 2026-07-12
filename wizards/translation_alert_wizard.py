# -*- coding: utf-8 -*-
import json
from odoo import models, fields, api, _
from odoo.exceptions import UserError

class TranslationAlertWizard(models.TransientModel):
    _name = 'translation.alert.wizard'
    _description = 'Ventana Modal de Ajuste de Traducción'

    job_id = fields.Many2one(
        'translation.job', 
        string='Trabajo Relacionado', 
        required=True
    )
    
    text_original = fields.Text(string='Texto Original (Inglés)', readonly=True)
    
    # Dynamic Selection field to load options from the parent job
    selected_option = fields.Selection(
        selection='_get_options', 
        string='Opciones de Traducción Sugeridas'
    )
    
    custom_text = fields.Text(string='Redactar Traducción Manual alternativa')

    @api.model
    def default_get(self, fields_list):
        res = super(TranslationAlertWizard, self).default_get(fields_list)
        active_id = self.env.context.get('active_id')
        if active_id:
            job = self.env['translation.job'].browse(active_id)
            res.update({
                'job_id': job.id,
                'text_original': job.conflict_text_original,
            })
        return res

    def _get_options(self):
        """Parse dynamic suggestions from the parent job's JSON string in context."""
        active_id = self.env.context.get('active_id') or self.env.context.get('default_job_id')
        if active_id:
            job = self.env['translation.job'].browse(active_id)
            if job.conflict_suggested_options:
                try:
                    options = json.loads(job.conflict_suggested_options)
                    return [(opt, opt) for opt in options]
                except Exception:
                    pass
        return [('none', 'No hay opciones sugeridas disponibles')]

    def action_apply_and_resume(self):
        """Saves selected or custom translation text, resets state, and resumes background thread."""
        self.ensure_one()
        
        # Decide between custom text or selection
        final_translation = self.custom_text.strip() if self.custom_text else self.selected_option
        
        if not final_translation or final_translation == 'none':
            raise UserError(_("Debe seleccionar una de las sugerencias o escribir una traducción manual."))
            
        # Write translated line using exact field names
        self.env['translation.job.line'].create({
            'job_id': self.job_id.id,
            'page_number': self.job_id.current_page_num,
            'sequence': self.job_id.current_block_num,
            'text_original': self.job_id.conflict_text_original,
            'text_translated': final_translation,
            'alignment': self.job_id.current_block_alignment,
            'is_heading': self.job_id.current_block_is_heading,
            'state': 'translated'
        })
        
        # Reset parent job fields and change state
        self.job_id.write({
            'state': 'processing',
            'conflict_text_original': False,
            'conflict_suggested_options': False
        })
        
        # Log resolution in chatter
        self.job_id.message_post(
            body=_("Traducción resuelta manualmente por el usuario:<br/><b>%s</b>") % final_translation
        )
        
        # Resume background thread
        self.job_id.action_start_translation()
        
        return {'type': 'ir.actions.act_window_close'}
