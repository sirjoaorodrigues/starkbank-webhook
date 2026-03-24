import random
import logging
from celery import shared_task
from django.conf import settings
from django.db import transaction
from .models import Invoice, Transfer, InvoiceCampaign
from .services import create_invoices, create_transfer

logger = logging.getLogger(__name__)


@shared_task(
    autoretry_for=(Exception,),
    retry_backoff=settings.CELERY_RETRY_BACKOFF,
    retry_backoff_max=settings.CELERY_RETRY_BACKOFF_MAX,
    retry_kwargs={'max_retries': settings.CELERY_RETRY_MAX},
    retry_jitter=True,
)
def issue_invoices():
    """Task to issue 8-12 random invoices."""
    campaign = InvoiceCampaign.objects.filter(is_active=True).first()

    if not campaign:
        logger.info('No active campaign found, skipping invoice creation')
        return {'skipped': True, 'reason': 'no_active_campaign'}

    if campaign.execution_count >= campaign.max_executions:
        campaign.is_active = False
        campaign.save()
        logger.info(
            'Campaign completed - max executions reached',
            extra={'campaign_id': campaign.id, 'max_executions': campaign.max_executions}
        )
        return {'skipped': True, 'reason': 'max_executions_reached'}

    count = random.randint(8, 12)
    execution_number = campaign.execution_count + 1
    logger.info(
        'Starting invoice creation batch',
        extra={
            'campaign_id': campaign.id,
            'invoice_count': count,
            'execution': execution_number,
            'max_executions': campaign.max_executions
        }
    )

    try:
        starkbank_invoices = create_invoices(count, campaign_id=campaign.id)

        for sb_invoice in starkbank_invoices:
            Invoice.objects.create(
                starkbank_id=sb_invoice.id,
                amount=sb_invoice.amount,
                name=sb_invoice.name,
                tax_id=sb_invoice.tax_id,
                status=Invoice.Status.CREATED
            )
            logger.info(
                'Invoice created',
                extra={
                    'invoice_id': sb_invoice.id,
                    'amount': sb_invoice.amount,
                    'campaign_id': campaign.id
                }
            )

        campaign.increment_and_check()
        logger.info(
            'Invoice batch completed',
            extra={
                'campaign_id': campaign.id,
                'created_count': count,
                'execution': campaign.execution_count,
                'max_executions': campaign.max_executions,
                'campaign_active': campaign.is_active
            }
        )
        return {'created': count, 'campaign_id': campaign.id, 'execution': campaign.execution_count}

    except Exception as e:
        logger.error(
            'Error creating invoices',
            extra={'campaign_id': campaign.id, 'error': str(e)},
            exc_info=True
        )
        raise


@shared_task(
    autoretry_for=(Exception,),
    retry_backoff=settings.CELERY_RETRY_BACKOFF,
    retry_backoff_max=settings.CELERY_RETRY_BACKOFF_MAX,
    retry_kwargs={'max_retries': settings.CELERY_RETRY_MAX},
    retry_jitter=True,
)
def process_invoice_credit(invoice_id: str, amount: int, fee: int):
    """Process a paid invoice and create a transfer."""
    log_context = {'invoice_id': invoice_id, 'amount': amount, 'fee': fee}
    logger.info('Processing invoice credit', extra=log_context)

    try:
        invoice = Invoice.objects.get(starkbank_id=invoice_id)

        transfer_amount = amount - fee
        if transfer_amount <= 0:
            logger.warning(
                'Transfer amount is zero or negative',
                extra={**log_context, 'transfer_amount': transfer_amount}
            )
            return {'error': 'Transfer amount is zero or negative'}

        sb_transfer = create_transfer(transfer_amount, invoice_id)

        with transaction.atomic():
            invoice.status = Invoice.Status.PAID
            invoice.fee = fee
            invoice.save()

            Transfer.objects.create(
                starkbank_id=sb_transfer.id,
                invoice=invoice,
                amount=transfer_amount,
                status=Transfer.Status.PROCESSING
            )

        logger.info(
            'Transfer created successfully',
            extra={
                'invoice_id': invoice_id,
                'transfer_id': sb_transfer.id,
                'transfer_amount': transfer_amount,
                'fee': fee
            }
        )
        return {'transfer_id': sb_transfer.id, 'amount': transfer_amount}

    except Invoice.DoesNotExist:
        logger.error('Invoice not found in database', extra=log_context)
        raise
    except Exception as e:
        logger.error(
            'Error processing invoice credit',
            extra={**log_context, 'error': str(e)},
            exc_info=True
        )
        raise