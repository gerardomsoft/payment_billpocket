# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging
from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)


class PaymentAcquirer(models.Model):
    _inherit = 'payment.acquirer'

    provider = fields.Selection(
        selection_add=[('billpocket', "Billpocket")], ondelete={'billpocket': 'set default'})
    bill_seller_account = fields.Char(
        string="Merchant Account", groups='base.group_system')
    bill_seller_pass = fields.Char(
        string="Password", groups='base.group_system')
    bill_process_token = fields.Char(string="Process Token", groups='base.group_system')
    bill_api_url = fields.Char(string="API URL", groups='base.group_system')
    connection_type = fields.Selection([
        ('direct', "Direct"),
        ('redirect', "Redirect")
        ], string='Connection Type', default="direct",
        help="Direct: Pago se realiza desde Odoo. / "
             "Redirect: Se redirecciona a otra web para completar el pago fuera de Odoo.")

    # def _paypal_get_api_url(self):
    #    """ Return the API URL according to the acquirer state.
    #
    #    Note: self.ensure_one()
    #
    #    :return: The API URL
    #    :rtype: str
    #    """
    #    self.ensure_one()
    #
    #    if self.state == 'enabled':
    #        return 'https://www.paypal.com/cgi-bin/webscr'
    #    else:
    #        return 'https://www.sandbox.paypal.com/cgi-bin/webscr'

    def _get_default_payment_method_id(self):
        self.ensure_one()
        if self.provider != 'billpocket':
            return super()._get_default_payment_method_id()
        return self.env.ref('payment_billpocket.payment_method_billpocket').id
