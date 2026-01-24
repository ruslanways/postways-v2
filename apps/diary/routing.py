"""
WebSocket URL routing for the diary application.

This module defines the WebSocket URL patterns that connect clients
to Django Channels consumers for real-time updates.
"""

from django.urls import path

from . import consumers

websocket_urlpatterns = [
    # WebSocket endpoint for real-time like count updates
    # Clients connect to: ws://host/ws/socket-server/
    path("ws/socket-server/", consumers.LikeConsumer.as_asgi()),
]
