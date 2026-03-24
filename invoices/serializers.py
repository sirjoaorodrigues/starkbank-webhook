from rest_framework import serializers
from .models import Invoice, Transfer, WebhookEvent


class InvoiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Invoice
        fields = ['id', 'starkbank_id', 'amount', 'name', 'status', 'fee', 'created_at', 'updated_at']


class TransferSerializer(serializers.ModelSerializer):
    class Meta:
        model = Transfer
        fields = ['id', 'starkbank_id', 'invoice', 'amount', 'status', 'created_at', 'updated_at']


class WebhookEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = WebhookEvent
        fields = ['id', 'event_id', 'event_type', 'processed', 'created_at']