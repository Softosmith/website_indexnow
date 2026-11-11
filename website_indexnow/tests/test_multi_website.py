from odoo.tests.common import TransactionCase


class TestIndexNowMultiWebsite(TransactionCase):
    def test_domains_keep_separate_keys(self):
        one = self.env['website'].create({'name': 'One', 'domain': 'https://one.example.com'})
        two = self.env['website'].create({'name': 'Two', 'domain': 'https://two.example.com'})
        one.action_indexnow_generate_key()
        two.action_indexnow_generate_key()
        self.assertNotEqual(one._indexnow_key_url(), two._indexnow_key_url())
