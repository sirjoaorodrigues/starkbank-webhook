from unittest.mock import patch, MagicMock
from django.conf import settings
from rest_framework.test import APITestCase
from rest_framework import status
from invoices.models import Invoice, Transfer, WebhookEvent


class InvoiceViewSetTest(APITestCase):

    def setUp(self):
        self.invoice = Invoice.objects.create(
            starkbank_id='123456789',
            amount=10000,
            name='Test User',
            tax_id='12345678901',
            status=Invoice.Status.CREATED
        )
        self.api_key = settings.API_KEY

    def test_list_invoices_without_api_key(self):
        response = self.client.get('/api/invoices/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_list_invoices_with_invalid_api_key(self):
        response = self.client.get(
            '/api/invoices/',
            HTTP_X_API_KEY='invalid-key'
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_list_invoices_with_valid_api_key(self):
        response = self.client.get(
            '/api/invoices/',
            HTTP_X_API_KEY=self.api_key
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

    def test_retrieve_invoice_with_valid_api_key(self):
        response = self.client.get(
            f'/api/invoices/{self.invoice.id}/',
            HTTP_X_API_KEY=self.api_key
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['starkbank_id'], '123456789')

    def test_invoices_read_only(self):
        response = self.client.post(
            '/api/invoices/',
            {'name': 'Test'},
            HTTP_X_API_KEY=self.api_key
        )
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_list_invoices_ordered_by_created_at_desc(self):
        Invoice.objects.create(
            starkbank_id='222222222',
            amount=5000,
            name='Second User',
            tax_id='22222222222'
        )
        response = self.client.get(
            '/api/invoices/',
            HTTP_X_API_KEY=self.api_key
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data[0]['starkbank_id'], '222222222')

    def test_retrieve_nonexistent_invoice(self):
        response = self.client.get(
            '/api/invoices/99999/',
            HTTP_X_API_KEY=self.api_key
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class TransferViewSetTest(APITestCase):

    def setUp(self):
        self.invoice = Invoice.objects.create(
            starkbank_id='123456789',
            amount=10000,
            name='Test User',
            tax_id='12345678901'
        )
        self.transfer = Transfer.objects.create(
            starkbank_id='987654321',
            invoice=self.invoice,
            amount=9500,
            status=Transfer.Status.PROCESSING
        )
        self.api_key = settings.API_KEY

    def test_list_transfers_without_api_key(self):
        response = self.client.get('/api/transfers/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_list_transfers_with_valid_api_key(self):
        response = self.client.get(
            '/api/transfers/',
            HTTP_X_API_KEY=self.api_key
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

    def test_retrieve_transfer_with_valid_api_key(self):
        response = self.client.get(
            f'/api/transfers/{self.transfer.id}/',
            HTTP_X_API_KEY=self.api_key
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['starkbank_id'], '987654321')

    def test_transfers_read_only(self):
        response = self.client.post(
            '/api/transfers/',
            {'amount': 1000},
            HTTP_X_API_KEY=self.api_key
        )
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_transfer_contains_invoice_reference(self):
        response = self.client.get(
            f'/api/transfers/{self.transfer.id}/',
            HTTP_X_API_KEY=self.api_key
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('invoice', response.data)
        self.assertEqual(response.data['invoice'], self.invoice.id)


class WebhookCallbackTest(APITestCase):
    """Webhook tests - no API key required (uses Digital-Signature)."""

    @patch('invoices.views.get_starkbank_project')
    def test_webhook_without_signature(self, mock_get_project):
        response = self.client.post(
            '/api/webhook/',
            data={'event': 'test'},
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['detail'], 'Missing signature')

    @patch('invoices.views.get_starkbank_project')
    @patch('invoices.views.starkbank.event.parse')
    def test_webhook_with_invalid_signature(self, mock_parse, mock_get_project):
        import starkbank
        mock_parse.side_effect = starkbank.error.InvalidSignatureError('Invalid signature')

        response = self.client.post(
            '/api/webhook/',
            data={'event': 'test'},
            format='json',
            HTTP_DIGITAL_SIGNATURE='invalid-signature'
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['detail'], 'Invalid signature')

    @patch('invoices.views.get_starkbank_project')
    @patch('invoices.views.starkbank.event.parse')
    def test_webhook_duplicate_event_ignored(self, mock_parse, mock_get_project):
        WebhookEvent.objects.create(
            event_id='event-123',
            event_type='invoice',
            payload={'log': 'test'},
            processed=True
        )

        mock_event = MagicMock()
        mock_event.id = 'event-123'
        mock_parse.return_value = mock_event

        response = self.client.post(
            '/api/webhook/',
            data={'event': 'test'},
            format='json',
            HTTP_DIGITAL_SIGNATURE='valid-signature'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(WebhookEvent.objects.count(), 1)

    @patch('invoices.views.process_invoice_credit')
    @patch('invoices.views.get_starkbank_project')
    @patch('invoices.views.starkbank.event.parse')
    def test_webhook_invoice_credited_triggers_transfer(self, mock_parse, mock_get_project, mock_task):
        mock_invoice = MagicMock()
        mock_invoice.id = '123456789'
        mock_invoice.amount = 10000
        mock_invoice.fee = 500

        mock_log = MagicMock()
        mock_log.type = 'credited'
        mock_log.invoice = mock_invoice

        mock_event = MagicMock()
        mock_event.id = 'event-456'
        mock_event.subscription = 'invoice'
        mock_event.log = mock_log
        mock_parse.return_value = mock_event

        response = self.client.post(
            '/api/webhook/',
            data={'event': 'test'},
            format='json',
            HTTP_DIGITAL_SIGNATURE='valid-signature'
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        mock_task.delay.assert_called_once_with(
            invoice_id='123456789',
            amount=10000,
            fee=500
        )
        self.assertTrue(WebhookEvent.objects.filter(event_id='event-456', processed=True).exists())

    @patch('invoices.views.process_invoice_credit')
    @patch('invoices.views.get_starkbank_project')
    @patch('invoices.views.starkbank.event.parse')
    def test_webhook_invoice_not_credited_does_not_trigger_transfer(self, mock_parse, mock_get_project, mock_task):
        mock_invoice = MagicMock()
        mock_invoice.id = '123456789'

        mock_log = MagicMock()
        mock_log.type = 'created'
        mock_log.invoice = mock_invoice

        mock_event = MagicMock()
        mock_event.id = 'event-789'
        mock_event.subscription = 'invoice'
        mock_event.log = mock_log
        mock_parse.return_value = mock_event

        response = self.client.post(
            '/api/webhook/',
            data={'event': 'test'},
            format='json',
            HTTP_DIGITAL_SIGNATURE='valid-signature'
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        mock_task.delay.assert_not_called()

    @patch('invoices.views.process_invoice_credit')
    @patch('invoices.views.get_starkbank_project')
    @patch('invoices.views.starkbank.event.parse')
    def test_webhook_non_invoice_event_ignored(self, mock_parse, mock_get_project, mock_task):
        mock_event = MagicMock()
        mock_event.id = 'event-999'
        mock_event.subscription = 'transfer'
        mock_event.log = MagicMock()
        mock_parse.return_value = mock_event

        response = self.client.post(
            '/api/webhook/',
            data={'event': 'test'},
            format='json',
            HTTP_DIGITAL_SIGNATURE='valid-signature'
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        mock_task.delay.assert_not_called()

    @patch('invoices.views.process_invoice_credit')
    @patch('invoices.views.get_starkbank_project')
    @patch('invoices.views.starkbank.event.parse')
    def test_webhook_invoice_credited_with_zero_fee(self, mock_parse, mock_get_project, mock_task):
        mock_invoice = MagicMock()
        mock_invoice.id = '123456789'
        mock_invoice.amount = 10000
        mock_invoice.fee = None

        mock_log = MagicMock()
        mock_log.type = 'credited'
        mock_log.invoice = mock_invoice

        mock_event = MagicMock()
        mock_event.id = 'event-000'
        mock_event.subscription = 'invoice'
        mock_event.log = mock_log
        mock_parse.return_value = mock_event

        response = self.client.post(
            '/api/webhook/',
            data={'event': 'test'},
            format='json',
            HTTP_DIGITAL_SIGNATURE='valid-signature'
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        mock_task.delay.assert_called_once_with(
            invoice_id='123456789',
            amount=10000,
            fee=0
        )

    @patch('invoices.views.get_starkbank_project')
    @patch('invoices.views.starkbank.event.parse')
    def test_webhook_creates_event_record(self, mock_parse, mock_get_project):
        mock_event = MagicMock()
        mock_event.id = 'new-event-123'
        mock_event.subscription = 'boleto'
        mock_event.log = MagicMock()
        mock_parse.return_value = mock_event

        response = self.client.post(
            '/api/webhook/',
            data={'event': 'test'},
            format='json',
            HTTP_DIGITAL_SIGNATURE='valid-signature'
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        event = WebhookEvent.objects.get(event_id='new-event-123')
        self.assertEqual(event.event_type, 'boleto')
        self.assertFalse(event.processed)


class WebhookIPWhitelistTest(APITestCase):
    """Tests for webhook IP whitelist functionality."""

    @patch('invoices.views.settings')
    @patch('invoices.views.get_starkbank_project')
    def test_webhook_blocked_ip(self, mock_get_project, mock_settings):
        mock_settings.WEBHOOK_IP_WHITELIST = ['1.2.3.4', '5.6.7.8']

        response = self.client.post(
            '/api/webhook/',
            data={'event': 'test'},
            format='json',
            HTTP_DIGITAL_SIGNATURE='valid-signature',
            REMOTE_ADDR='9.9.9.9'
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.data['detail'], 'IP address not allowed')

    @patch('invoices.views.settings')
    @patch('invoices.views.get_starkbank_project')
    def test_webhook_allowed_ip(self, mock_get_project, mock_settings):
        mock_settings.WEBHOOK_IP_WHITELIST = ['127.0.0.1', '5.6.7.8']

        response = self.client.post(
            '/api/webhook/',
            data={'event': 'test'},
            format='json',
            REMOTE_ADDR='127.0.0.1'
        )

        # Will fail on signature, but IP check passed
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['detail'], 'Missing signature')

    @patch('invoices.views.settings')
    @patch('invoices.views.get_starkbank_project')
    def test_webhook_whitelist_disabled(self, mock_get_project, mock_settings):
        mock_settings.WEBHOOK_IP_WHITELIST = []

        response = self.client.post(
            '/api/webhook/',
            data={'event': 'test'},
            format='json',
            REMOTE_ADDR='9.9.9.9'
        )

        # IP check disabled, will fail on signature
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['detail'], 'Missing signature')

    @patch('invoices.views.settings')
    @patch('invoices.views.get_starkbank_project')
    def test_webhook_whitelist_empty_string(self, mock_get_project, mock_settings):
        mock_settings.WEBHOOK_IP_WHITELIST = ['']

        response = self.client.post(
            '/api/webhook/',
            data={'event': 'test'},
            format='json',
            REMOTE_ADDR='9.9.9.9'
        )

        # IP check disabled for empty string, will fail on signature
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['detail'], 'Missing signature')

    @patch('invoices.views.settings')
    @patch('invoices.views.get_starkbank_project')
    def test_webhook_x_forwarded_for_header(self, mock_get_project, mock_settings):
        mock_settings.WEBHOOK_IP_WHITELIST = ['10.0.0.1']

        response = self.client.post(
            '/api/webhook/',
            data={'event': 'test'},
            format='json',
            HTTP_X_FORWARDED_FOR='10.0.0.1, 192.168.1.1',
            REMOTE_ADDR='127.0.0.1'
        )

        # X-Forwarded-For takes precedence, IP check passed
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['detail'], 'Missing signature')

    @patch('invoices.views.settings')
    @patch('invoices.views.get_starkbank_project')
    def test_webhook_x_forwarded_for_blocked(self, mock_get_project, mock_settings):
        mock_settings.WEBHOOK_IP_WHITELIST = ['10.0.0.1']

        response = self.client.post(
            '/api/webhook/',
            data={'event': 'test'},
            format='json',
            HTTP_X_FORWARDED_FOR='9.9.9.9, 192.168.1.1',
            REMOTE_ADDR='10.0.0.1'
        )

        # X-Forwarded-For takes precedence, IP blocked
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.data['detail'], 'IP address not allowed')