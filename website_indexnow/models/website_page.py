# Copyright (C) 2026 Asad Ali (Softosmith)
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class WebsitePage(models.Model):
    _inherit = 'website.page'

    indexnow_state = fields.Selection([
        ('not_eligible', 'Not Eligible'), ('never', 'Never Submitted'), ('pending', 'Pending'),
        ('submitted', 'Submitted'), ('accepted', 'Accepted'), ('failed', 'Failed'), ('removed', 'Removed'),
    ], compute='_compute_indexnow_status', string='IndexNow Status')
    indexnow_last_queued_on = fields.Datetime(compute='_compute_indexnow_status')
    indexnow_last_submitted_on = fields.Datetime(compute='_compute_indexnow_status')
    indexnow_last_http_status = fields.Integer(compute='_compute_indexnow_status')
    indexnow_last_url = fields.Char(compute='_compute_indexnow_status')
    indexnow_submission_count = fields.Integer(compute='_compute_indexnow_status')

    def _indexnow_websites(self):
        self.ensure_one()
        return self.website_id if self.website_id else self.env['website'].sudo().search([])

    def _indexnow_snapshot(self):
        snapshots = {}
        for page in self:
            snapshots[page.id] = {}
            for website in page._indexnow_websites():
                try:
                    snapshots[page.id][website.id] = {
                        'eligible': website._indexnow_page_is_eligible(page),
                        'urls': website._indexnow_page_urls(page, allow_ineligible=True),
                    }
                except UserError:
                    snapshots[page.id][website.id] = {'eligible': False, 'urls': []}
        return snapshots

    def _indexnow_queue_transition(self, before, vals):
        if self.env.context.get('indexnow_skip_tracking'):
            return
        visibility_fields = {'website_published', 'is_published', 'publish_on', 'visibility', 'group_ids', 'website_indexed'}
        content_fields = {'arch', 'arch_db', 'name', 'website_meta_title', 'website_meta_description', 'website_meta_keywords'}
        for page in self:
            for website in page._indexnow_websites():
                if not website.indexnow_enabled or not website.indexnow_auto_submit:
                    continue
                old = before.get(page.id, {}).get(website.id, {'eligible': False, 'urls': []})
                current_urls = website._indexnow_page_urls(page)
                new_eligible = bool(current_urls)
                old_urls = old['urls'] if old['eligible'] else []
                if old['eligible'] and not new_eligible:
                    event = 'unpublished'
                    if 'website_indexed' in vals and not page.website_indexed:
                        event = 'non_indexed'
                    elif ({'visibility', 'group_ids'} & set(vals)) and page.visibility != 'public':
                        event = 'restricted'
                    self.env['website.indexnow.queue']._queue_urls(website, old_urls, event, page=page)
                elif not old['eligible'] and new_eligible:
                    self.env['website.indexnow.queue']._queue_urls(website, current_urls, 'published', page=page)
                elif new_eligible:
                    old_only = set(old_urls) - set(current_urls)
                    new_only = set(current_urls) - set(old_urls)
                    if old_only or new_only:
                        self.env['website.indexnow.queue']._queue_urls(website, list(old_only), 'moved', page=page)
                        self.env['website.indexnow.queue']._queue_urls(website, current_urls, 'moved', page=page)
                    elif visibility_fields & set(vals) or content_fields & set(vals):
                        self.env['website.indexnow.queue']._queue_urls(website, current_urls, 'updated', page=page)

    @api.model_create_multi
    def create(self, vals_list):
        pages = super().create(vals_list)
        if not self.env.context.get('indexnow_skip_tracking'):
            for page in pages:
                for website in page._indexnow_websites():
                    if website.indexnow_auto_submit:
                        self.env['website.indexnow.queue']._queue_urls(website, website._indexnow_page_urls(page), 'created', page=page)
        return pages

    def write(self, vals):
        before = self._indexnow_snapshot()
        result = super().write(vals)
        self._indexnow_queue_transition(before, vals)
        return result

    def unlink(self):
        snapshots = self._indexnow_snapshot()
        queues = []
        for page in self:
            for website_id, snapshot in snapshots.get(page.id, {}).items():
                if snapshot['eligible']:
                    queues.append((self.env['website'].browse(website_id), snapshot['urls']))
        result = super().unlink()
        for website, urls in queues:
            self.env['website.indexnow.queue']._queue_urls(website, urls, 'deleted')
        return result

    def _compute_indexnow_status(self):
        Queue = self.env['website.indexnow.queue'].sudo()
        for page in self:
            latest = Queue.search([('page_id', '=', page.id)], order='queued_on desc, id desc', limit=1)
            page.indexnow_submission_count = Queue.search_count([('page_id', '=', page.id), ('submission_id', '!=', False)])
            page.indexnow_last_queued_on = latest.queued_on
            page.indexnow_last_submitted_on = latest.submitted_on
            page.indexnow_last_http_status = latest.last_http_status
            page.indexnow_last_url = latest.url
            eligible = any(website._indexnow_page_is_eligible(page) and bool(website.domain) for website in page._indexnow_websites())
            if not eligible:
                page.indexnow_state = 'removed' if latest and latest.event in ('unpublished', 'restricted', 'non_indexed', 'deleted') else 'not_eligible'
            elif not latest:
                page.indexnow_state = 'never'
            elif latest.state == 'accepted':
                page.indexnow_state = 'accepted'
            elif latest.state == 'submitted':
                page.indexnow_state = 'submitted'
            elif latest.state == 'failed':
                page.indexnow_state = 'failed'
            else:
                page.indexnow_state = 'pending'

    def action_indexnow_submit(self):
        queued = skipped = 0
        for page in self:
            for website in page._indexnow_websites():
                urls = website._indexnow_page_urls(page)
                if urls:
                    queued += self.env['website.indexnow.queue']._queue_urls(website, urls, 'manual', page=page, delay=0)
                else:
                    skipped += 1
        return {'type': 'ir.actions.client', 'tag': 'display_notification', 'params': {
            'title': _('IndexNow'),
            'message': _(
                'Done! %(queued)s URLs were added to the submission queue. '
                '%(skipped)s page and website combinations were skipped because they are not eligible.',
                queued=queued, skipped=skipped,
            ),
            'type': 'success',
        }}

    def action_indexnow_retry(self):
        records = self.env['website.indexnow.queue'].search([('page_id', 'in', self.ids), ('state', '=', 'failed')])
        count = records._retry_failed()
        return {'type': 'ir.actions.client', 'tag': 'display_notification', 'params': {
            'title': _('IndexNow'),
            'message': _('%s failed URLs were added back to the queue for another attempt.') % count,
            'type': 'success',
        }}

    def action_indexnow_history(self):
        action = self.env['ir.actions.actions']._for_xml_id('website_indexnow.action_indexnow_submission')
        action['domain'] = [('queue_ids.page_id', 'in', self.ids)]
        return action
