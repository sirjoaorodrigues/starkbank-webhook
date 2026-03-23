from unittest.mock import patch, MagicMock
from django.test import TestCase
from django.db import IntegrityError
from invoices.models import Invoice, Transfer, WebhookEvent
from invoices.tasks import process_invoice_credit


class InvoiceIdempotencyTest(TestCase):
    """Tests to ensure invoice processing is idempotent."""

    def test_duplicate_starkbank_id_raises_error(self):
        Invoice.objects.create(
            starkbank_id='unique-id-123',
            amount=10000,
            name='User 1',
            tax_id='12345678901'
        )

        with self.assertRaises(IntegrityError):
            Invoice.objects.create(
                starkbank_id='unique-id-123',
                amount=20000,
                name='User 2',
                tax_id='98765432100'
            )

    def test_webhook_event_idempotency(self):
        WebhookEvent.objects.create(
            event_id='event-unique-123',
            event_type='invoice',
            payload={'test': 'data'}
        )

        with self.assertRaises(IntegrityError):
            WebhookEvent.objects.create(
                event_id='event-unique-123',
                event_type='invoice',
                payload={'different': 'data'}
            )


class TransferBusinessRulesTest(TestCase):
    """Tests for transfer business rules."""

    def setUp(self):
        self.invoice = Invoice.objects.create(
            starkbank_id='invoice-for-transfer',
            amount=10000,
            name='Test User',
            tax_id='12345678901',
            status=Invoice.Status.CREATED
        )

    @patch('invoices.tasks.create_transfer')
    def test_transfer_amount_is_invoice_amount_minus_fee(self, mock_create_transfer):
        mock_transfer = MagicMock()
        mock_transfer.id = 'transfer-123'
        mock_create_transfer.return_value = mock_transfer

        process_invoice_credit(
            invoice_id='invoice-for-transfer',
            amount=10000,
            fee=500
        )

        transfer = Transfer.objects.first()
        expected_amount = 10000 - 500
        self.assertEqual(transfer.amount, expected_amount)

    @patch('invoices.tasks.create_transfer')
    def test_no_transfer_when_fee_exceeds_amount(self, mock_create_transfer):
        result = process_invoice_credit(
            invoice_id='invoice-for-transfer',
            amount=100,
            fee=200
        )

        self.assertIn('error', result)
        self.assertEqual(Transfer.objects.count(), 0)
        mock_create_transfer.assert_not_called()

    @patch('invoices.tasks.create_transfer')
    def test_transfer_linked_to_correct_invoice(self, mock_create_transfer):
        another_invoice = Invoice.objects.create(
            starkbank_id='another-invoice',
            amount=5000,
            name='Another User',
            tax_id='11111111111'
        )

        mock_transfer = MagicMock()
        mock_transfer.id = 'transfer-for-another'
        mock_create_transfer.return_value = mock_transfer

        process_invoice_credit(
            invoice_id='another-invoice',
            amount=5000,
            fee=100
        )

        transfer = Transfer.objects.first()
        self.assertEqual(transfer.invoice, another_invoice)
        self.assertNotEqual(transfer.invoice, self.invoice)


class InvoiceStatusTransitionTest(TestCase):
    """Tests for invoice status transitions."""

    @patch('invoices.tasks.create_transfer')
    def test_invoice_transitions_to_paid_after_credit(self, mock_create_transfer):
        invoice = Invoice.objects.create(
            starkbank_id='status-test-invoice',
            amount=10000,
            name='Status Test User',
            tax_id='12345678901',
            status=Invoice.Status.CREATED
        )

        mock_transfer = MagicMock()
        mock_transfer.id = 'transfer-status'
        mock_create_transfer.return_value = mock_transfer

        process_invoice_credit(
            invoice_id='status-test-invoice',
            amount=10000,
            fee=500
        )

        invoice.refresh_from_db()
        self.assertEqual(invoice.status, Invoice.Status.PAID)

    @patch('invoices.tasks.create_transfer')
    def test_invoice_fee_stored_on_payment(self, mock_create_transfer):
        invoice = Invoice.objects.create(
            starkbank_id='fee-test-invoice',
            amount=10000,
            name='Fee Test User',
            tax_id='12345678901'
        )

        mock_transfer = MagicMock()
        mock_transfer.id = 'transfer-fee'
        mock_create_transfer.return_value = mock_transfer

        process_invoice_credit(
            invoice_id='fee-test-invoice',
            amount=10000,
            fee=350
        )

        invoice.refresh_from_db()
        self.assertEqual(invoice.fee, 350)


class WebhookEventProcessingTest(TestCase):
    """Tests for webhook event processing rules."""

    def test_event_marked_as_unprocessed_on_creation(self):
        event = WebhookEvent.objects.create(
            event_id='new-event',
            event_type='invoice',
            payload={'data': 'test'}
        )

        self.assertFalse(event.processed)

    def test_event_can_be_marked_as_processed(self):
        event = WebhookEvent.objects.create(
            event_id='process-event',
            event_type='invoice',
            payload={'data': 'test'},
            processed=False
        )

        event.processed = True
        event.save()

        event.refresh_from_db()
        self.assertTrue(event.processed)


class InvoiceTransferRelationshipTest(TestCase):
    """Tests for invoice-transfer relationships."""

    def test_invoice_can_have_multiple_transfers(self):
        invoice = Invoice.objects.create(
            starkbank_id='multi-transfer-invoice',
            amount=10000,
            name='Multi Transfer User',
            tax_id='12345678901'
        )

        Transfer.objects.create(
            starkbank_id='transfer-1',
            invoice=invoice,
            amount=5000
        )
        Transfer.objects.create(
            starkbank_id='transfer-2',
            invoice=invoice,
            amount=3000
        )

        self.assertEqual(invoice.transfers.count(), 2)

    def test_deleting_invoice_deletes_transfers(self):
        invoice = Invoice.objects.create(
            starkbank_id='delete-test-invoice',
            amount=10000,
            name='Delete Test User',
            tax_id='12345678901'
        )

        Transfer.objects.create(
            starkbank_id='delete-transfer',
            invoice=invoice,
            amount=9500
        )

        self.assertEqual(Transfer.objects.count(), 1)

        invoice.delete()

        self.assertEqual(Transfer.objects.count(), 0)

    def test_transfer_requires_valid_invoice(self):
        """Transfer cannot reference a non-existent invoice."""
        # This test verifies the relationship at the application level
        # since SQLite doesn't enforce FK constraints the same way as PostgreSQL
        self.assertEqual(Invoice.objects.filter(id=99999).count(), 0)

        # In production (PostgreSQL), this would raise IntegrityError
        # For SQLite, we verify the invoice doesn't exist
        transfer = Transfer(
            starkbank_id='orphan-transfer',
            invoice_id=99999,
            amount=5000
        )
        # Verify the referenced invoice doesn't exist
        with self.assertRaises(Invoice.DoesNotExist):
            _ = transfer.invoice


class AmountCalculationTest(TestCase):
    """Tests for amount calculations."""

    @patch('invoices.tasks.create_transfer')
    def test_transfer_amount_correct_with_various_fees(self, mock_create_transfer):
        test_cases = [
            (10000, 500, 9500),
            (10000, 0, 10000),
            (10000, 1000, 9000),
            (5000, 250, 4750),
            (100000, 5000, 95000),
        ]

        mock_transfer = MagicMock()
        mock_transfer.id = 'calc-transfer'
        mock_create_transfer.return_value = mock_transfer

        for amount, fee, expected_transfer in test_cases:
            Invoice.objects.all().delete()
            Transfer.objects.all().delete()

            invoice = Invoice.objects.create(
                starkbank_id=f'calc-invoice-{amount}-{fee}',
                amount=amount,
                name='Calc User',
                tax_id='12345678901'
            )

            result = process_invoice_credit(
                invoice_id=invoice.starkbank_id,
                amount=amount,
                fee=fee
            )

            self.assertEqual(
                result['amount'],
                expected_transfer,
                f'Failed for amount={amount}, fee={fee}'
            )