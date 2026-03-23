import random
import logging
from celery import shared_task
from .models import Invoice, Transfer
from .services import create_invoices, create_transfer

logger = logging.getLogger(__name__)


@shared_task
def issue_invoices():
    """Task to issue 8-12 random invoices."""
    count = random.randint(8, 12)
    logger.info(f'Creating {count} invoices...')

    try:
        starkbank_invoices = create_invoices(count)

        for sb_invoice in starkbank_invoices:
            Invoice.objects.create(
                starkbank_id=sb_invoice.id,
                amount=sb_invoice.amount,
                name=sb_invoice.name,
                tax_id=sb_invoice.tax_id,
                status=Invoice.Status.CREATED
            )
            logger.info(f'Invoice {sb_invoice.id} created for {sb_invoice.name}')

        logger.info(f'Successfully created {count} invoices')
        return {'created': count}

    except Exception as e:
        logger.error(f'Error creating invoices: {e}')
        raise


@shared_task
def process_invoice_credit(invoice_id: str, amount: int, fee: int):
    """Process a paid invoice and create a transfer."""
    logger.info(f'Processing invoice credit: {invoice_id}, amount: {amount}, fee: {fee}')

    try:
        invoice = Invoice.objects.get(starkbank_id=invoice_id)
        invoice.status = Invoice.Status.PAID
        invoice.fee = fee
        invoice.save()

        transfer_amount = amount - fee
        if transfer_amount <= 0:
            logger.warning(f'Transfer amount is zero or negative for invoice {invoice_id}')
            return {'error': 'Transfer amount is zero or negative'}

        sb_transfer = create_transfer(transfer_amount, invoice_id)

        Transfer.objects.create(
            starkbank_id=sb_transfer.id,
            invoice=invoice,
            amount=transfer_amount,
            status=Transfer.Status.PROCESSING
        )

        logger.info(f'Transfer {sb_transfer.id} created for invoice {invoice_id}')
        return {'transfer_id': sb_transfer.id, 'amount': transfer_amount}

    except Invoice.DoesNotExist:
        logger.error(f'Invoice {invoice_id} not found in database')
        raise
    except Exception as e:
        logger.error(f'Error processing invoice credit: {e}')
        raise