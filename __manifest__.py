# -*- coding: utf-8 -*-
{
    'name': 'Billpocket Payment Acquirer',
    'summary': 'Payment Acquirer: Billpocket Implementation',
    'description': """Billpocket Payment Acquirer""",
    'category': 'Accounting/Payment Acquirers',
    'author': 'Meridasoft',
    'website': 'https://meridasoft.com',
    'version': '0.1',
    'depends': ['base', 'payment'],
    'data': [
        'views/payment_billpocket_templates.xml',
        'views/payment_views.xml',
        'data/payment_acquirer_data.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'payment_billpocket/static/src/css/styles.css',
            'payment_billpocket/static/src/js/billpocket.js',
            'payment_billpocket/static/src/js/payment.js',
        ],
    },
    'installable': True,
    'application': True,
    'auto_install': False,
}
