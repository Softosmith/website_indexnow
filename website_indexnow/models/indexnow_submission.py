# Copyright (C) 2026 Asad Ali (Softosmith)
from odoo import api, fields, models, _


class IndexNowSubmission(models.Model):
    _name = 'website.indexnow.submission'
    _description = 'IndexNow Submission'
    _order = 'submitted_on desc, id desc'

    name = fields.Char(default=lambda self: _('New'), readonly=True, copy=False)
    website_id = fields.Many2one('website', required=True, ondelete='cascade', index=True)
    host = fields.Char(required=True, readonly=True)
    endpoint = fields.Char(required=True, readonly=True)
    urls = fields.Text(required=True, readonly=True)
    url_count = fields.Integer(required=True, readonly=True)
    trigger = fields.Selection([
        ('cron', 'Scheduled Job'), ('manual', 'Manual'), ('initial', 'Initial Sync'), ('retry', 'Retry'),
    ], required=True, readonly=True)
    submitted_by = fields.Many2one('res.users', readonly=True)
    submitted_on = fields.Datetime(default=fields.Datetime.now, required=True, readonly=True)
    duration = fields.Float(readonly=True, digits=(16, 3), help='Request duration in seconds')
    http_status = fields.Integer(readonly=True)
    result = fields.Selection([('success', 'Submitted'), ('accepted', 'Accepted'), ('failed', 'Failed')], required=True, readonly=True)
    response = fields.Text(readonly=True)
    attempt_number = fields.Integer(default=1, required=True, readonly=True)
    queue_ids = fields.One2many('website.indexnow.queue', 'submission_id', readonly=True)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('name') or vals['name'] == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('website.indexnow.submission') or _('New')
        return super().create(vals_list)

    def action_retry_failed_urls(self):
        count = 0
        Queue = self.env['website.indexnow.queue']
        for submission in self.filtered(lambda item: item.result == 'failed'):
            failed = submission.queue_ids.filtered(lambda item: item.state == 'failed')
            count += failed._retry_failed()
            if not failed:
                urls = [url for url in (submission.urls or '').splitlines() if url]
                count += Queue._queue_urls(submission.website_id, urls, 'manual', delay=0)
        return {'type': 'ir.actions.client', 'tag': 'display_notification', 'params': {
            'title': _('IndexNow'),
            'message': _('%s failed URLs were added back to the queue for another attempt.') % count,
            'type': 'success',
        }}

    def action_open_website(self):
        self.ensure_one()
        return {'type': 'ir.actions.act_url', 'url': self.website_id._indexnow_public_origin(), 'target': 'new'}
