import logging
import starkbank
from django.conf import settings
from rest_framework import viewsets
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiParameter
from drf_spectacular.types import OpenApiTypes
from .models import Invoice, Transfer, WebhookEvent
from .serializers import InvoiceSerializer, TransferSerializer
from .services import get_starkbank_project, APIKeyAuthentication, HasValidAPIKey
from .tasks import process_invoice_credit
from .exceptions import MissingSignatureError, InvalidSignatureError, WebhookProcessingError, IPNotAllowedError

logger = logging.getLogger(__name__)

API_KEY_HEADER = OpenApiParameter(
    name='X-API-Key',
    type=OpenApiTypes.STR,
    location=OpenApiParameter.HEADER,
    required=True,
    description='API Key for authentication'
)


@extend_schema_view(
    list=extend_schema(parameters=[API_KEY_HEADER]),
    retrieve=extend_schema(parameters=[API_KEY_HEADER]),
)
class APIKeyProtectedViewSet(viewsets.ReadOnlyModelViewSet):
    """Base ViewSet with API Key authentication."""
    authentication_classes = [APIKeyAuthentication]
    permission_classes = [HasValidAPIKey]


class InvoiceViewSet(APIKeyProtectedViewSet):
    """ViewSet for listing and retrieving invoices."""
    queryset = Invoice.objects.all()
    serializer_class = InvoiceSerializer


class TransferViewSet(APIKeyProtectedViewSet):
    """ViewSet for listing and retrieving transfers."""
    queryset = Transfer.objects.all()
    serializer_class = TransferSerializer


class WebhookCallbackView(APIView):
    """Endpoint to receive webhook callbacks from Stark Bank."""
    authentication_classes = []
    permission_classes = []
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'webhook'

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name='Digital-Signature',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.HEADER,
                required=True,
                description='Stark Bank digital signature'
            )
        ],
        request=OpenApiTypes.OBJECT,
        responses={200: OpenApiTypes.OBJECT},
    )
    def post(self, request):
        try:
            self._validate_ip(request)
            event = self._parse_event(request)
            self._process_event(event)
            return Response({'status': 'ok'})
        except (MissingSignatureError, InvalidSignatureError, IPNotAllowedError):
            raise
        except Exception as e:
            logger.error(f'Error processing webhook: {e}')
            raise WebhookProcessingError()

    @staticmethod
    def _get_client_ip(request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR')

    def _validate_ip(self, request):
        whitelist = settings.WEBHOOK_IP_WHITELIST
        if not whitelist or whitelist == ['']:
            return

        client_ip = self._get_client_ip(request)
        if client_ip not in whitelist:
            logger.warning(f'Webhook request from non-whitelisted IP: {client_ip}')
            raise IPNotAllowedError()

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