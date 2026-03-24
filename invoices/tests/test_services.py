from unittest.mock import patch, MagicMock
from django.test import TestCase, override_settings
from faker import Faker


class FakerIntegrationTest(TestCase):

    def setUp(self):
        self.fake = Faker('pt_BR')

    def test_faker_generates_valid_cpf(self):
        cpf = self.fake.cpf()
        # CPF com pontuação tem 14 caracteres (XXX.XXX.XXX-XX)
        self.assertEqual(len(cpf), 14)

    def test_faker_generates_name(self):
        name = self.fake.name()
        self.assertTrue(len(name) > 0)

    def test_faker_generates_different_names(self):
        names = {self.fake.name() for _ in range(50)}
        self.assertGreater(len(names), 1)

    def test_faker_generates_different_cpfs(self):
        cpfs = {self.fake.cpf() for _ in range(50)}
        self.assertGreater(len(cpfs), 1)


class CreateInvoicesTest(TestCase):
    """Tests for the create_invoices service function."""

    @patch('invoices.services.starkbank.invoice.create')
    @patch('invoices.services.get_starkbank_project')
    def test_create_invoices_calls_starkbank_api(self, mock_get_project, mock_create):
        from invoices.services import create_invoices

        mock_create.return_value = []
        create_invoices(count=5)

        mock_get_project.assert_called_once()
        mock_create.assert_called_once()

    @patch('invoices.services.starkbank.invoice.create')
    @patch('invoices.services.get_starkbank_project')
    def test_create_invoices_creates_correct_count(self, mock_get_project, mock_create):
        from invoices.services import create_invoices

        mock_create.return_value = []
        create_invoices(count=10)

        invoices_arg = mock_create.call_args[0][0]
        self.assertEqual(len(invoices_arg), 10)

    @patch('invoices.services.starkbank.Invoice')
    @patch('invoices.services.starkbank.invoice.create')
    @patch('invoices.services.get_starkbank_project')
    def test_create_invoices_includes_tags(self, mock_get_project, mock_create, mock_invoice_class):
        from invoices.services import create_invoices

        mock_create.return_value = []
        create_invoices(count=1)

        call_kwargs = mock_invoice_class.call_args[1]
        self.assertIn('tags', call_kwargs)
        self.assertIn('auto-generated', call_kwargs['tags'])
        self.assertIn('starkbank-challenge', call_kwargs['tags'])

    @patch('invoices.services.starkbank.Invoice')
    @patch('invoices.services.starkbank.invoice.create')
    @patch('invoices.services.get_starkbank_project')
    def test_create_invoices_includes_campaign_tag(self, mock_get_project, mock_create, mock_invoice_class):
        from invoices.services import create_invoices

        mock_create.return_value = []
        create_invoices(count=1, campaign_id=42)

        call_kwargs = mock_invoice_class.call_args[1]
        self.assertIn('campaign-42', call_kwargs['tags'])

    @patch('invoices.services.starkbank.Invoice')
    @patch('invoices.services.starkbank.invoice.create')
    @patch('invoices.services.get_starkbank_project')
    def test_create_invoices_without_campaign_id(self, mock_get_project, mock_create, mock_invoice_class):
        from invoices.services import create_invoices

        mock_create.return_value = []
        create_invoices(count=1)

        call_kwargs = mock_invoice_class.call_args[1]
        campaign_tags = [t for t in call_kwargs['tags'] if t.startswith('campaign-')]
        self.assertEqual(len(campaign_tags), 0)

    @patch('invoices.services.starkbank.Invoice')
    @patch('invoices.services.starkbank.invoice.create')
    @patch('invoices.services.get_starkbank_project')
    def test_create_invoices_includes_descriptions(self, mock_get_project, mock_create, mock_invoice_class):
        from invoices.services import create_invoices

        mock_create.return_value = []
        create_invoices(count=1)

        call_kwargs = mock_invoice_class.call_args[1]
        self.assertIn('descriptions', call_kwargs)
        descriptions = call_kwargs['descriptions']
        self.assertEqual(len(descriptions), 2)

        keys = [d['key'] for d in descriptions]
        self.assertIn('Product', keys)
        self.assertIn('Origin', keys)

    @patch('invoices.services.starkbank.Invoice')
    @patch('invoices.services.starkbank.invoice.create')
    @patch('invoices.services.get_starkbank_project')
    @override_settings(INVOICE_EXPIRATION_HOURS=12)
    def test_create_invoices_expiration_from_settings(self, mock_get_project, mock_create, mock_invoice_class):
        from invoices.services import create_invoices

        mock_create.return_value = []
        create_invoices(count=1)

        call_kwargs = mock_invoice_class.call_args[1]
        self.assertEqual(call_kwargs['expiration'], 12 * 3600)

    @patch('invoices.services.starkbank.Invoice')
    @patch('invoices.services.starkbank.invoice.create')
    @patch('invoices.services.get_starkbank_project')
    @override_settings(INVOICE_EXPIRATION_HOURS=24)
    def test_create_invoices_expiration_24_hours(self, mock_get_project, mock_create, mock_invoice_class):
        from invoices.services import create_invoices

        mock_create.return_value = []
        create_invoices(count=1)

        call_kwargs = mock_invoice_class.call_args[1]
        self.assertEqual(call_kwargs['expiration'], 24 * 3600)

    @patch('invoices.services.starkbank.Invoice')
    @patch('invoices.services.starkbank.invoice.create')
    @patch('invoices.services.get_starkbank_project')
    def test_create_invoices_amount_in_valid_range(self, mock_get_project, mock_create, mock_invoice_class):
        from invoices.services import create_invoices

        mock_create.return_value = []
        create_invoices(count=1)

        call_kwargs = mock_invoice_class.call_args[1]
        amount = call_kwargs['amount']
        self.assertGreaterEqual(amount, 1000)
        self.assertLessEqual(amount, 100000)

    @patch('invoices.services.starkbank.Invoice')
    @patch('invoices.services.starkbank.invoice.create')
    @patch('invoices.services.get_starkbank_project')
    def test_create_invoices_has_valid_name(self, mock_get_project, mock_create, mock_invoice_class):
        from invoices.services import create_invoices

        mock_create.return_value = []
        create_invoices(count=1)

        call_kwargs = mock_invoice_class.call_args[1]
        self.assertIn('name', call_kwargs)
        self.assertTrue(len(call_kwargs['name']) > 0)

    @patch('invoices.services.starkbank.Invoice')
    @patch('invoices.services.starkbank.invoice.create')
    @patch('invoices.services.get_starkbank_project')
    def test_create_invoices_has_valid_tax_id(self, mock_get_project, mock_create, mock_invoice_class):
        from invoices.services import create_invoices

        mock_create.return_value = []
        create_invoices(count=1)

        call_kwargs = mock_invoice_class.call_args[1]
        self.assertIn('tax_id', call_kwargs)
        # CPF format: XXX.XXX.XXX-XX (14 chars)
        self.assertEqual(len(call_kwargs['tax_id']), 14)

    @patch('invoices.services.starkbank.Invoice')
    @patch('invoices.services.starkbank.invoice.create')
    @patch('invoices.services.get_starkbank_project')
    def test_create_invoices_description_includes_invoice_number(self, mock_get_project, mock_create, mock_invoice_class):
        from invoices.services import create_invoices

        mock_create.return_value = []
        create_invoices(count=5)

        # Check last invoice created (5th)
        call_kwargs = mock_invoice_class.call_args[1]
        descriptions = call_kwargs['descriptions']
        product_desc = next(d for d in descriptions if d['key'] == 'Product')
        self.assertIn('5 of 5', product_desc['value'])