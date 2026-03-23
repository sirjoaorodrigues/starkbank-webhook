from django.db import models


class Invoice(models.Model):
    """Model to track invoices created in Stark Bank."""

    class Status(models.TextChoices):
        CREATED = 'created', 'Created'
        PAID = 'paid', 'Paid'
        CANCELED = 'canceled', 'Canceled'
        OVERDUE = 'overdue', 'Overdue'

    starkbank_id = models.CharField(max_length=100, unique=True)
    amount = models.BigIntegerField(help_text='Amount in cents')
    name = models.CharField(max_length=255)
    tax_id = models.CharField(max_length=20)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.CREATED
    )
    fee = models.BigIntegerField(null=True, blank=True, help_text='Fee in cents')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'Invoice {self.starkbank_id} - {self.name}'


class Transfer(models.Model):
    """Model to track transfers made from paid invoices."""

    class Status(models.TextChoices):
        CREATED = 'created', 'Created'
        PROCESSING = 'processing', 'Processing'
        SUCCESS = 'success', 'Success'
        FAILED = 'failed', 'Failed'

    starkbank_id = models.CharField(max_length=100, unique=True, null=True, blank=True)
    invoice = models.ForeignKey(
        Invoice,
        on_delete=models.CASCADE,
        related_name='transfers'
    )
    amount = models.BigIntegerField(help_text='Amount in cents')
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.CREATED
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'Transfer {self.starkbank_id} - {self.amount}'


class WebhookEvent(models.Model):
    """Model to store webhook events for auditing."""

    event_id = models.CharField(max_length=100, unique=True)
    event_type = models.CharField(max_length=100)
    payload = models.JSONField()
    processed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'Event {self.event_id} - {self.event_type}'