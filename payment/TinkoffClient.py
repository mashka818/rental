import hashlib
import logging
import requests

from RentalGuru.settings import TINYPAY_TERMINAL_KEY, TINYPAY_PASSWORD, TINYPAY_SUCCESS_URL, TINYPAY_FAIL_URL, HOST_URL

logger = logging.getLogger('payment')


class TinkoffAPI:
    def __init__(self):
        self.base_url = 'https://securepay.tinkoff.ru/v2/'
        self.cancel_url = 'https://securepay.tinkoff.ru/v2/Cancel'
        self.terminal_key = TINYPAY_TERMINAL_KEY
        self.secret_key = TINYPAY_PASSWORD
        self.success_url = TINYPAY_SUCCESS_URL
        self.fail_url = TINYPAY_FAIL_URL

    def _generate_token(self, params):
        """Генерация токена для подписи по спецификации Тинькофф"""
        params["Password"] = self.secret_key
        sorted_params = ''.join(str(params[key]) for key in sorted(params.keys()))
        return hashlib.sha256(sorted_params.encode("utf-8")).hexdigest()

    def create_payment(self, order_id, amount, description, receipt, lang):
        """Создание платежа"""
        payload = {'TerminalKey': self.terminal_key,
                   'Amount': amount,
                   'OrderId': order_id,
                   'Description': description,
                   'SuccessURL': f"{self.success_url}{lang}/profile?trip=true&success=true",
                   'FailURL': f"{self.success_url}{lang}/profile?trip=true&success=false",
                   'NotificationURL': f'{HOST_URL}/payment/callback/'}
        payload['Token'] = self._generate_token(payload)
        payload['Receipt'] = receipt
        response = requests.post(f'{self.base_url}Init', json=payload)
        response.raise_for_status()
        return response.json()

    def cancel_payment(self, payment_id, amount):
        params = {
            "TerminalKey": self.terminal_key,
            "PaymentId": payment_id,
            "Amount": int(amount * 100) if amount else None
        }
        params["Token"] = self._generate_token(params)
        response = requests.post(self.cancel_url, json=params, headers={"Content-Type": "application/json"})
        return response.json()

    def get_state(self, payment_id):
        """Запрос статуса платежа по его ID"""
        payload = {
            "TerminalKey": self.terminal_key,
            "PaymentId": payment_id
        }
        response = requests.post(f"{self.base_url}GetState", json=payload)
        return response.json()
