# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging
from werkzeug import urls
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from odoo.http import request
from odoo.addons.payment import utils as payment_utils
from odoo.addons.payment_billpocket.controllers.main import BillpocketController

_logger = logging.getLogger(__name__)


class PaymentTransaction(models.Model):
    _inherit = 'payment.transaction'

    bill_external_transaction_id = fields.Char('External Transaction ID')
    bill_transaction_id = fields.Char('Transaction ID')
    bill_response_message = fields.Char('Transaction Result')
    bill_status_code = fields.Char('Transaction Status Code',
                                help="3:Approved / 4:Rejected / 6:Refund / 7:Chargeback / 8:Rejected by Fraud Control")
    bill_error_message = fields.Char('Transaction Error')

    # # Transaction status codes:
    # 3 Approved transaction
    # 4 Rejected transaction
    # 6 Refund
    # 7 Chargeback
    # 8 Rejected by Fraud Control

    def _get_specific_rendering_values(self, processing_values):
        """ Override of payment to return Paypal-specific rendering values.

        Note: self.ensure_one() from `_get_processing_values`

        :param dict processing_values: The generic and specific processing values of the transaction
        :return: The dict of acquirer-specific processing values
        :rtype: dict
        """
        res = super()._get_specific_rendering_values(processing_values)
        if self.provider != 'billpocket':
            return res

        # base_url = self.acquirer_id.get_base_url()
        partner_first_name, partner_last_name = payment_utils.split_partner_name(self.partner_name)
        return {
            'address1': self.partner_address,
            'amount': self.amount,
            'city': self.partner_city,
            'country': self.partner_country_id.code,
            'currency_code': self.currency_id.name,
            'email': self.partner_email,
            'first_name': partner_first_name,
            'handling': self.fees,
            'item_name': f"{self.company_id.name}: {self.reference}",
            'item_number': self.reference,
            'last_name': partner_last_name,
            'lc': self.partner_lang,
            'state': self.partner_state_id.name,
            'zip_code': self.partner_zip,
            'api_url': BillpocketController._confirm_url,
            'reference': self.reference,
        }

    @api.model
    def _get_tx_from_feedback_data(self, provider, data):
        """ Override of payment to find the transaction based on Paypal data.

        :param str provider: The provider of the acquirer that handled the transaction
        :param dict data: The feedback data sent by the provider
        :return: The transaction if found
        :rtype: recordset of `payment.transaction`
        :raise: ValidationError if the data match no transaction
        """
        tx = super()._get_tx_from_feedback_data(provider, data)
        if provider != 'billpocket':
            return tx

        reference = data.get('reference')
        if not reference:
            # used in redirect mode
            reference = data.get('external_transaction_id')

        tx = self.search([('reference', '=', reference), ('provider', '=', 'billpocket')])
        if not tx:
            raise ValidationError(
                "Billpocket: " + _("No transaction found matching reference %s.", reference)
            )
        return tx

    def _process_feedback_data(self, data):
        """ Override of payment to process the transaction based on transfer data.

        Note: self.ensure_one()

        :param dict data: The transfer feedback data
        :return: None
        """
        super()._process_feedback_data(data)
        if self.provider != 'billpocket':
            return

        values = {
            "bill_external_transaction_id": data.get('external_transaction_id'),
            "bill_transaction_id": data.get('transaction_id'),
            "bill_status_code": data.get('status_code'),
            "bill_response_message": data.get('error_message'),
        }
        self.write(values)
        status_code = int(data.get('status_code', '0'))
        state_message = f"Error code {data.get('error_code')}: {data.get('error_message')}"
        if status_code == 3:
            self._set_done()
        elif status_code in [4, 8]:
            self._set_canceled(state_message=state_message)
        elif status_code in [6, 7]:
            self._set_pending(state_message=state_message)
        else:
            msg = u'Ocurrió un error durante el pago. Por favor revisar transacción directo con el Proveedor Billpocket!'
            self._set_error(state_message='%s\n%s' % (msg, state_message))
        _logger.info("::::: Validated payment transaction with reference %s: set as %s! :::::"
                     % (self.reference, self.state))
