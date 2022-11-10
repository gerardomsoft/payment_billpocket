import logging
import pprint
import requests
import werkzeug
import json
import time
import socket
from odoo import _, http
from odoo.exceptions import ValidationError
from odoo.http import request
from odoo.addons.payment.controllers.post_processing import PaymentPostProcessing

_logger = logging.getLogger(__name__)


class BillpocketController(http.Controller):
    _test_api_url = 'https://sandboxcore.actnet.com.mx/api'
    _sale_url_direct = '/api/direct_card_sale'
    _sale_url_redirect = '/api/card_sale'
    _login_url = '/login'
    _sale_url = '/sale'
    _confirm_url = '/payment/billpocket/feedback'
    _notify_url = '/payment/billpocket/notify'
    _return_url = '/payment/billpocket/return'
    _token = ''

    # Test Account: TODO eliminar
    # Merchant: alberto.gonzalez@meridasoft.com
    # Password: vcUFLeXrQn9j4vqn
    # Process Token: rLY7fUXyKuGZnVDX

    @staticmethod
    def _get_acquirer_bp():
        """ Return de payment acquirer object for Billpocket. """
        acquirer_bp = request.env['payment.acquirer'].sudo().search([
            ('provider', '=', 'billpocket'),
            ('state', 'in', ('test', 'enabled'))
        ])
        return acquirer_bp

    def _get_url_api(self):
        bp = self._get_acquirer_bp()
        if bp and bp.state == 'enabled':
            return bp.bill_api_url
        elif bp and bp.state == 'test':
            return self._test_api_url
        else:
            return ''

    @http.route(_confirm_url, type='http', auth='public', methods=['POST'], website=True, csrf=False)
    def billpocket_form_feedback(self, **post):
        _logger.info("beginning _handle_feedback_data with post data %s", pprint.pformat(post))
        return request.redirect('/payment/billpocket/data?reference=%s' % post['reference'])

    @http.route('/payment/billpocket/data', type='http', methods=['POST', 'GET'], auth="public", website=True, csrf=False)
    def billpocket_payment_data(self, **post):
        order = request.website.sale_get_order()
        values = {
            'website_sale_order': order,
            'reference': post['reference'],
            'nombre': order and order.partner_id.name or False,
            'card': order and order.partner_id.bank_ids and order.partner_id.bank_ids[0].acc_number or False,
            'action_url': '/billpocket/payment/complete'
        }
        if self._get_acquirer_bp().state == 'test':
            # load test data
            values.update({
                # 'nombre': 'TESTUSER',
                # 'paterno': 'Dummy',
                # 'materno': 'Customer',
                # 'birthday': "1973-02-01",
                'card': '4000000000001091',
                'expire': '02/2025',
                'cvv': '123',
                'card_type': 'VI',
            })
        _logger.info("::::: ODOO SESSION => %s" % request.session)
        return request.render("payment_billpocket.billpocket_complete_payment", values)

    @http.route('/billpocket/payment/complete', type='http', methods=['POST', 'GET'], auth="public", website=True, csrf=False)
    def billpocket_payment_complete(self, **post):
        _logger.info(f'::::: PAYMENT POST => {post} :::::')
        values = {
            'website_sale_order': request.website.sale_get_order(),
            'reference': post['reference'],
            'action_url': '/billpocket/payment/complete'
        }
        # if form submitted
        if 'submitted' in post:
            values.update({
                'nombre': post['nombre'],
                'card': post['card'],
                'expire': post['expire'],
                'cvv': post['cvv'],
                'card_type': post['card_type'],
                # 'birthday': post['birthday'],
            })
        client_err_msg = 'Existen problemas para procesar y completar su pago. ' \
                         u'Intente más tarde nuevamente o seleccione un proveedor de pago diferente!'
        token, error = self.bp_login()
        if token:
            headers = {'Accept': 'application/json', 'Authorization': 'Bearer %s' % token}
            url_conn = "%s%s" % (self._get_url_api(), self._sale_url)
            _logger.info("::::: URL REQUEST => %s" % url_conn)
            json_data = self._get_data_transaction(post, request.website.sale_get_order())
            _logger.info("::::: TRANSACTION DATA => %s" % json_data)
            if self._get_acquirer_bp().connection_type == 'direct':
                # url_conn = "%s%s" % (self._get_url_api(), self._sale_url_direct)
                resp = requests.post(url_conn, headers=headers, json=json_data)
                _logger.info("::::: RESPONSE => %s" % resp.json())
                if 'redirect_url' in resp.json().keys():
                    info = 'Configuración incorrecta, se debe utilizar el Método de conexión Redireccionado!'
                    values.update({'error': '%s \n%s' % (info, client_err_msg)})
                elif 'error' not in resp.json().keys():
                    post.update({
                        "external_transaction_id": resp.json()['external_transaction_id'],
                        "transaction_id": resp.json()['transaction_id'],
                        "status_code": resp.json()['status_code'],
                        "error_code": resp.json()['error_code'],
                        "error_message": resp.json()['error_message']
                    })
                    request.env['payment.transaction'].sudo()._handle_feedback_data('billpocket', post)
                    return request.redirect('/payment/status')
                else:
                    values.update({'error': '%s \nError %s: %s' % (client_err_msg,
                                                                   resp.json()['error']['error_code'],
                                                                   resp.json()['error']['error_message'])
                                   })
            else: # redirect
                # url_conn = werkzeug.urls.url_join(self._get_url_api(), self._sale_url_redirect)
                # _logger.info("::::: URL REQUEST => %s" % url_conn)
                resp = requests.post(url_conn, headers=headers, json=json_data)
                _logger.info("::::: RESPONSE => %s" % resp.json())
                if 'status' in resp.json().keys() and resp.json()['status'] == 1:
                    # redirect to an external website
                    return werkzeug.utils.redirect(resp.json()['redirect_url'])
                else: # got an api error
                    message_error = " "
                    if 'card_number' in resp.json()['error']['error_message']:
                        message_error += ", " + "el número de tarjeta tiene una estructura incorrecta"
                    if 'expiration_year' in resp.json()['error']['error_message']:
                        message_error += ", " + "tarjeta expirada"
                    if 'cvv' in resp.json()['error']['error_message']:
                        message_error += ", " + "CVV incorrecto"
                    message_error += "."

                    values.update({'error': '%s \nError%s' % (client_err_msg,message_error)})
                    # return request.render("payment_billpocket.billpocket_errors", {'error': resp.json()})
        elif error:
            _logger.info("::::: PAYMENT ERROR => %s" % error)
            values.update({'error': client_err_msg})
        return request.render("payment_billpocket.billpocket_complete_payment", values)

    # @http.route(_notify_url, type='http', auth='public', methods=['POST', 'GET'], website=True, csrf=False)
    # def billpocket_notify_status(self, **post):
    @http.route(_return_url, type='http', auth='public', methods=['POST', 'GET'], website=True, csrf=False)
    def billpocket_return_status(self, **post):
        # Used in redirect mode
        _logger.info("::::: API RETURN => %s" % post)
        # update tx data in case of any changes
        request.env['payment.transaction'].sudo()._handle_feedback_data('billpocket', post)

        tx_sudo = request.env['payment.transaction'].sudo().search([
            ('provider', '=', 'billpocket'),
            ('reference', '=', post['external_transaction_id'])
        ])
        # # # Reconstructing odoo session data
        if tx_sudo:
            number = tx_sudo.reference
            refs = tx_sudo.reference.split('-')
            if len(refs) > 1:
                # removing extra characters from sale order reference (-#)
                number = refs[0]
            # Re-adding payment to session to monitor the transaction to make it available in the portal
            PaymentPostProcessing.monitor_transactions(tx_sudo)
            request.session['__website_sale_last_tx_id'] = tx_sudo.id
            # sale_order = request.website.sale_get_order() # return null value
            sale_order = request.env['sale.order'].sudo().search([('name', '=', number)])
            if sale_order:
                request.session['sale_order_id'] = sale_order.id
                request.session['sale_last_order_id'] = sale_order.id
                request.session['website_sale_current_pl'] = sale_order.pricelist_id.id
            _logger.info("::::: ODOO SESSION => %s" % request.session)

        # return request.redirect('/shop/payment/validate')
        return request.redirect('/payment/status')

    # @http.route(_return_url, type='http', auth='public', methods=['POST', 'GET'], website=True, csrf=False)
    # def billpocket_return_status(self, **post):
    @http.route(_notify_url, type='http', auth='public', methods=['POST', 'GET'], website=True, csrf=False)
    def billpocket_notify_status(self, **post):
        # Used in redirect mode
        _logger.info("::::: API NOTIFY => %s" % post)
        # the API calls route '_notify_url' first and then call route '_return_url' returning same data
        # and redirecting to Odoo
        if 'external_transaction_id' not in post.keys():
            # add test data for test purposes
            post.update({
                'external_transaction_id': "BP-TEST",
                'transaction_id': "123456",
                'status_code': 3,
                'error_code': "0",
                'error_message': "Approved"
            })
        # update tx data from response
        request.env['payment.transaction'].sudo()._handle_feedback_data('billpocket', post)
        return json.dumps(post)

    def bp_login(self, **data):
        bp = self._get_acquirer_bp()
        if bp:
            json_data = {'merchant': bp.bill_seller_account, 'password': bp.bill_seller_pass}
            url_conn = "%s%s" % (self._get_url_api(), self._login_url)
            _logger.info("::::: API LOGIN => %s" % url_conn)
            try:
                resp = requests.post(url_conn, json=json_data)
            except requests.exceptions.ConnectionError as e:
                _logger.info("::::: LOGIN ERROR => %s" % e)
                return False, u'Error: API URL incorrecta o existen problemas con la conexión!'
            # _logger.info("::::: JSON => %s" % resp.json())
            if 'error' in resp.json().keys():
                msg = '"Error": {"error_code": "%s","error_message": "%s"}' % \
                       (resp.json()['error']['error_code'], resp.json()['error']['error_message'])
                _logger.info("::::: API ERROR => %s" % msg)
                return False, msg
            self._token = resp.json()['token']
            return resp.json()['token'], False
        return False, u'Error: No se encontró método de pago activo para Billpocket!'

    def _get_data_transaction(self, post, order):
        bp = self._get_acquirer_bp()
        first_name, last_name = self._separate_names(post.get('nombre'))
        ts = int(time.time())  # ts stores the timestamp in seconds
        # _logger.info("::::: TIMESTAMP = %s" % ts)
        data = {
            "transaction_id": post.get('reference'),
            # "transaction_id": '%s-%s' % (str(ts), post.get('reference')),
            "description": "Odoo %s" % post.get('reference'),
            "process_token": bp.bill_process_token,
            "amount": order and order.amount_total or 1.00,
            # "usd_amount": 1.00, # optional
            "currency_code": order.currency_id.name,
            "customer_username": bp.bill_seller_account,
            "first_name": first_name,
            "last_name": last_name,
            # "birth_date": post['birthday'], # optional
            "email": order.partner_id.email,
            "phone": order.partner_id.phone,
            "country": order.partner_id.country_id.code,
            "state": order.partner_id.state_id.code,
            "city": order.partner_id.city,
            "address": "%s %s" % (order.partner_id.street, order.partner_id.street2),
            "zip_code": order.partner_id.zip,
            "ip_address": socket.gethostbyname(socket.gethostname()),
            "name_on_card": post.get('nombre'),
            "card_number": post.get('card'),
            "expiration_month": post.get('expire').split('/')[0],
            "expiration_year": post.get('expire').split('/')[1],
            "cvv": post.get('cvv'),
            "card_type": post.get('card_type')
        }
        # Datos no requeridos que no sabemos de donde obtenerlos.
        # data.update({
        #     "vip_level": 0,
        #     "account_creation_date": time.strftime('%Y-%m-%d'), # "2010-02-18",
        #     "first_deposit_date": "2010-02-18",
        #     "first_withdraw_date": "2012-01-28",
        #     "last_deposit_date": "2019-10-08",
        #     "last_withdraw_date": "2019-08-19",
        #     "number_of_deposits": 0,
        #     "number_of_withdraws": 0
        # })
        return data

    @staticmethod
    def _separate_names(full_name):
        first_name, last_name = '', ''
        words = full_name.split()
        if len(words) == 1:
            return words[0], ''
        if len(words) == 2:
            return words[0], words[1]
        elif len(words) > 2:
            last_name = ' '.join(words[-2:])
            first_name = ' '.join(words[0:len(words)-2])
        return first_name, last_name

    # # # TEST CODE - ONLY FOR TESTING PURPOSES # # #

    @http.route('/names', auth='public', type='http', csrf=False)
    def show_separate_names(self):
        return '%s / %s' % self._separate_names(full_name='Jose de Maria Apellido1 Apellido2')

    @staticmethod
    def _get_test_transaction(reference, process_token='rLY7fUXyKuGZnVDX', order=None):
        return {
            "transaction_id": reference,  # "123456",
            "description": "Odoo %s" % reference,
            "process_token": process_token,
            "amount": order and order.amount_total or 1.00,
            # "usd_amount": 1.00,
            "currency_code": "MXN",
            "customer_username": "TESTUSER",
            "first_name": "Dummy",
            "last_name": "Customer",
            # "birth_date": "1973-02-01",
            "email": "dummycustomer@test.com",
            "phone": "5550001",
            "country": "US",
            "state": "CA",
            "city": "Beverly Hills",
            "address": "1 Rodeo Do",
            "zip_code": "90210",
            "name_on_card": "Dummy Customer",
            "card_number": "4111111111111111",
            "expiration_year": "2025",
            "expiration_month": "02",
            "cvv": "123",
            "card_type": "VI",
            "ip_address": "127.0.0.1",
            # "vip_level": 0,
            # "account_creation_date": "2010-02-18",
            # "first_deposit_date": "2010-02-18",
            # "first_withdraw_date": "2012-01-28",
            # "last_deposit_date": "2019-10-08",
            # "last_withdraw_date": "2019-08-19",
            # "number_of_deposits": 10,
            # "number_of_withdraws": 8
        }

    @http.route('/bp/login', auth='public', type='http', csrf=False)
    def bp_login_test(self, **data):
        # Route for manual test api connection and authentication of the account returning the security token.
        bp = self._get_acquirer_bp()
        if bp:
            json_data = {'merchant': bp.bill_seller_account, 'password': bp.bill_seller_pass}
            url_conn = "%s%s" % (self._get_url_api(), self._login_url)
            # url_conn = self._get_url_login()
            _logger.info("::::: API TEST CONN => %s" % url_conn)
            try:
                resp = requests.post(url_conn, json=json_data)
            except requests.exceptions.ConnectionError as e:
                return u'API URL incorrecta o existen problemas con la conexión! Error: %s' % e
            _logger.info("::::: JSON => %s" % resp.json())
            if 'error' in resp.json().keys():
                return '"Error": {"error_code": "%s","error_message": "%s"}' % \
                       (resp.json()['error']['error_code'], resp.json()['error']['error_message'])

            return resp.json()['token']
        return 'Billpocket payment method disabled!'

    @http.route('/api/test', type='http', auth='public', methods=['GET', 'POST'], csrf=False)
    def test_login(self, **data):
        json_data = {'merchant': 'alberto.gonzalez@meridasoft.com', 'password': 'vcUFLeXrQn9j4vqn'}
        # url_conn = werkzeug.urls.url_join(self._test_api_url, self._login_url)
        url_conn = "%s%s" % (self._get_url_api(), self._login_url)
        _logger.info("::::: API TEST => %s" % url_conn)
        r = requests.post(url_conn, json=json_data)
        self._token = r.json()['token'] if 'token' in r.json().keys() else ''
        _logger.info("::::: TOKEN => %s" % self._token)
        return r.text

    @http.route('/api', type='http', auth='public', method=['POST'], csrf=False)
    def printjson(self, **kw):
        payload = {'key1': 'value1', 'key2': 'value2'}
        # r = requests.post("https://httpbin.org/post", json=json.dumps(payload))
        r = requests.post("https://httpbin.org/post", json=payload)
        _logger.info("::::: JSON => %s" % r.json())
        _logger.info("::::: IP %s" % socket.gethostbyname(socket.gethostname()))
        return r.text

    @http.route('/test-error', type='http', auth='public', methods=['GET', 'POST'], csrf=False)
    def test_error_info(self, **post):
        _logger.info("::::: POST => %s" % post)
        if 'external_transaction_id' not in post.keys():
            # add test data
            post.update({
                'external_transaction_id': "BP-TEST",
                'transaction_id': None,
                'status_code': 0,
                'error_code': "T3",
                'error_message': "card_not_supported"
            })
        # update tx data from post
        request.env['payment.transaction'].sudo()._handle_feedback_data('billpocket', post)
        return json.dumps(post)
