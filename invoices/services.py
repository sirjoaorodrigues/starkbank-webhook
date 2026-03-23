import random
import starkbank
from django.conf import settings
from faker import Faker
from rest_framework import authentication, exceptions, permissions
from drf_spectacular.extensions import OpenApiAuthenticationExtension

fake = Faker('pt_BR')


# =============================================================================
# Stark Bank Services
# =============================================================================

def get_starkbank_project():
    """Initialize and return Stark Bank project."""
    with open(settings.STARKBANK_PRIVATE_KEY_PATH, 'r') as f:
        private_key = f.read()

    project = starkbank.Project(
        environment=settings.STARKBANK_ENVIRONMENT,
        id=settings.STARKBANK_PROJECT_ID,
        private_key=private_key
    )
    starkbank.user = project
    return project


def create_invoices(count: int) -> list:
    """Create random invoices in Stark Bank."""
    get_starkbank_project()

    invoices = []
    for _ in range(count):
        invoice = starkbank.Invoice(
            amount=random.randint(1000, 100000),
            name=fake.name(),
            tax_id=fake.cpf(),
            due=None,
            expiration=3600 * 24 * 2,
        )
        invoices.append(invoice)

    return starkbank.invoice.create(invoices)


def create_transfer(amount: int, invoice_starkbank_id: str) -> starkbank.Transfer:
    """Create a transfer to the destination account."""
    get_starkbank_project()

    transfer = starkbank.Transfer(
        amount=amount,
        bank_code=settings.TRANSFER_BANK_CODE,
        branch_code=settings.TRANSFER_BRANCH_CODE,
        account_number=settings.TRANSFER_ACCOUNT_NUMBER,
        account_type=settings.TRANSFER_ACCOUNT_TYPE,
        name=settings.TRANSFER_ACCOUNT_NAME,
        tax_id=settings.TRANSFER_TAX_ID,
        external_id=f'invoice-{invoice_starkbank_id}',
    )

    transfers = starkbank.transfer.create([transfer])
    return transfers[0]


# =============================================================================
# API Key Authentication
# =============================================================================

class APIKeyUser:
    """Fake user for API Key authentication."""
    is_authenticated = True


class APIKeyAuthentication(authentication.BaseAuthentication):
    """Custom authentication using X-API-Key header."""

    def authenticate(self, request):
        api_key = request.headers.get('X-API-Key')

        if not api_key:
            return None

        if api_key != settings.API_KEY:
            raise exceptions.AuthenticationFailed('Invalid API Key')

        return (APIKeyUser(), None)


class APIKeyAuthenticationScheme(OpenApiAuthenticationExtension):
    """OpenAPI schema extension for API Key authentication."""
    target_class = 'invoices.services.APIKeyAuthentication'
    name = 'ApiKeyAuth'

    def get_security_definition(self, auto_schema):
        return {
            'type': 'apiKey',
            'in': 'header',
            'name': 'X-API-Key',
        }


class HasValidAPIKey(permissions.BasePermission):
    """Permission that checks if request was authenticated via API Key."""

    def has_permission(self, request, view):
        return isinstance(request.user, APIKeyUser)