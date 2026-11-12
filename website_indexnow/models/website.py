# Copyright (C) 2026 Asad Ali (Softosmith)
import ipaddress
import secrets
import urllib.error
import urllib.request
from datetime import timedelta
from urllib.parse import urljoin, urlsplit, urlunsplit

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError


class Website(models.Model):
    _inherit = 'website'

    indexnow_enabled = fields.Boolean(string='Enable IndexNow', default=False)
    indexnow_key = fields.Char(string='IndexNow API Key', copy=False, groups='website_indexnow.group_indexnow_manager')
    indexnow_auto_submit = fields.Boolean(string='Automatic Submission', default=True)
    indexnow_submit_translations = fields.Boolean(string='Submit Translated URLs', default=True)
    indexnow_submission_delay = fields.Selection([
        ('0', 'Immediately'), ('5', '5 minutes'), ('15', '15 minutes'),
        ('30', '30 minutes'), ('60', '60 minutes'),
    ], default='5', required=True)
    indexnow_batch_size = fields.Integer(default=100, required=True)
    indexnow_endpoint = fields.Char(default='https://api.indexnow.org/indexnow', required=True)
    indexnow_key_verified = fields.Boolean(readonly=True, copy=False)
    indexnow_key_verified_on = fields.Datetime(readonly=True, copy=False)
    indexnow_last_success_on = fields.Datetime(readonly=True, copy=False)
    indexnow_last_error = fields.Text(readonly=True, copy=False)
    indexnow_health = fields.Selection([
        ('ready', 'Ready'), ('disabled', 'Disabled'), ('domain_missing', 'Domain Missing'),
        ('key_missing', 'Key Missing'), ('key_unverified', 'Key File Not Verified'),
        ('failures', 'Submission Failures'),
    ], compute='_compute_indexnow_dashboard')
    indexnow_pending_count = fields.Integer(compute='_compute_indexnow_dashboard')
    indexnow_failed_count = fields.Integer(compute='_compute_indexnow_dashboard')
    indexnow_submitted_today = fields.Integer(compute='_compute_indexnow_dashboard')
    indexnow_submitted_week = fields.Integer(compute='_compute_indexnow_dashboard')

    _indexnow_batch_size_check = models.Constraint(
        'CHECK(indexnow_batch_size >= 1 AND indexnow_batch_size <= 10000)',
        'IndexNow batch size must be between 1 and 10,000.',
    )

    def _compute_indexnow_dashboard(self):
        Queue = self.env['website.indexnow.queue'].sudo()
        Submission = self.env['website.indexnow.submission'].sudo()
        now = fields.Datetime.now()
        for website in self:
            website.indexnow_pending_count = Queue.search_count([('website_id', '=', website.id), ('state', 'in', ('pending', 'processing'))])
            website.indexnow_failed_count = Queue.search_count([('website_id', '=', website.id), ('state', '=', 'failed')])
            website.indexnow_submitted_today = Submission.search_count([('website_id', '=', website.id), ('submitted_on', '>=', now - timedelta(days=1)), ('result', 'in', ('success', 'accepted'))])
            website.indexnow_submitted_week = Submission.search_count([('website_id', '=', website.id), ('submitted_on', '>=', now - timedelta(days=7)), ('result', 'in', ('success', 'accepted'))])
            if not website.indexnow_enabled:
                website.indexnow_health = 'disabled'
            elif not website.domain:
                website.indexnow_health = 'domain_missing'
            elif not website.indexnow_key:
                website.indexnow_health = 'key_missing'
            elif website.indexnow_failed_count:
                website.indexnow_health = 'failures'
            elif not website.indexnow_key_verified:
                website.indexnow_health = 'key_unverified'
            else:
                website.indexnow_health = 'ready'

    @api.model
    def get_indexnow_dashboard_data(self, days=7, website_id=False):
        """Return the compact, aggregated payload used by the OWL dashboard."""
        self.check_access('read')
        days = int(days) if str(days).isdigit() else 7
        days = days if days in (1, 7, 30) else 7
        websites = self.search([])
        try:
            website_id = int(website_id) if website_id else False
        except (TypeError, ValueError):
            website_id = False
        selected = websites.filtered(lambda website: website.id == website_id) if website_id else websites
        if website_id and not selected:
            selected = websites

        now = fields.Datetime.now()
        start = now - timedelta(days=days)
        website_ids = selected.ids
        Queue = self.env['website.indexnow.queue'].sudo()
        Submission = self.env['website.indexnow.submission'].sudo()
        queue_domain = [('website_id', 'in', website_ids)]
        submission_domain = [('website_id', 'in', website_ids), ('submitted_on', '>=', start)]

        submissions = Submission.search(submission_domain)
        successful = submissions.filtered(lambda item: item.result in ('success', 'accepted'))
        failed = submissions.filtered(lambda item: item.result == 'failed')
        submitted_urls = sum(successful.mapped('url_count'))
        failed_urls = sum(failed.mapped('url_count'))
        total_urls = submitted_urls + failed_urls

        activity = {}
        for offset in range(days - 1, -1, -1):
            day = (now - timedelta(days=offset)).date()
            activity[day] = {
                'key': fields.Date.to_string(day),
                'label': day.strftime('%b %d'),
                'submitted': 0,
                'failed': 0,
            }
        for submission in submissions:
            day = submission.submitted_on.date()
            if day in activity:
                key = 'failed' if submission.result == 'failed' else 'submitted'
                activity[day][key] += submission.url_count

        health_labels = dict(self._fields['indexnow_health'].selection)
        website_rows = []
        for website in (selected if website_id else websites):
            website_rows.append({
                'id': website.id,
                'name': website.name,
                'domain': website.domain or _('Domain not configured'),
                'enabled': website.indexnow_enabled,
                'health': website.indexnow_health,
                'health_label': health_labels.get(website.indexnow_health, website.indexnow_health),
                'key_verified': website.indexnow_key_verified,
                'has_key': bool(website.indexnow_key),
                'pending': website.indexnow_pending_count,
                'failed': website.indexnow_failed_count,
                'submitted_today': website.indexnow_submitted_today,
                'submitted_week': website.indexnow_submitted_week,
                'last_success': fields.Datetime.to_string(website.indexnow_last_success_on) if website.indexnow_last_success_on else False,
                'last_error': website.indexnow_last_error or False,
            })

        recent_submissions = Submission.search(
            [('website_id', 'in', website_ids)], limit=8, order='submitted_on desc, id desc'
        )
        recent_activity = [{
            'id': submission.id,
            'name': submission.name,
            'website': submission.website_id.name,
            'result': submission.result,
            'url_count': submission.url_count,
            'trigger': dict(submission._fields['trigger'].selection).get(submission.trigger),
            'submitted_on': fields.Datetime.to_string(submission.submitted_on),
            'http_status': submission.http_status,
        } for submission in recent_submissions]

        pending = Queue.search(queue_domain + [('state', 'in', ('pending', 'processing'))], limit=6, order='next_attempt, id')
        queue_preview = [{
            'id': item.id,
            'website': item.website_id.name,
            'url': item.url,
            'event': dict(item._fields['event'].selection).get(item.event),
            'state': item.state,
            'attempts': item.attempts,
            'next_attempt': fields.Datetime.to_string(item.next_attempt),
        } for item in pending]

        return {
            'generated_at': fields.Datetime.to_string(now),
            'days': days,
            'selected_website_id': website_id,
            'kpis': {
                'enabled_websites': len(selected.filtered('indexnow_enabled')),
                'total_websites': len(selected),
                'submitted_urls': submitted_urls,
                'pending_urls': Queue.search_count(queue_domain + [('state', 'in', ('pending', 'processing'))]),
                'failed_urls': Queue.search_count(queue_domain + [('state', '=', 'failed')]),
                'success_rate': round((submitted_urls / total_urls) * 100, 1) if total_urls else 100.0,
            },
            'activity': list(activity.values()),
            'website_options': [{'id': website.id, 'name': website.name} for website in websites],
            'websites': website_rows,
            'recent_activity': recent_activity,
            'queue_preview': queue_preview,
        }

    @api.constrains('indexnow_endpoint')
    def _check_indexnow_endpoint(self):
        for website in self:
            parsed = urlsplit(website.indexnow_endpoint or '')
            if parsed.scheme not in ('http', 'https') or not parsed.hostname:
                raise ValidationError(_('The IndexNow endpoint must be a valid HTTP(S) URL.'))

    def write(self, vals):
        reset_verification = 'domain' in vals or 'indexnow_key' in vals
        result = super().write(vals)
        if reset_verification and not self.env.context.get('indexnow_skip_verification_reset'):
            super(Website, self).write({
                'indexnow_key_verified': False,
                'indexnow_key_verified_on': False,
            })
        if vals.get('indexnow_enabled'):
            for website in self:
                website._indexnow_require_ready(require_key=False)
        return result

    def _indexnow_public_origin(self):
        self.ensure_one()
        value = (self.domain or '').strip()
        parsed = urlsplit(value)
        if parsed.scheme not in ('http', 'https') or not parsed.hostname or parsed.username or parsed.password:
            raise UserError(_('Public website domain must be configured as a valid HTTP(S) URL.'))
        hostname = parsed.hostname.rstrip('.').lower()
        if hostname == 'localhost' or hostname.endswith('.localhost') or '.' not in hostname:
            raise UserError(_('IndexNow requires a public website domain; local or internal hostnames are not supported.'))
        try:
            address = ipaddress.ip_address(hostname)
            if not address.is_global:
                raise UserError(_('IndexNow requires a public website domain; private and loopback addresses are not supported.'))
        except ValueError:
            pass
        netloc = hostname
        if parsed.port and not ((parsed.scheme == 'http' and parsed.port == 80) or (parsed.scheme == 'https' and parsed.port == 443)):
            netloc = f'{hostname}:{parsed.port}'
        return urlunsplit((parsed.scheme.lower(), netloc, '', '', '')).rstrip('/')

    def _indexnow_require_ready(self, require_key=True):
        self.ensure_one()
        origin = self._indexnow_public_origin()
        if require_key and not self.indexnow_key:
            raise UserError(_('Generate an IndexNow key before submitting URLs.'))
        return origin

    def _indexnow_key_url(self):
        self.ensure_one()
        return f'{self._indexnow_require_ready()}/{self.indexnow_key}.txt'

    def action_indexnow_generate_key(self):
        self.ensure_one()
        if self.indexnow_key and not self.env.context.get('indexnow_confirm_regenerate'):
            raise UserError(_('A key already exists. Use Regenerate Key and confirm replacement.'))
        self._indexnow_require_ready(require_key=False)
        self.with_context(indexnow_skip_verification_reset=True).write({
            'indexnow_key': secrets.token_hex(16),
            'indexnow_key_verified': False,
            'indexnow_key_verified_on': False,
            'indexnow_last_error': False,
        })
        return self._indexnow_notification(_(
            'Your new IndexNow key was generated successfully. '
            'Please click “Verify Key” to confirm it is publicly accessible.'
        ))

    def action_indexnow_regenerate_key(self):
        return self.with_context(indexnow_confirm_regenerate=True).action_indexnow_generate_key()

    def action_indexnow_remove_key(self):
        self.ensure_one()
        if not self.env.user.has_group('website_indexnow.group_indexnow_manager'):
            raise AccessError(_('Only an IndexNow Manager can remove the key file.'))
        self.write({
            'indexnow_key': False,
            'indexnow_key_verified': False,
            'indexnow_key_verified_on': False,
            'indexnow_last_error': False,
        })
        return self._indexnow_notification(_(
            'Your IndexNow key was removed successfully. '
            'Generate a new key before submitting URLs again.'
        ))

    def action_indexnow_verify_key(self):
        self.ensure_one()
        key_url = self._indexnow_key_url()
        try:
            request = urllib.request.Request(key_url, method='GET', headers={'User-Agent': 'Odoo-IndexNow/1.0'})
            with urllib.request.urlopen(request, timeout=15) as response:
                status = response.status
                body = response.read(256).decode('utf-8', errors='replace')
            if status != 200 or body != self.indexnow_key:
                raise UserError(_(
                    'We could not verify the key file. Make sure the key URL is publicly accessible '
                    'and displays only your current IndexNow key, then try again.'
                ))
        except UserError:
            raise
        except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
            message = self._indexnow_sanitize_error(exc)
            self.sudo().write({'indexnow_key_verified': False, 'indexnow_last_error': message})
            raise UserError(_(
                'We could not access your IndexNow key file. Please open the key URL to confirm it '
                'is publicly accessible, then try again. Technical details: %s'
            ) % message) from exc
        self.sudo().write({
            'indexnow_key_verified': True,
            'indexnow_key_verified_on': fields.Datetime.now(),
            'indexnow_last_error': False,
        })
        return self._indexnow_notification(_(
            'Your IndexNow key was verified successfully. You can now submit URLs.'
        ))

    def _indexnow_pages(self):
        self.ensure_one()
        return self.with_context(website_id=self.id)._get_website_pages()

    def _indexnow_page_urls(self, page, include_translations=None, allow_ineligible=False):
        self.ensure_one()
        if not allow_ineligible and not self._indexnow_page_is_eligible(page):
            return []
        origin = self._indexnow_require_ready()
        path = urlsplit(page.url or '').path
        if not path.startswith('/') or path.startswith(('/web', '/my', '/portal')) or path == f'/{self.indexnow_key}.txt':
            return []
        include = self.indexnow_submit_translations if include_translations is None else include_translations
        languages = self.language_ids if include else self.default_lang_id
        urls = []
        for language in languages:
            localized_path = path
            if language != self.default_lang_id:
                localized_path = f'/{language.url_code}{path if path != "/" else ""}'
            url = urljoin(f'{origin}/', localized_path.lstrip('/'))
            if self._indexnow_normalize_url(url):
                urls.append(self._indexnow_normalize_url(url))
        return list(dict.fromkeys(urls))

    def _indexnow_page_is_eligible(self, page):
        self.ensure_one()
        return bool(
            self.indexnow_enabled and self.indexnow_key
            and (not page.website_id or page.website_id == self)
            and page.website_published and page.website_indexed
            and (not page.publish_on or page.publish_on <= fields.Datetime.now())
            and page.visibility == 'public'
        )

    def _indexnow_normalize_url(self, url):
        self.ensure_one()
        try:
            origin = urlsplit(self._indexnow_public_origin())
            parsed = urlsplit(url)
        except (ValueError, UserError):
            return False
        if parsed.scheme not in ('http', 'https') or parsed.hostname != origin.hostname or parsed.port != origin.port:
            return False
        if parsed.query or parsed.fragment or not parsed.path.startswith('/'):
            return False
        if parsed.path.startswith(('/web', '/my', '/portal')) or parsed.path == f'/{self.indexnow_key}.txt':
            return False
        path = '/' + '/'.join(segment for segment in parsed.path.split('/') if segment)
        if parsed.path.endswith('/') and path != '/':
            path += '/'
        return urlunsplit((origin.scheme, origin.netloc, path, '', ''))

    def action_indexnow_submit_all_pages(self):
        self.ensure_one()
        self._indexnow_require_ready()
        queued = skipped = 0
        for page in self._indexnow_pages():
            urls = self._indexnow_page_urls(page)
            if not urls:
                skipped += 1
                continue
            queued += self.env['website.indexnow.queue']._queue_urls(self, urls, 'initial', page=page)
        return self._indexnow_notification(_(
            'Done! %(queued)s URLs were added to the submission queue. '
            '%(skipped)s private or non-indexable pages were skipped.',
            queued=queued, skipped=skipped,
        ))

    def action_indexnow_process_queue(self):
        self.ensure_one()
        result = self.env['website.indexnow.queue']._process_due(website=self, trigger='manual', include_future=True)
        return self._indexnow_notification(_(
            'Queue processing is complete: %(submitted)s URLs were submitted, '
            '%(accepted)s were accepted, and %(failed)s failed.',
            **result,
        ), sticky=True)

    def action_indexnow_open_history(self):
        self.ensure_one()
        action = self.env['ir.actions.actions']._for_xml_id('website_indexnow.action_indexnow_submission')
        action['domain'] = [('website_id', '=', self.id)]
        return action

    def _indexnow_notification(self, message, sticky=False, refresh=False):
        params = {
            'title': _('IndexNow'), 'message': message, 'type': 'success', 'sticky': sticky,
        }
        if refresh:
            params['next'] = {'type': 'ir.actions.client', 'tag': 'soft_reload'}
        return {'type': 'ir.actions.client', 'tag': 'display_notification', 'params': params}

    @api.model
    def _indexnow_sanitize_error(self, error, key=None):
        text = str(error or '')[:1000]
        if key:
            text = text.replace(key, '[redacted]')
        return text
