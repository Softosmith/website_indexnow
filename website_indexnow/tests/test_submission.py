from odoo.tests.common import TransactionCase


class TestIndexNowSubmission(TransactionCase):
    def test_cross_domain_url_is_rejected(self):
        website = self.env['website'].create({'name': 'IndexNow', 'domain': 'https://indexnow.example.com', 'indexnow_key': 'a' * 32})
        self.assertFalse(website._indexnow_normalize_url('https://other.example.com/page'))
