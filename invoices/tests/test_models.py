from django.test import TestCase
from invoices.models import Invoice, Transfer, WebhookEvent


class InvoiceModelTest(TestCase):

    def test_create_invoice(self):
        invoice = Invoice.objects.create(
            starkbank_id='123456789',
            amount=10000,
            name='Test User',
            tax_id='12345678901',
            status=Invoice.Status.CREATED
        )
        self.assertEqual(invoice.starkbank_id, '123456789')
        self.assertEqual(invoice.amount, 10000)
        self.assertEqual(invoice.status, Invoice.Status.CREATED)

    def test_invoice_str(self):
        invoice = Invoice.objects.create(
            starkbank_id='123456789',
            amount=10000,
            name='Test User',
            tax_id='12345678901'
        )
        self.assertEqual(str(invoice), 'Invoice 123456789 - Test User')

    def test_invoice_status_choices(self):
        self.assertEqual(Invoice.Status.CREATED, 'created')
        self.assertEqual(Invoice.Status.PAID, 'paid')
        self.assertEqual(Invoice.Status.CANCELED, 'canceled')
        self.assertEqual(Invoice.Status.OVERDUE, 'overdue')


class TransferModelTest(TestCase):

    def setUp(self):
        self.invoice = Invoice.objects.create(
            starkbank_id='123456789',
            amount=10000,
            name='Test User',
            tax_id='12345678901'
        )

    def test_create_transfer(self):
        transfer = Transfer.objects.create(
            starkbank_id='987654321',
            invoice=self.invoice,
            amount=9500,
            status=Transfer.Status.PROCESSING
        )
        self.assertEqual(transfer.starkbank_id, '987654321')
        self.assertEqual(transfer.amount, 9500)
        self.assertEqual(transfer.invoice, self.invoice)

    def test_transfer_str(self):
        transfer = Transfer.objects.create(
            starkbank_id='987654321',
            invoice=self.invoice,
            amount=9500
        )
        self.assertEqual(str(transfer), 'Transfer 987654321 - 9500')

    def test_invoice_transfer_relationship(self):
        Transfer.objects.create(
            starkbank_id='987654321',
            invoice=self.invoice,
            amount=9500
        )
        self.assertEqual(self.invoice.transfers.count(), 1)


class WebhookEventModelTest(TestCase):

    def test_create_webhook_event(self):
        event = WebhookEvent.objects.create(
            event_id='event-123',
            event_type='invoice',
            payload={'test': 'data'}
        )
        self.assertEqual(event.event_id, 'event-123')
        self.assertEqual(event.event_type, 'invoice')
        self.assertFalse(event.processed)

    def test_webhook_event_str(self):
        event = WebhookEvent.objects.create(
            event_id='event-123',
            event_type='invoice',
            payload={}
        )
        self.assertEqual(str(event), 'Event event-123 - invoice')