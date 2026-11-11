# Copyright (C) 2026 Asad Ali (Softosmith)
{
    'name': 'Odoo IndexNow SEO – Automatic URL Submission',
    'version': '19.0.1.1.0',
    'category': 'Website/SEO',
    'summary': 'Automatically submits new and updated website pages to IndexNow-supported search engines.',
    'description': """
IndexNow SEO for standard Odoo Website pages. Generate and verify a separate key for
 each website, queue page changes, and submit canonical URLs asynchronously in safe,
 deduplicated batches. Version 1 supports website.page only.
    """,
    'author': 'Asad Ali (Softosmith)',
    'website': 'https://softosmith.com',
    'support': 'support@softosmith.com',
    'license': 'OPL-1',
    'price': 49.99,
    'currency': 'USD',
    'depends': ['website'],
    'data': [
        'security/indexnow_security.xml',
        'security/ir.model.access.csv',
        'data/indexnow_sequence.xml',
        'data/indexnow_cron.xml',
        'views/res_config_settings_views.xml',
        'data/indexnow_install_action.xml',
        'views/website_page_views.xml',
        'views/indexnow_queue_views.xml',
        'views/indexnow_submission_views.xml',
        'views/indexnow_dashboard_views.xml',
        'wizard/indexnow_submit_wizard_views.xml',
        'views/indexnow_menus.xml',
    ],
    'images': ['static/description/icon.png'],
    'assets': {
        'web.assets_backend': [
            'website_indexnow/static/src/js/indexnow_settings.js',
            'website_indexnow/static/src/js/indexnow_dashboard.js',
            'website_indexnow/static/src/xml/indexnow_dashboard.xml',
            'website_indexnow/static/src/scss/indexnow_dashboard.scss',
        ],
    },
    'installable': True,
    'application': True,
    'auto_install': False,
}
