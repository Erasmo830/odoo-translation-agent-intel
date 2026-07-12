# -*- coding: utf-8 -*-
{
    'name': 'AI Multi-Agent Translation Engine',
    'version': '16.0.1.0.0',
    'summary': 'Translate scanned PDFs to Word (.docx) using a concurrent multi-agent system with human-in-the-loop validation.',
    'description': """
        Odoo module to translate scanned PDFs into Word files using PyMuPDF, EasyOCR, and LLMs/fallback translation engines.
        The module uses a multi-agent system (Linguistic, Reviewer, and QA agents) to ensure high-quality translations
        and provides a native wizard popup for human resolution when ambiguities or low confidence is detected.
    """,
    'category': 'Productivity/Translation',
    'author': 'Erasmo Ramos / Antigravity',
    'website': 'https://github.com/google-gemini',
    'depends': [
        'base',
        'mail',
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/ir_sequence_data.xml',
        'data/ir_config_parameter_data.xml',
        'views/translation_alert_wizard_views.xml',
        'views/translation_job_views.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
    'license': 'LGPL-3',
}
