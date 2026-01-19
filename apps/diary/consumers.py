import json
import logging

from channels.generic.websocket import AsyncWebsocketConsumer

logger = logging.getLogger(__name__)


class LikeConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.room_group_name = "likes"
        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        logger.debug("WebSocket disconnected with code %s", close_code)
        await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

    async def like_message(self, event):
        post_id = event["post_id"]
        like_count = event["like_count"]
        user_id = event["user_id"]
        # Don't send to the user who triggered the like (they update optimistically)
        # Anonymous users (id=None) always receive updates
        current_user_id = getattr(self.scope["user"], "id", None)
        if current_user_id is None or current_user_id != user_id:
            await self.send(
                text_data=json.dumps({"post_id": post_id, "like_count": like_count})
            )
