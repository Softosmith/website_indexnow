from odoo.tests.common import TransactionCase


class TestIndexNowPageQueue(TransactionCase):
    def test_private_page_is_not_eligible(self):
        website = self.env['website'].create({'name': 'IndexNow', 'domain': 'https://indexnow.example.com', 'indexnow_enabled': True, 'indexnow_key': 'a' * 32})
        view = self.env['ir.ui.view'].create({'name': 'Private', 'type': 'qweb', 'key': 'test.private', 'arch': '<t/>', 'website_id': website.id, 'visibility': 'connected'})
        page = self.env['website.page'].create({'name': 'Private', 'url': '/private', 'view_id': view.id, 'is_published': True})
        self.assertFalse(website._indexnow_page_urls(page))
