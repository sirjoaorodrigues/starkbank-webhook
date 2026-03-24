from unittest.mock import patch, MagicMock
from django.test import TestCase
from invoices.models import Invoice, Transfer, InvoiceCampaign
from invoices.tasks import issue_invoices, process_invoice_credit


class IssueInvoicesTaskTest(TestCase):

    def setUp(self):
        self.campaign = InvoiceCampaign.objects.create(
            max_executions=8,
            is_active=True
        )

    @patch('invoices.tasks.create_invoices')
    def test_issue_invoices_creates_records(self, mock_create_invoices):
        mock_invoice = MagicMock()
        mock_invoice.id = '123456789'
        mock_invoice.amount = 10000
        mock_invoice.name = 'Test User'
        mock_invoice.tax_id = '12345678901'
        mock_create_invoices.return_value = [mock_invoice]

        with patch('invoices.tasks.random.randint', return_value=1):
            result = issue_invoices()

        self.assertEqual(result['created'], 1)
        self.assertEqual(result['campaign_id'], self.campaign.id)
        self.assertEqual(result['execution'], 1)
        self.assertEqual(Invoice.objects.count(), 1)
        invoice = Invoice.objects.first()
        self.assertEqual(invoice.starkbank_id, '123456789')
        self.assertEqual(invoice.status, Invoice.Status.CREATED)

    @patch('invoices.tasks.create_invoices')
    def test_issue_invoices_count_range(self, mock_create_invoices):
        mock_create_invoices.return_value = []

        with patch('invoices.tasks.random.randint') as mock_randint:
            mock_randint.return_value = 10
            issue_invoices()
            mock_randint.assert_called_with(8, 12)

    @patch('invoices.tasks.create_invoices')
    def test_issue_invoices_passes_campaign_id(self, mock_create_invoices):
        """Task should pass campaign_id to create_invoices."""
        mock_create_invoices.return_value = []

        with patch('invoices.tasks.random.randint', return_value=8):
            issue_invoices()

        mock_create_invoices.assert_called_once_with(8, campaign_id=self.campaign.id)

    @patch('invoices.tasks.create_invoices')
    def test_issue_invoices_creates_multiple_records(self, mock_create_invoices):
        mock_invoices = []
        for i in range(10):
            mock_invoice = MagicMock()
            mock_invoice.id = f'invoice-{i}'
            mock_invoice.amount = 1000 * (i + 1)
            mock_invoice.name = f'User {i}'
            mock_invoice.tax_id = f'1234567890{i}'
            mock_invoices.append(mock_invoice)

        mock_create_invoices.return_value = mock_invoices

        with patch('invoices.tasks.random.randint', return_value=10):
            result = issue_invoices()

        self.assertEqual(result['created'], 10)
        self.assertEqual(result['campaign_id'], self.campaign.id)
        self.assertEqual(Invoice.objects.count(), 10)

    @patch('invoices.tasks.create_invoices')
    def test_issue_invoices_api_error_raises_exception(self, mock_create_invoices):
        mock_create_invoices.side_effect = Exception('API Error')

        with patch('invoices.tasks.random.randint', return_value=8):
            with self.assertRaises(Exception) as context:
                issue_invoices()

        self.assertIn('API Error', str(context.exception))
        self.assertEqual(Invoice.objects.count(), 0)

    @patch('invoices.tasks.create_invoices')
    def test_issue_invoices_all_have_created_status(self, mock_create_invoices):
        mock_invoices = []
        for i in range(3):
            mock_invoice = MagicMock()
            mock_invoice.id = f'invoice-{i}'
            mock_invoice.amount = 5000
            mock_invoice.name = f'User {i}'
            mock_invoice.tax_id = f'1234567890{i}'
            mock_invoices.append(mock_invoice)

        mock_create_invoices.return_value = mock_invoices

        with patch('invoices.tasks.random.randint', return_value=3):
            issue_invoices()

        for invoice in Invoice.objects.all():
            self.assertEqual(invoice.status, Invoice.Status.CREATED)


class ProcessInvoiceCreditTaskTest(TestCase):

    def setUp(self):
        self.invoice = Invoice.objects.create(
            starkbank_id='123456789',
            amount=10000,
            name='Test User',
            tax_id='12345678901',
            status=Invoice.Status.CREATED
        )

    @patch('invoices.tasks.create_transfer')
    def test_process_invoice_credit_success(self, mock_create_transfer):
        mock_transfer = MagicMock()
        mock_transfer.id = '987654321'
        mock_create_transfer.return_value = mock_transfer

        result = process_invoice_credit(
            invoice_id='123456789',
            amount=10000,
            fee=500
        )

        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.status, Invoice.Status.PAID)
        self.assertEqual(self.invoice.fee, 500)
        self.assertEqual(result['transfer_id'], '987654321')
        self.assertEqual(result['amount'], 9500)
        self.assertEqual(Transfer.objects.count(), 1)

    @patch('invoices.tasks.create_transfer')
    def test_process_invoice_credit_zero_amount(self, mock_create_transfer):
        result = process_invoice_credit(
            invoice_id='123456789',
            amount=500,
            fee=500
        )

        self.assertEqual(result['error'], 'Transfer amount is zero or negative')
        mock_create_transfer.assert_not_called()
        self.assertEqual(Transfer.objects.count(), 0)

    @patch('invoices.tasks.create_transfer')
    def test_process_invoice_credit_negative_amount(self, mock_create_transfer):
        result = process_invoice_credit(
            invoice_id='123456789',
            amount=100,
            fee=500
        )

        self.assertEqual(result['error'], 'Transfer amount is zero or negative')
        mock_create_transfer.assert_not_called()

    def test_process_invoice_credit_not_found(self):
        with self.assertRaises(Invoice.DoesNotExist):
            process_invoice_credit(
                invoice_id='nonexistent',
                amount=10000,
                fee=500
            )

    @patch('invoices.tasks.create_transfer')
    def test_process_invoice_credit_updates_invoice_status(self, mock_create_transfer):
        mock_transfer = MagicMock()
        mock_transfer.id = '987654321'
        mock_create_transfer.return_value = mock_transfer

        self.assertEqual(self.invoice.status, Invoice.Status.CREATED)

        process_invoice_credit(
            invoice_id='123456789',
            amount=10000,
            fee=100
        )

        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.status, Invoice.Status.PAID)

    @patch('invoices.tasks.create_transfer')
    def test_process_invoice_credit_stores_fee(self, mock_create_transfer):
        mock_transfer = MagicMock()
        mock_transfer.id = '987654321'
        mock_create_transfer.return_value = mock_transfer

        process_invoice_credit(
            invoice_id='123456789',
            amount=10000,
            fee=750
        )

        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.fee, 750)

    @patch('invoices.tasks.create_transfer')
    def test_process_invoice_credit_transfer_amount_calculation(self, mock_create_transfer):
        mock_transfer = MagicMock()
        mock_transfer.id = '987654321'
        mock_create_transfer.return_value = mock_transfer

        result = process_invoice_credit(
            invoice_id='123456789',
            amount=10000,
            fee=350
        )

        self.assertEqual(result['amount'], 9650)
        transfer = Transfer.objects.first()
        self.assertEqual(transfer.amount, 9650)

    @patch('invoices.tasks.create_transfer')
    def test_process_invoice_credit_creates_transfer_record(self, mock_create_transfer):
        mock_transfer = MagicMock()
        mock_transfer.id = 'transfer-abc'
        mock_create_transfer.return_value = mock_transfer

        process_invoice_credit(
            invoice_id='123456789',
            amount=10000,
            fee=200
        )

        transfer = Transfer.objects.first()
        self.assertEqual(transfer.starkbank_id, 'transfer-abc')
        self.assertEqual(transfer.invoice, self.invoice)
        self.assertEqual(transfer.status, Transfer.Status.PROCESSING)

    @patch('invoices.tasks.create_transfer')
    def test_process_invoice_credit_with_zero_fee(self, mock_create_transfer):
        mock_transfer = MagicMock()
        mock_transfer.id = '987654321'
        mock_create_transfer.return_value = mock_transfer

        result = process_invoice_credit(
            invoice_id='123456789',
            amount=10000,
            fee=0
        )

        self.assertEqual(result['amount'], 10000)
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.fee, 0)

    @patch('invoices.tasks.create_transfer')
    def test_process_invoice_credit_api_error_raises_exception(self, mock_create_transfer):
        mock_create_transfer.side_effect = Exception('Transfer API Error')

        with self.assertRaises(Exception) as context:
            process_invoice_credit(
                invoice_id='123456789',
                amount=10000,
                fee=500
            )

        self.assertIn('Transfer API Error', str(context.exception))
        self.assertEqual(Transfer.objects.count(), 0)

    @patch('invoices.tasks.create_transfer')
    def test_process_invoice_credit_invoice_not_updated_on_transfer_error(self, mock_create_transfer):
        """Invoice should NOT be updated if transfer creation fails (atomic transaction)."""
        mock_create_transfer.side_effect = Exception('Transfer API Error')

        with self.assertRaises(Exception):
            process_invoice_credit(
                invoice_id='123456789',
                amount=10000,
                fee=500
            )

        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.status, Invoice.Status.CREATED)
        self.assertIsNone(self.invoice.fee)


class ProcessInvoiceCreditEdgeCasesTest(TestCase):

    @patch('invoices.tasks.create_transfer')
    def test_process_large_amount(self, mock_create_transfer):
        invoice = Invoice.objects.create(
            starkbank_id='large-invoice',
            amount=999999999,
            name='Rich User',
            tax_id='12345678901'
        )

        mock_transfer = MagicMock()
        mock_transfer.id = 'large-transfer'
        mock_create_transfer.return_value = mock_transfer

        result = process_invoice_credit(
            invoice_id='large-invoice',
            amount=999999999,
            fee=1000
        )

        self.assertEqual(result['amount'], 999998999)

    @patch('invoices.tasks.create_transfer')
    def test_process_minimum_amount(self, mock_create_transfer):
        invoice = Invoice.objects.create(
            starkbank_id='min-invoice',
            amount=2,
            name='Min User',
            tax_id='12345678901'
        )

        mock_transfer = MagicMock()
        mock_transfer.id = 'min-transfer'
        mock_create_transfer.return_value = mock_transfer

        result = process_invoice_credit(
            invoice_id='min-invoice',
            amount=2,
            fee=1
        )

        self.assertEqual(result['amount'], 1)

    @patch('invoices.tasks.create_transfer')
    def test_process_fee_equals_amount_minus_one(self, mock_create_transfer):
        invoice = Invoice.objects.create(
            starkbank_id='edge-invoice',
            amount=1000,
            name='Edge User',
            tax_id='12345678901'
        )

        mock_transfer = MagicMock()
        mock_transfer.id = 'edge-transfer'
        mock_create_transfer.return_value = mock_transfer

        result = process_invoice_credit(
            invoice_id='edge-invoice',
            amount=1000,
            fee=999
        )

        self.assertEqual(result['amount'], 1)


class IssueInvoicesCampaignTest(TestCase):
    """Tests for invoice issuance with campaign logic."""

    def test_issue_invoices_no_active_campaign(self):
        """Task should skip when no active campaign exists."""
        result = issue_invoices()

        self.assertTrue(result['skipped'])
        self.assertEqual(result['reason'], 'no_active_campaign')
        self.assertEqual(Invoice.objects.count(), 0)

    def test_issue_invoices_inactive_campaign(self):
        """Task should skip when campaign is inactive."""
        InvoiceCampaign.objects.create(is_active=False)

        result = issue_invoices()

        self.assertTrue(result['skipped'])
        self.assertEqual(result['reason'], 'no_active_campaign')

    @patch('invoices.tasks.create_invoices')
    def test_issue_invoices_max_executions_reached(self, mock_create_invoices):
        """Task should deactivate campaign when max executions reached."""
        campaign = InvoiceCampaign.objects.create(
            max_executions=3,
            execution_count=3,
            is_active=True
        )

        result = issue_invoices()

        campaign.refresh_from_db()
        self.assertTrue(result['skipped'])
        self.assertEqual(result['reason'], 'max_executions_reached')
        self.assertFalse(campaign.is_active)
        mock_create_invoices.assert_not_called()

    @patch('invoices.tasks.create_invoices')
    def test_issue_invoices_increments_counter(self, mock_create_invoices):
        """Task should increment execution counter after success."""
        campaign = InvoiceCampaign.objects.create(
            max_executions=8,
            execution_count=0,
            is_active=True
        )
        mock_create_invoices.return_value = []

        with patch('invoices.tasks.random.randint', return_value=8):
            issue_invoices()

        campaign.refresh_from_db()
        self.assertEqual(campaign.execution_count, 1)

    @patch('invoices.tasks.create_invoices')
    def test_issue_invoices_deactivates_on_last_execution(self, mock_create_invoices):
        """Campaign should deactivate after last execution."""
        campaign = InvoiceCampaign.objects.create(
            max_executions=8,
            execution_count=7,
            is_active=True
        )
        mock_create_invoices.return_value = []

        with patch('invoices.tasks.random.randint', return_value=8):
            issue_invoices()

        campaign.refresh_from_db()
        self.assertEqual(campaign.execution_count, 8)
        self.assertFalse(campaign.is_active)

    @patch('invoices.tasks.create_invoices')
    def test_issue_invoices_uses_most_recent_active_campaign(self, mock_create_invoices):
        """Task should use the most recent active campaign (ordered by -started_at)."""
        InvoiceCampaign.objects.create(is_active=False)
        InvoiceCampaign.objects.create(is_active=True)
        most_recent_campaign = InvoiceCampaign.objects.create(is_active=True)

        mock_create_invoices.return_value = []

        with patch('invoices.tasks.random.randint', return_value=8):
            result = issue_invoices()

        self.assertEqual(result['campaign_id'], most_recent_campaign.id)

    @patch('invoices.tasks.create_invoices')
    def test_issue_invoices_full_campaign_cycle(self, mock_create_invoices):
        """Test complete campaign cycle of 8 executions."""
        campaign = InvoiceCampaign.objects.create(
            max_executions=8,
            is_active=True
        )
        mock_create_invoices.return_value = []

        for i in range(8):
            with patch('invoices.tasks.random.randint', return_value=8):
                result = issue_invoices()
            self.assertEqual(result['execution'], i + 1)

        campaign.refresh_from_db()
        self.assertFalse(campaign.is_active)
        self.assertEqual(campaign.execution_count, 8)

        result = issue_invoices()
        self.assertTrue(result['skipped'])