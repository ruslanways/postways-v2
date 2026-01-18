import logging
import traceback

from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import render
from django.utils import timezone

logger = logging.getLogger(__name__)


class UserLastRequestMiddleware:
    """
    Updates the last_request timestamp for authenticated users.
    Throttled to avoid database writes on every request.
    """

    # Only update if last request was more than 60 seconds ago
    UPDATE_INTERVAL_SECONDS = 60

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        # Update last_request after response (non-blocking for user)
        if request.user.is_authenticated:
            self._update_last_request(request.user)

        return response

    def _update_last_request(self, user):
        """Only update if enough time has passed since last update."""
        now = timezone.now()
        if user.last_request is None:
            should_update = True
        else:
            elapsed = (now - user.last_request).total_seconds()
            should_update = elapsed > self.UPDATE_INTERVAL_SECONDS

        if should_update:
            # Use update() to handle case where user was deleted during request
            # Use _meta.model to get the actual model class (works with SimpleLazyObject)
            user._meta.model.objects.filter(pk=user.pk).update(last_request=now)


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
