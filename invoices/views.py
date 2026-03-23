import logging
import starkbank
from rest_framework import viewsets
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from .models import Invoice, Transfer, WebhookEvent
from .serializers import InvoiceSerializer, TransferSerializer
from .services import get_starkbank_project
from .tasks import process_invoice_credit
from .exceptions import MissingSignatureError, InvalidSignatureError, WebhookProcessingError
from .authentication import APIKeyAuthentication

logger = logging.getLogger(__name__)


class InvoiceViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for listing and retrieving invoices."""
    queryset = Invoice.objects.all()
    serializer_class = InvoiceSerializer
    authentication_classes = [APIKeyAuthentication]
    permission_classes = [IsAuthenticated]


class TransferViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for listing and retrieving transfers."""
    queryset = Transfer.objects.all()
    serializer_class = TransferSerializer
    authentication_classes = [APIKeyAuthentication]
    permission_classes = [IsAuthenticated]


class WebhookCallbackView(APIView):
    """Endpoint to receive webhook callbacks from Stark Bank."""
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        try:
            event = self._parse_event(request)
            self._process_event(event)
            return Response({'status': 'ok'})
        except (MissingSignatureError, InvalidSignatureError):
            raise
        except Exception as e:
            logger.error(f'Error processing webhook: {e}')
            raise WebhookProcessingError()

    @staticmethod
    def _parse_event(request):
        get_starkbank_project()

        signature = request.headers.get('Digital-Signature')
        if not signature:
            logger.warning('Webhook received without signature')
            raise MissingSignatureError()

        raw_body = request.body.decode('utf-8')

        try:
            return starkbank.event.parse(content=raw_body, signature=signature)
        except starkbank.error.InvalidSignatureError:
            logger.warning('Invalid webhook signature')
            raise InvalidSignatureError()

    def _process_event(self, event):
        if WebhookEvent.objects.filter(event_id=event.id).exists():
            logger.info(f'Event {event.id} already processed')
            return

        WebhookEvent.objects.create(
            event_id=event.id,
            event_type=event.subscription,
            payload={'log': str(event.log)},
            processed=False
        )

        if event.subscription == 'invoice' and hasattr(event.log, 'invoice'):
            self._handle_invoice_event(event)

    @staticmethod
    def _handle_invoice_event(event):
        invoice_log = event.log
        invoice = invoice_log.invoice

        if invoice_log.type == 'credited':
            logger.info(f'Invoice {invoice.id} credited: amount={invoice.amount}, fee={invoice.fee}')

            process_invoice_credit.delay(
                invoice_id=str(invoice.id),
                amount=invoice.amount,
                fee=invoice.fee or 0
            )

            WebhookEvent.objects.filter(event_id=event.id).update(processed=True)