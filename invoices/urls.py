from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import InvoiceViewSet, TransferViewSet, WebhookCallbackView

router = DefaultRouter()
router.register(r'invoices', InvoiceViewSet)
router.register(r'transfers', TransferViewSet)

urlpatterns = [
    path('', include(router.urls)),
    path('webhook', WebhookCallbackView.as_view(), name='webhook-callback'),
]