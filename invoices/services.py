import random
import starkbank
from django.conf import settings
from faker import Faker

fake = Faker('pt_BR')


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