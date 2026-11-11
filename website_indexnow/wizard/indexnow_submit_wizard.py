# Copyright (C) 2026 Asad Ali (Softosmith)
from odoo import fields, models, _


class IndexNowSubmitWizard(models.TransientModel):
    _name = 'website.indexnow.submit.wizard'
    _description = 'Submit Website Pages to IndexNow'

    website_id = fields.Many2one('website', required=True, default=lambda self: self.env['website'].get_current_website())
    page_ids = fields.Many2many('website.page', string='Website Pages', required=True)
    include_translations = fields.Boolean(default=True)

    def action_queue_urls(self):
        self.ensure_one()
        queued = skipped = 0
        for page in self.page_ids:
            if page.website_id and page.website_id != self.website_id:
                skipped += 1
                continue
            urls = self.website_id._indexnow_page_urls(page, include_translations=self.include_translations)
            if not urls:
                skipped += 1
                continue
            queued += self.env['website.indexnow.queue']._queue_urls(self.website_id, urls, 'manual', page=page)
        return {'type': 'ir.actions.client', 'tag': 'display_notification', 'params': {
            'title': _('IndexNow'),
            'message': _(
                'Done! %(queued)s URLs were added to the submission queue. '
                '%(skipped)s pages were skipped because they are not eligible.',
                queued=queued, skipped=skipped,
            ),
            'type': 'success', 'next': {'type': 'ir.actions.act_window_close'},
        }}
