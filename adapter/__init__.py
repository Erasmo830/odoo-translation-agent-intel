# -*- coding: utf-8 -*-
"""
AURA TRANSLATOR — ODOO ADAPTER PACKAGE
Integration layer enabling Odoo to consume AURA Translation Core.
One-way dependency: Odoo Adapter -> AURA Translation Core.
"""

from translation_agent_intel.adapter.translator_adapter import (
    OdooTranslationAdapter,
    OdooLanguageMapper,
    get_odoo_adapter
)

__all__ = [
    "OdooTranslationAdapter",
    "OdooLanguageMapper",
    "get_odoo_adapter"
]
