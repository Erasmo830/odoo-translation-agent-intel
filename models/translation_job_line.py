# -*- coding: utf-8 -*-
from odoo import models, fields

class TranslationJobLine(models.Model):
    _name = 'translation.job.line'
    _description = 'Línea de Segmento de Traducción'
    _order = 'page_number, sequence'

    job_id = fields.Many2one(
        'translation.job', 
        string='Trabajo Relacionado', 
        required=True, 
        ondelete='cascade'
    )
    
    page_number = fields.Integer(string='Página', required=True)
    sequence = fields.Integer(string='Secuencia', required=True)
    
    text_original = fields.Text(string='Texto Original (Inglés)', required=True)
    text_translated = fields.Text(string='Texto Traducido (Español)', required=True)
    
    state = fields.Selection([
        ('draft', 'Borrador'),
        ('translated', 'Traducido'),
        ('conflict', 'Conflicto')
    ], string='Estado', default='translated')
    
    alignment = fields.Selection([
        ('left', 'Izquierda'),
        ('center', 'Centro'),
        ('right', 'Derecha')
    ], string='Alineación', default='left')
    
    is_heading = fields.Boolean(string='Es Título/Encabezado', default=False)
