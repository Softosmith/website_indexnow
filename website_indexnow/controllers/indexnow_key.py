# Copyright (C) 2026 Asad Ali (Softosmith)
from odoo import http
from odoo.http import request
from werkzeug.exceptions import NotFound


class IndexNowKeyController(http.Controller):

    @http.route(
        '/<string:key>.txt',
        type='http',
        auth='public',
        methods=['GET'],
        website=True,
        csrf=False,
        sitemap=False,
        save_session=False,
        readonly=True,
    )
    def indexnow_key(self, key, **kwargs):
        website = request.website
        if not website:
            raise NotFound()
        website = website.sudo()
        if not website.indexnow_enabled or not website.indexnow_key or key != website.indexnow_key:
            raise NotFound()
        return request.make_response(
            website.indexnow_key,
            headers=[('Content-Type', 'text/plain; charset=utf-8'), ('Cache-Control', 'no-store')],
        )
