from django.contrib import admin
from .models import Invoice, Transfer, WebhookEvent, InvoiceCampaign


@admin.register(InvoiceCampaign)
class InvoiceCampaignAdmin(admin.ModelAdmin):
    list_display = ['id', 'is_active', 'execution_count', 'max_executions', 'started_at']
    list_filter = ['is_active', 'started_at']
    readonly_fields = ['started_at', 'execution_count']
    actions = ['deactivate_campaigns', 'activate_campaigns']

    @admin.action(description='Deactivate selected campaigns')
    def deactivate_campaigns(self, request, queryset):
        queryset.update(is_active=False)

    @admin.action(description='Activate selected campaigns')
    def activate_campaigns(self, request, queryset):
        queryset.update(is_active=True)


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ['starkbank_id', 'name', 'amount', 'status', 'created_at']
    list_filter = ['status', 'created_at']
    search_fields = ['starkbank_id', 'name', 'tax_id']
    readonly_fields = ['starkbank_id', 'created_at', 'updated_at']


@admin.register(Transfer)
class TransferAdmin(admin.ModelAdmin):
    list_display = ['starkbank_id', 'invoice', 'amount', 'status', 'created_at']
    list_filter = ['status', 'created_at']
    search_fields = ['starkbank_id']
    readonly_fields = ['starkbank_id', 'created_at', 'updated_at']


@admin.register(WebhookEvent)
class WebhookEventAdmin(admin.ModelAdmin):
    list_display = ['event_id', 'event_type', 'processed', 'created_at']
    list_filter = ['event_type', 'processed', 'created_at']
    search_fields = ['event_id']
    readonly_fields = ['event_id', 'event_type', 'payload', 'created_at']