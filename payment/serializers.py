from rest_framework import serializers
from payment.models import Payment


class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = ['id', 'request_rent', 'amount', 'deposite', 'delivery', 'status', 'payment_id', 'created_at', 'url']
