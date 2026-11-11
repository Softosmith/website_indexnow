# Tests intentionally supplied as an implementation checklist; run only during explicit verification.
from odoo.tests.common import TransactionCase


class TestIndexNowKeyRoute(TransactionCase):
    def test_key_generation_is_per_website(self):
        websites = self.env['website'].create([
            {'name': 'One', 'domain': 'https://one.example.com'},
            {'name': 'Two', 'domain': 'https://two.example.com'},
        ])
        websites[0].action_indexnow_generate_key()
        websites[1].action_indexnow_generate_key()
        self.assertEqual(len(websites[0].indexnow_key), 32)
        self.assertNotEqual(websites[0].indexnow_key, websites[1].indexnow_key)
