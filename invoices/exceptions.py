from rest_framework.exceptions import APIException
from rest_framework import status


class MissingSignatureError(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = 'Missing signature'
    default_code = 'missing_signature'


class InvalidSignatureError(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = 'Invalid signature'
    default_code = 'invalid_signature'


class WebhookProcessingError(APIException):
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    default_detail = 'Error processing webhook'
    default_code = 'webhook_processing_error'


class IPNotAllowedError(APIException):
    status_code = status.HTTP_403_FORBIDDEN
    default_detail = 'IP address not allowed'
    default_code = 'ip_not_allowed'