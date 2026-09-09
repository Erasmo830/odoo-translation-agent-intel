# -*- coding: utf-8 -*-
"""
AURA TRANSLATOR — ODOO ADAPTER IMPLEMENTATION
Translates Odoo records, dictionaries, and language codes into pure AURA Translation Core requests.
Guarantees clean integration while maintaining one-way dependency (Odoo -> Core).
"""

import logging
from typing import Optional, Dict, Any, List, Union

from translation_core.contracts import (
    TranslationRequest,
    TranslationResponse,
    TranslationBlockResult
)
from translation_core.exceptions import (
    AuraCoreError,
    ProviderUnavailableError,
    ProviderTimeoutError,
    ProviderRateLimitError,
    TenantSecurityError,
    CoreValidationError
)
from translation_core.service import TranslationService

_logger = logging.getLogger("odoo.addons.translation_agent_intel.adapter")


class OdooLanguageMapper:
    """Maps between Odoo language codes and Core ISO language codes."""

    ODOO_TO_CORE_MAP = {
        "auto": "auto",
        "en_US": "en",
        "en_GB": "en",
        "es_ES": "es",
        "es_419": "es",
        "pt": "pt",
        "pt_BR": "pt",
        "fr": "fr",
        "fr_FR": "fr",
        "de": "de",
        "de_DE": "de",
        "it": "it",
        "it_IT": "it",
        "ja": "ja",
        "ja_JP": "ja",
        "zh": "zh",
        "zh_CN": "zh",
        "nl": "nl",
        "nl_NL": "nl",
    }

    CORE_TO_ODOO_MAP = {
        "auto": "auto",
        "en": "en_US",
        "es": "es_ES",
        "pt": "pt",
        "fr": "fr",
        "de": "de",
        "it": "it",
        "ja": "ja",
        "zh": "zh",
        "nl": "nl",
    }

    @classmethod
    def odoo_to_core(cls, odoo_lang: str) -> str:
        """Converts an Odoo language code (e.g. 'en_US', 'es_ES') to ISO format ('en', 'es')."""
        if not odoo_lang:
            return "auto"
        clean = odoo_lang.strip()
        if clean in cls.ODOO_TO_CORE_MAP:
            return cls.ODOO_TO_CORE_MAP[clean]
        # Fallback to prefix before underscore
        base = clean.split("_")[0].lower()
        return base

    @classmethod
    def core_to_odoo(cls, core_lang: str) -> str:
        """Converts an ISO language code ('en', 'es') to default Odoo format ('en_US', 'es_ES')."""
        if not core_lang:
            return "auto"
        clean = core_lang.strip().lower()
        return cls.CORE_TO_ODOO_MAP.get(clean, clean)


class OdooTranslationAdapter:
    """
    Odoo Adapter layer for AURA Translation Core.
    
    Transforms Odoo models/data into TranslationRequest, executes through
    TranslationService, and formats the output into Odoo ORM data structures.
    """

    def __init__(self, service: Optional[TranslationService] = None):
        self._service = service or TranslationService()

    @property
    def service(self) -> TranslationService:
        return self._service

    def translate_text(
        self,
        text: str,
        source_lang: str,
        target_lang: str,
        target_country: str = "ES",
        provider: Optional[str] = None,
        tenant_id: str = "odoo_instance",
        options: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Translates raw text from Odoo context through AURA Core.
        Returns a dictionary compatible with Odoo controllers and models.
        """
        core_src = OdooLanguageMapper.odoo_to_core(source_lang)
        core_tgt = OdooLanguageMapper.odoo_to_core(target_lang)
        
        request = TranslationRequest(
            source_language=core_src,
            target_language=core_tgt,
            text=text,
            target_country=target_country,
            provider=provider or "fallback",
            tenant_id=tenant_id,
            options=options or {}
        )

        try:
            response: TranslationResponse = self._service.translate(request)
            return {
                "success": response.status == "completed",
                "status": response.status,
                "job_id": response.job_id,
                "translated_text": response.translated_text or "",
                "source_language": OdooLanguageMapper.core_to_odoo(response.source_language),
                "target_language": OdooLanguageMapper.core_to_odoo(response.target_language),
                "target_country": response.target_country,
                "provider": response.provider,
                "latency": response.latency,
                "usage": response.usage,
                "error_message": response.error_message
            }
        except AuraCoreError as ce:
            _logger.error("AURA Core error in Odoo Adapter: %s", str(ce))
            return {
                "success": False,
                "status": "error",
                "error_message": ce.message,
                "status_code": ce.status_code,
                "error_code": ce.error_code
            }
        except Exception as ex:
            _logger.exception("Unexpected error in Odoo Translation Adapter: %s", str(ex))
            return {
                "success": False,
                "status": "error",
                "error_message": f"Adapter error: {str(ex)}",
                "status_code": 500,
                "error_code": "ADAPTER_INTERNAL_ERROR"
            }

    def translate_blocks_for_odoo_lines(
        self,
        blocks: List[Dict[str, Any]],
        source_lang: str,
        target_lang: str,
        target_country: str = "ES",
        tenant_id: str = "odoo_instance"
    ) -> List[Dict[str, Any]]:
        """
        Translates structured text blocks and formats them for Odoo 'translation.job.line' creation.
        
        Returns a list of dicts ready to be used with (0, 0, line_vals).
        """
        core_src = OdooLanguageMapper.odoo_to_core(source_lang)
        core_tgt = OdooLanguageMapper.odoo_to_core(target_lang)
        
        results = []
        for block in blocks:
            original = block.get("text", "")
            req = TranslationRequest(
                source_language=core_src,
                target_language=core_tgt,
                text=original,
                target_country=target_country,
                tenant_id=tenant_id
            )
            try:
                resp = self._service.translate(req)
                results.append({
                    "sequence": block.get("seq", block.get("sequence", 0)),
                    "original_text": original,
                    "translated_text": resp.translated_text or "",
                    "confidence": 1.0 if resp.status == "completed" else 0.5,
                    "is_heading": block.get("is_heading", False),
                    "page_number": block.get("page_num", 1)
                })
            except Exception as e:
                _logger.warning("Block translation error in adapter: %s", e)
                results.append({
                    "sequence": block.get("seq", block.get("sequence", 0)),
                    "original_text": original,
                    "translated_text": original,  # Fallback to original text on failure
                    "confidence": 0.0,
                    "is_heading": block.get("is_heading", False),
                    "page_number": block.get("page_num", 1)
                })
        return results


# Global adapter singleton helper
_global_odoo_adapter: Optional[OdooTranslationAdapter] = None


def get_odoo_adapter() -> OdooTranslationAdapter:
    """Returns the singleton instance of OdooTranslationAdapter."""
    global _global_odoo_adapter
    if _global_odoo_adapter is None:
        _global_odoo_adapter = OdooTranslationAdapter()
    return _global_odoo_adapter
