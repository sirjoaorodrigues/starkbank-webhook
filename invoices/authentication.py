from django.conf import settings
from rest_framework import authentication, exceptions, permissions


class APIKeyUser:
    """Fake user for API Key authentication."""
    is_authenticated = True


class APIKeyAuthentication(authentication.BaseAuthentication):
    """
    Custom authentication using X-API-Key header.
    """

    def authenticate(self, request):
        api_key = request.headers.get('X-API-Key')

        if not api_key:
            return None

        if api_key != settings.API_KEY:
            raise exceptions.AuthenticationFailed('Invalid API Key')

        return (APIKeyUser(), None)


class HasValidAPIKey(permissions.BasePermission):
    """
    Permission that checks if request was authenticated via API Key.
    """

    def has_permission(self, request, view):
        return isinstance(request.user, APIKeyUser)