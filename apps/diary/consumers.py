import json
from channels.generic.websocket import WebsocketConsumer
from asgiref.sync import async_to_sync


class LikeConsumer(WebsocketConsumer):
    def connect(self):
        self.room_group_name = "likes"
        async_to_sync(self.channel_layer.group_add)(
            self.room_group_name, self.channel_name
        )
        self.accept()

    def disconnect(self, close_code):
        print("Socket Disconnected")

    def like_message(self, event):
        post_id = event["post_id"]
        like_count = event["like_count"]
        user_id = event["user_id"]
        if self.scope["user"].id != user_id:
            self.send(
                text_data=json.dumps({"post_id": post_id, "like_count": like_count})
            )
