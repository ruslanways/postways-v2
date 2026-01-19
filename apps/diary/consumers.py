"""
WebSocket consumers for real-time updates in the diary application.

This module handles WebSocket connections for broadcasting like count updates
to all connected clients when a post is liked or unliked.
"""
import json
import logging
from typing import Any

from channels.generic.websocket import AsyncWebsocketConsumer

logger = logging.getLogger(__name__)


class LikeConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for real-time like count updates.
    
    When a user likes or unlikes a post, this consumer broadcasts the updated
    like count to all connected clients (except the user who triggered the action,
    since they already see the update optimistically in the frontend).
    """
    
    async def connect(self) -> None:
        """
        Handle new WebSocket connection.
        
        Adds the connection to the "likes" group so it can receive broadcasts
        when any post's like count changes.
        """
        self.room_group_name = "likes"
        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code: int) -> None:
        """
        Handle WebSocket disconnection.
        
        Removes the connection from the "likes" group when the client disconnects.
        
        Args:
            close_code: WebSocket close code indicating the reason for disconnection
        """
        logger.debug("WebSocket disconnected with code %s", close_code)
        await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

    async def like_message(self, event: dict[str, Any]) -> None:
        """
        Handle broadcast message when a post's like count changes.
        
        Sends the updated like count to the client, unless this is the user
        who triggered the like (they already see the update optimistically).
        Anonymous users always receive updates since they can't trigger likes.
        
        Args:
            event: Dictionary containing:
                - post_id: ID of the post whose like count changed
                - like_count: New like count for the post
                - user_id: ID of the user who triggered the like/unlike
        """
        post_id = event["post_id"]
        like_count = event["like_count"]
        user_id = event["user_id"]
        
        # Get current user ID (None for anonymous users)
        current_user_id = getattr(self.scope["user"], "id", None)
        
        # Don't send to the user who triggered the like (they update optimistically)
        # Anonymous users (id=None) always receive updates
        if current_user_id is None or current_user_id != user_id:
            await self.send(
                text_data=json.dumps({"post_id": post_id, "like_count": like_count})
            )
