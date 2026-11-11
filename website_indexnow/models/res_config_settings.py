# Copyright (C) 2026 Asad Ali (Softosmith)
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    indexnow_enabled = fields.Boolean(related='website_id.indexnow_enabled', readonly=False)
    indexnow_key = fields.Char(related='website_id.indexnow_key', readonly=False)
    indexnow_auto_submit = fields.Boolean(related='website_id.indexnow_auto_submit', readonly=False)
    indexnow_submit_translations = fields.Boolean(related='website_id.indexnow_submit_translations', readonly=False)
    indexnow_submission_delay = fields.Selection(related='website_id.indexnow_submission_delay', readonly=False)
    indexnow_batch_size = fields.Integer(related='website_id.indexnow_batch_size', readonly=False)
    indexnow_endpoint = fields.Char(related='website_id.indexnow_endpoint', readonly=False)
    indexnow_key_verified = fields.Boolean(related='website_id.indexnow_key_verified', readonly=True)
    indexnow_key_verified_on = fields.Datetime(related='website_id.indexnow_key_verified_on', readonly=True)
    indexnow_last_success_on = fields.Datetime(related='website_id.indexnow_last_success_on', readonly=True)
    indexnow_last_error = fields.Text(related='website_id.indexnow_last_error', readonly=True)
    indexnow_key_url = fields.Char(compute='_compute_indexnow_key_url')

    def _compute_indexnow_key_url(self):
        for settings in self:
            try:
                settings.indexnow_key_url = settings.website_id._indexnow_key_url() if settings.website_id.indexnow_key else False
            except Exception:
                settings.indexnow_key_url = False

    def _indexnow_refresh_settings(self, action):
        action['params']['next'] = {
            'type': 'ir.actions.client',
            'tag': 'website_indexnow_refresh_settings',
            'params': {'setting_id': 'website_indexnow_setting'},
        }
        return action

    def action_indexnow_generate_key(self):
        return self._indexnow_refresh_settings(self.website_id.action_indexnow_generate_key())

    def action_indexnow_regenerate_key(self):
        return self._indexnow_refresh_settings(self.website_id.action_indexnow_regenerate_key())

    def action_indexnow_remove_key(self):
        return self._indexnow_refresh_settings(self.website_id.action_indexnow_remove_key())

    def action_indexnow_verify_key(self):
        return self._indexnow_refresh_settings(self.website_id.action_indexnow_verify_key())

    def action_indexnow_submit_all_pages(self):
        return self.website_id.action_indexnow_submit_all_pages()

    def action_indexnow_process_queue(self):
        return self.website_id.action_indexnow_process_queue()

    def action_indexnow_open_history(self):
        return self.website_id.action_indexnow_open_history()

    def action_indexnow_open_key(self):
        return {'type': 'ir.actions.act_url', 'url': self.website_id._indexnow_key_url(), 'target': 'new'}
