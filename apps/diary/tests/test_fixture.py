
from apps.diary.models import CustomUser, Post, Like
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken



class DiaryAPITestCase(APITestCase):
    @classmethod
    def setUpTestData(cls):

        cls.admin = CustomUser.objects.create_user(
            email="admin@ukr.net", username="admin", password="fokker123", is_staff=True
        )
        cls.test_user_1 = CustomUser.objects.create_user(
            email="test1@ukr.net", username="TestUser1", password="fokker123"
        )
        cls.test_user_2 = CustomUser.objects.create_user(
            email="test2@ukr.net", username="TestUser2", password="fokker123"
        )
        cls.test_user_3 = CustomUser.objects.create_user(
            email="test3@ukr.net", username="TestUser3", password="fokker123"
        )

        cls.test_post_1 = Post.objects.create(
            title="TestPost1", author=cls.test_user_1, content="Some test 1 content"
        )
        cls.test_post_2 = Post.objects.create(
            title="TestPost2", author=cls.test_user_3, content="Some test 2 content"
        )
        cls.test_post_3 = Post.objects.create(
            title="TestPost3",
            author=cls.test_user_1,
            content="Some test 3 content",
            published=False,
        )
        cls.test_post_4 = Post.objects.create(
            title="TestPost4", author=cls.test_user_2, content="Some test 4 content"
        )
        cls.test_post_5 = Post.objects.create(
            title="TestPost5", author=cls.test_user_3, content="Some test 5 content"
        )
        cls.test_post_6 = Post.objects.create(
            title="TestPost6", author=cls.test_user_3, content="Some test 6 content"
        )
        cls.test_post_7 = Post.objects.create(
            title="TestPost7", author=cls.test_user_1, content="Some test 7 content"
        )
        cls.test_post_8 = Post.objects.create(
            title="TestPost8", author=cls.test_user_2, content="Some test 8 content"
        )
        cls.test_post_9 = Post.objects.create(
            title="TestPost9", author=cls.test_user_3, content="Some test 9 content"
        )
        cls.test_post_10 = Post.objects.create(
            title="TestPost10", author=cls.test_user_2, content="Some test 10 content"
        )
        cls.test_post_11 = Post.objects.create(
            title="TestPost11", author=cls.test_user_3, content="Some test 11 content"
        )
        cls.test_post_12 = Post.objects.create(
            title="TestPost12",
            author=cls.test_user_3,
            content="Some test 11 content",
            published=False,
        )

        # Obtaining an access token for further authorization by JWT-tokens.
        cls.access_token_admin = RefreshToken.for_user(cls.admin).access_token
        cls.access_token_user1 = RefreshToken.for_user(cls.test_user_1).access_token
        cls.access_token_user2 = RefreshToken.for_user(cls.test_user_2).access_token
        cls.access_token_user3 = RefreshToken.for_user(cls.test_user_3).access_token

        cls.test_like1 = Like.objects.create(user=cls.test_user_1, post=cls.test_post_1)
        cls.test_like2 = Like.objects.create(user=cls.test_user_1, post=cls.test_post_3)
        cls.test_like3 = Like.objects.create(user=cls.test_user_1, post=cls.test_post_5)
        cls.test_like4 = Like.objects.create(user=cls.test_user_1, post=cls.test_post_9)
        cls.test_like5 = Like.objects.create(user=cls.test_user_1, post=cls.test_post_7)
        cls.test_like6 = Like.objects.create(user=cls.test_user_1, post=cls.test_post_2)
        cls.test_like7 = Like.objects.create(user=cls.test_user_2, post=cls.test_post_1)
        cls.test_like8 = Like.objects.create(user=cls.test_user_2, post=cls.test_post_2)
        cls.test_like9 = Like.objects.create(user=cls.test_user_2, post=cls.test_post_3)
        cls.test_like10 = Like.objects.create(
            user=cls.test_user_2, post=cls.test_post_8
        )
        cls.test_like11 = Like.objects.create(
            user=cls.test_user_2, post=cls.test_post_10
        )
        cls.test_like12 = Like.objects.create(
            user=cls.test_user_2, post=cls.test_post_11
        )
        cls.test_like13 = Like.objects.create(
            user=cls.test_user_2, post=cls.test_post_5
        )
        cls.test_like14 = Like.objects.create(
            user=cls.test_user_3, post=cls.test_post_11
        )
        cls.test_like15 = Like.objects.create(
            user=cls.test_user_3, post=cls.test_post_3
        )
        cls.test_like16 = Like.objects.create(
            user=cls.test_user_3, post=cls.test_post_2
        )
        cls.test_like17 = Like.objects.create(
            user=cls.test_user_3, post=cls.test_post_1
        )
        cls.test_like18 = Like.objects.create(
            user=cls.test_user_3, post=cls.test_post_4
        )
        cls.test_like19 = Like.objects.create(
            user=cls.test_user_3, post=cls.test_post_7
        )
        cls.test_like20 = Like.objects.create(
            user=cls.test_user_3, post=cls.test_post_8
        )
        cls.test_like21 = Like.objects.create(
            user=cls.test_user_3, post=cls.test_post_9
        )
        cls.test_like22 = Like.objects.create(
            user=cls.test_user_3, post=cls.test_post_6
        )