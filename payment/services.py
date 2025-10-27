import requests
from django.conf import settings
import hashlib


class TinkoffPaymentService:
    def __init__(self):
        self.base_url = "https://securepay.tinkoff.ru/v2/"
        self.terminal_key = settings.TINKOFF_TERMINAL_KEY
        self.secret_key = settings.TINKOFF_SECRET_KEY

    def init_payment(self, amount, order_id, description):
        url = f"{self.base_url}Init"
        data = {
            "TerminalKey": self.terminal_key,
            "Amount": amount * 100,  # сумма в копейках
            "OrderId": order_id,
            "Description": description,
        }
        response = requests.post(url, json=data)
        return response.json()

    def check_payment_status(self, payment_id):
        url = f"{self.base_url}GetState"
        data = {
            "TerminalKey": self.terminal_key,
            "PaymentId": payment_id,
        }
        response = requests.post(url, json=data)
        return response.json()

    def refund(self, payment_id, amount):
        url = f"{self.base_url}Cancel"
        data = {
            "TerminalKey": self.terminal_key,
            "PaymentId": payment_id,
            "Amount": amount * 100,  # сумма в копейках
        }
        response = requests.post(url, json=data)
        return response.json()