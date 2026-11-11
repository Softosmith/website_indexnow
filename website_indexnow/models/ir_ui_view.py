# Copyright (C) 2026 Asad Ali (Softosmith)
from odoo import models


class IrUiView(models.Model):
    _inherit = 'ir.ui.view'

    def write(self, vals):
        tracked_fields = {'arch', 'arch_db', 'arch_base'}
        pages = self.mapped('page_ids') if tracked_fields & set(vals) else self.env['website.page']
        result = super().write(vals)
        if pages and not self.env.context.get('indexnow_skip_tracking'):
            for page in pages.exists():
                for website in page._indexnow_websites():
                    if website.indexnow_enabled and website.indexnow_auto_submit:
                        urls = website._indexnow_page_urls(page)
                        if urls:
                            self.env['website.indexnow.queue']._queue_urls(website, urls, 'updated', page=page)
        return result
