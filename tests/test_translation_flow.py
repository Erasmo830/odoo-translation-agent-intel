# -*- coding: utf-8 -*-
import base64
from odoo.tests.common import TransactionCase
from odoo.exceptions import UserError

class TestTranslationFlow(TransactionCase):

    def setUp(self):
        super(TestTranslationFlow, self).setUp()
        self.TranslationJobObj = self.env['translation.job']
        self.TranslationLineObj = self.env['translation.job.line']
        
        # Base64 encoded empty PDF structure for unit tests
        self.dummy_pdf_base64 = base64.b64encode(b"%PDF-1.4 ... dummy content")
        
    def test_01_job_creation_and_sequence(self):
        """Test 1: Verify sequence code name generation on creation."""
        job = self.TranslationJobObj.create({
            'pdf_file': self.dummy_pdf_base64,
            'pdf_filename': 'test.pdf'
        })
        self.assertTrue(job.name, "Job name should be generated.")
        self.assertNotEqual(job.name, 'Nuevo', "Job name should not be 'Nuevo'")
        self.assertTrue(job.name.startswith("TR-"), "Job name should start with prefix 'TR-'")
        
        # Check prefix and sequence split formatting: TR-YYYY-NNNN
        name_parts = job.name.split("-")
        self.assertEqual(len(name_parts), 3, "Name format should split in 3 parts: TR-YYYY-NNNN")
        self.assertEqual(job.state, 'draft', "Initial job state should be 'draft'")
        
    def test_02_job_start_translation(self):
        """Test 2: Verify start translation starts pipeline and changes state to processing."""
        job = self.TranslationJobObj.create({
            'pdf_file': self.dummy_pdf_base64,
            'pdf_filename': 'test.pdf'
        })
        
        # Temporarily mock the background thread process to prevent actual thread launch during test
        orig_background = self.TranslationJobObj.__class__._process_translation_background
        self.TranslationJobObj.__class__._process_translation_background = lambda *args, **kwargs: None
        
        try:
            job.action_start_translation()
            self.assertEqual(job.state, 'processing', "State should switch to 'processing' after starting")
        finally:
            # Restore original method
            self.TranslationJobObj.__class__._process_translation_background = orig_background

    def test_03_reviewer_conflict_interruption_and_wizard(self):
        """Test 3: Simulate Reviewer Agent alert interruption, wizard input, and resume flow."""
        job = self.TranslationJobObj.create({
            'pdf_file': self.dummy_pdf_base64,
            'pdf_filename': 'test.pdf'
        })
        
        # 1. Simulate Reviewer Agent finding a translation conflict and pausing
        job.write({
            'state': 'alert',
            'conflict_text_original': "This is a critical milestone that requires synergy.",
            'conflict_suggested_options': '["Este es un hito crítico que requiere sinergia.", "Este logro requiere apalancamiento.", "Se requiere sinergía y creatividad."]',
            'current_page_num': 0,
            'current_block_num': 2,
            'current_block_alignment': 'left',
            'current_block_is_heading': False
        })
        
        self.assertEqual(job.state, 'alert', "Job state should be 'alert' when paused by Supervisor.")
        self.assertEqual(job.conflict_text_original, "This is a critical milestone that requires synergy.")
        
        # 2. Simulate User opening the Wizard and resolving the conflict
        # active_id in context mimics Odoo web user clicking "Resolver Conflicto Narrativo"
        wizard_context = {'active_id': job.id}
        wizard = self.env['translation.alert.wizard'].with_context(wizard_context).create({
            'selected_option': 'Este es un hito crítico que requiere sinergia.',
        })
        
        # Validate selection options list load
        options = wizard._get_options()
        self.assertEqual(len(options), 3, "Wizard should load 3 suggested options dynamically.")
        
        # Mock background thread start for the Wizard resume step
        orig_background = self.TranslationJobObj.__class__._process_translation_background
        self.TranslationJobObj.__class__._process_translation_background = lambda *args, **kwargs: None
        
        try:
            action = wizard.action_apply_and_resume()
            # Verify close modal action is returned
            self.assertEqual(action.get('type'), 'ir.actions.act_window_close', "Action should close wizard modal.")
            
            # Verify parent job state reverted back to processing and conflicts cleared
            self.assertEqual(job.state, 'processing', "Job should return to 'processing' state.")
            self.assertFalse(job.conflict_text_original, "Conflict text should be cleared.")
            self.assertFalse(job.conflict_suggested_options, "Conflict options should be cleared.")
            
            # Verify Odoo DB persistent line is created with the chosen option
            lines = self.TranslationLineObj.search([('job_id', '=', job.id)])
            self.assertEqual(len(lines), 1, "A segment line should be created in the database.")
            self.assertEqual(lines.page_number, 0, "Line page_number should be 0")
            self.assertEqual(lines.sequence, 2, "Line sequence block should be 2")
            self.assertEqual(lines.text_translated, 'Este es un hito crítico que requiere sinergia.', "Translated text must match chosen suggestion.")
            self.assertEqual(lines.state, 'translated', "Line status should be 'translated'")
        finally:
            # Restore original method
            self.TranslationJobObj.__class__._process_translation_background = orig_background
