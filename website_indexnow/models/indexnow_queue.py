# Copyright (C) 2026 Asad Ali (Softosmith)
import json
import time
import urllib.error
import urllib.request
from datetime import timedelta
from urllib.parse import urlsplit

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class IndexNowQueue(models.Model):
    _name = 'website.indexnow.queue'
    _description = 'IndexNow URL Queue'
    _order = 'queued_on desc, id desc'

    website_id = fields.Many2one('website', required=True, ondelete='cascade', index=True)
    page_id = fields.Many2one('website.page', ondelete='set null', index=True)
    url = fields.Char(required=True, index=True)
    event = fields.Selection([
        ('created', 'Created'), ('updated', 'Updated'), ('published', 'Published'),
        ('unpublished', 'Unpublished'), ('moved', 'Moved'), ('deleted', 'Deleted'),
        ('restricted', 'Restricted'), ('non_indexed', 'Non-indexed'),
        ('initial', 'Initial Sync'), ('manual', 'Manual'),
    ], required=True, default='updated')
    state = fields.Selection([
        ('pending', 'Pending'), ('processing', 'Processing'), ('submitted', 'Submitted'),
        ('accepted', 'Accepted'), ('failed', 'Failed'), ('cancelled', 'Cancelled'),
    ], default='pending', required=True, index=True)
    attempts = fields.Integer(default=0, readonly=True)
    next_attempt = fields.Datetime(default=fields.Datetime.now, required=True, index=True)
    queued_on = fields.Datetime(default=fields.Datetime.now, required=True, readonly=True)
    submitted_on = fields.Datetime(readonly=True)
    last_http_status = fields.Integer(readonly=True)
    last_error = fields.Text(readonly=True)
    submission_id = fields.Many2one('website.indexnow.submission', ondelete='set null', readonly=True, index=True)

    @api.model
    def _queue_urls(self, website, urls, event, page=None, delay=None):
        if not website.indexnow_enabled:
            return 0
        delay = int(website.indexnow_submission_delay) if delay is None else delay
        due = fields.Datetime.now() + timedelta(minutes=delay)
        count = 0
        for raw_url in dict.fromkeys(urls):
            url = website._indexnow_normalize_url(raw_url)
            if not url:
                continue
            existing = self.sudo().search([
                ('website_id', '=', website.id), ('url', '=', url),
                ('state', 'in', ('pending', 'processing')),
            ], limit=1)
            values = {'event': event, 'queued_on': fields.Datetime.now(), 'next_attempt': due, 'last_error': False}
            if page:
                values['page_id'] = page.id
            if existing:
                existing.write(values)
            else:
                self.sudo().create(dict(values, website_id=website.id, url=url, state='pending'))
                count += 1
        return count

    @api.model
    def _process_due(self, website=None, trigger='cron', include_future=False):
        domain = [('state', '=', 'pending')]
        if not include_future:
            domain.append(('next_attempt', '<=', fields.Datetime.now()))
        if website:
            domain.append(('website_id', '=', website.id))
        websites = self.sudo().search(domain).mapped('website_id')
        totals = {'submitted': 0, 'accepted': 0, 'failed': 0}
        for current in websites:
            due_clause = '' if include_future else 'AND next_attempt <= %s'
            params = [current.id]
            if not include_future:
                params.append(fields.Datetime.now())
            query = "SELECT id FROM website_indexnow_queue WHERE state = 'pending' AND website_id = %s " + due_clause + " ORDER BY next_attempt, id FOR UPDATE SKIP LOCKED"
            self.env.cr.execute(query, params)
            entries = self.sudo().browse([row[0] for row in self.env.cr.fetchall()])
            for batch in (entries[offset:offset + current.indexnow_batch_size] for offset in range(0, len(entries), current.indexnow_batch_size)):
                result = self._send_batch(current, batch, trigger)
                totals[result] += len(batch)
        return totals

    @api.model
    def _send_batch(self, website, entries, trigger):
        entries = entries.exists().filtered(lambda item: item.state == 'pending')
        if not entries:
            return 'failed'
        valid_entries = entries.filtered(lambda item: website._indexnow_normalize_url(item.url))
        invalid_entries = entries - valid_entries
        if invalid_entries:
            invalid_entries.write({'state': 'failed', 'last_error': _('URL host mismatch or invalid URL.')})
        if not valid_entries:
            return 'failed'
        try:
            origin = website._indexnow_require_ready()
        except UserError as exc:
            error = website._indexnow_sanitize_error(exc, website.indexnow_key)
            valid_entries.write({'state': 'failed', 'last_error': error})
            website.sudo().write({'indexnow_last_error': error})
            return 'failed'

        valid_entries.write({'state': 'processing'})
        attempt = max(valid_entries.mapped('attempts') or [0]) + 1
        payload = {
            'host': urlsplit(origin).netloc,
            'key': website.indexnow_key,
            'keyLocation': website._indexnow_key_url(),
            'urlList': list(dict.fromkeys(valid_entries.mapped('url'))),
        }
        status = 0
        response_text = ''
        started = time.monotonic()
        try:
            request = urllib.request.Request(
                website.indexnow_endpoint,
                data=json.dumps(payload).encode('utf-8'),
                headers={'Content-Type': 'application/json; charset=utf-8', 'User-Agent': 'Odoo-IndexNow/1.0'},
                method='POST',
            )
            with urllib.request.urlopen(request, timeout=20) as response:
                status = response.status
                response_text = response.read(2048).decode('utf-8', errors='replace')
        except urllib.error.HTTPError as exc:
            status = exc.code
            response_text = exc.read(2048).decode('utf-8', errors='replace')
        except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
            response_text = website._indexnow_sanitize_error(exc, website.indexnow_key)
        duration = time.monotonic() - started
        response_text = website._indexnow_sanitize_error(response_text, website.indexnow_key)
        result = 'success' if status == 200 else 'accepted' if status == 202 else 'failed'
        submission = self.env['website.indexnow.submission'].sudo().create({
            'website_id': website.id, 'host': payload['host'], 'endpoint': website.indexnow_endpoint,
            'urls': '\n'.join(payload['urlList']), 'url_count': len(payload['urlList']),
            'trigger': trigger, 'submitted_by': self.env.user.id, 'duration': duration,
            'http_status': status, 'result': result, 'response': response_text, 'attempt_number': attempt,
        })
        values = {'attempts': attempt, 'last_http_status': status, 'submission_id': submission.id}
        if result in ('success', 'accepted'):
            values.update({'state': 'submitted' if result == 'success' else 'accepted', 'submitted_on': fields.Datetime.now(), 'last_error': False})
            website.sudo().write({'indexnow_last_success_on': fields.Datetime.now(), 'indexnow_last_error': False})
        elif status in (400, 403, 422) or attempt >= 5:
            values.update({'state': 'failed', 'last_error': response_text or _('Permanent IndexNow submission failure (HTTP %s).') % status})
            website.sudo().write({'indexnow_last_error': values['last_error']})
        else:
            backoff = {1: 15, 2: 60, 3: 360, 4: 1440}.get(attempt, 1440)
            values.update({'state': 'pending', 'next_attempt': fields.Datetime.now() + timedelta(minutes=backoff), 'last_error': response_text or _('Temporary IndexNow failure; retry scheduled automatically.')})
            website.sudo().write({'indexnow_last_error': values['last_error']})
        valid_entries.write(values)
        return result

    @api.model
    def _cron_process_queue(self):
        self._process_due(trigger='cron')

    @api.model
    def _cron_cleanup(self):
        now = fields.Datetime.now()
        self.sudo().search([
            ('state', 'in', ('submitted', 'accepted', 'cancelled')),
            ('queued_on', '<', now - timedelta(days=30)),
        ]).unlink()
        self.env['website.indexnow.submission'].sudo().search([
            ('submitted_on', '<', now - timedelta(days=90)),
        ]).unlink()

    def action_process_now(self):
        result = self._process_due(website=self[:1].website_id if self else None, trigger='manual', include_future=True)
        return {'type': 'ir.actions.client', 'tag': 'display_notification', 'params': {
            'title': _('IndexNow'),
            'message': _(
                'Queue processing is complete: %(submitted)s URLs were submitted, '
                '%(accepted)s were accepted, and %(failed)s failed.',
                **result,
            ),
            'type': 'success',
        }}

    def _retry_failed(self):
        records = self.filtered(lambda item: item.state == 'failed')
        records.write({'state': 'pending', 'attempts': 0, 'next_attempt': fields.Datetime.now(), 'last_error': False})
        return len(records)

    def action_retry(self):
        count = self._retry_failed()
        return {'type': 'ir.actions.client', 'tag': 'display_notification', 'params': {
            'title': _('IndexNow'),
            'message': _('%s failed URLs were added back to the queue for another attempt.') % count,
            'type': 'success',
        }}

    def action_cancel(self):
        self.filtered(lambda item: item.state in ('pending', 'processing')).write({'state': 'cancelled'})

    def action_open_url(self):
        self.ensure_one()
        return {'type': 'ir.actions.act_url', 'url': self.url, 'target': 'new'}

    def action_open_page(self):
        self.ensure_one()
        if not self.page_id:
            raise UserError(_('The related Website page no longer exists.'))
        return {'type': 'ir.actions.act_window', 'res_model': 'website.page', 'res_id': self.page_id.id, 'view_mode': 'form', 'target': 'current'}
