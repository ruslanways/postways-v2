import logging
import traceback

from django.conf import settings
from django.core.cache import cache
from django.core.exceptions import PermissionDenied
from django.http import Http404, JsonResponse
from django.shortcuts import render
from django.utils import timezone

logger = logging.getLogger(__name__)


class UserLastRequestMiddleware:
    """
    Updates the last_request timestamp for authenticated users.
    Uses Redis cache to throttle DB writes (at most once per UPDATE_INTERVAL_SECONDS).
    """

    UPDATE_INTERVAL_SECONDS = 60

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        if request.user.is_authenticated:
            self._update_last_request(request.user)

        return response

    def _update_last_request(self, user):
        """
        Update last_request only if cache key is missing (expired or first visit).
        Cache acts as a "cooldown timer" - while key exists, skip DB write.
        """
        cache_key = f"user_last_request:{user.pk}"

        # If key exists in cache, we updated recently - skip
        if cache.get(cache_key):
            return

        # Key missing = cooldown expired, time to update DB
        now = timezone.now()
        user._meta.model.objects.filter(pk=user.pk).update(last_request=now)

        # Set cache key with TTL = interval (key auto-expires, allowing next update)
        cache.set(cache_key, True, timeout=self.UPDATE_INTERVAL_SECONDS)


class UncaughtExceptionMiddleware:
    """
    Catches unhandled exceptions, logs them with full traceback,
    and returns user-friendly error responses.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

    def process_exception(self, request, exception):
        # Let Django handle its built-in HTTP exceptions (403, 404, etc.)
        # These should be processed by their respective handlers
        if isinstance(exception, (PermissionDenied, Http404)):
            return None

        # Only catches truly unexpected exceptions
        # Logs the full exception with traceback for debugging
        logger.error(
            "Uncaught exception: %s | User: %s | Path: %s\n%s",
            type(exception).__name__,
            request.user,
            request.get_full_path(),
            traceback.format_exc(),
        )

        # Return appropriate response
        if request.path.startswith("/api/"):
            return self._api_error_response(exception)
        return render(request, "500.html", status=500)

    def _api_error_response(self, exception):
        """Return JSON error - hide details in production."""
        if settings.DEBUG:
            # Show details only in development
            return JsonResponse(
                {
                    "error": type(exception).__name__,
                    "detail": str(exception),
                },
                status=500,
            )
        # Generic message in production
        return JsonResponse(
            {"error": "Internal server error"},
            status=500,
        )
