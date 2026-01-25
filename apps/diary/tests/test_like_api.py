from django.db.models import Count

from rest_framework import status
from rest_framework.reverse import reverse

from apps.diary.models import Like
from apps.diary.serializers import (
    LikeDetailSerializer,
    LikeSerializer,
)

from .test_fixture import DiaryAPITestCase


class LikeAPITestCase(DiaryAPITestCase):
    """
    Test suite for Like API endpoints.
    
    Tests cover:
    - Listing likes (analytics/counts)
    - Retrieving like details
    - Creating and deleting likes (toggling behavior)
    """
    def test_like_list(self):
        """
        Test the like list endpoint which returns analytics data.
        
        This endpoint aggregates likes by date and counts them.
        """
        queryset = (
            Like.objects.values("created__date")
            .annotate(likes=Count("id"))
            .order_by("-created__date")
        )

        response = self.client.get(reverse("like-list-api"))

        serializer = LikeSerializer(
            queryset, many=True, context={"request": response.wsgi_request}
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(serializer.data, response.data["results"])

    def test_like_detail(self):
        """Test retrieving a single like object details."""
        response = self.client.get(
            reverse("like-detail-api", args=[self.test_like1.id])
        )

        serializer = LikeDetailSerializer(
            self.test_like1,
            context={"request": response.wsgi_request},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(serializer.data, response.data)

    def test_like_create_delete(self):
        """
        Test the like toggle functionality.
        
        The 'like-toggle-api' endpoint acts as a toggle:
        - If the user hasn't liked the post -> Create Like (HTTP 201)
        - If the user has already liked the post -> Delete Like (HTTP 204)
        """
        count = self.test_post_11.like_set.count()

        # Unauthorized
        response1 = self.client.post(
            reverse("like-toggle-api"),
            {"post": self.test_post_11.id},
        )

        self.assertEqual(response1.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(count, self.test_post_11.like_set.count())

        # Authorized by unliked user = CREATE the like
        response2 = self.client.post(
            reverse("like-toggle-api"),
            {"post": self.test_post_11.id},
            HTTP_AUTHORIZATION=f"Bearer {self.access_token_user1}",
        )

        self.assertEqual(response2.status_code, status.HTTP_201_CREATED)
        self.assertEqual(count + 1, self.test_post_11.like_set.count())

        # Authorized by liked user = DELETE the like
        response3 = self.client.post(
            reverse("like-toggle-api"),
            {"post": self.test_post_11.id},
            HTTP_AUTHORIZATION=f"Bearer {self.access_token_user1}",
        )

        self.assertEqual(response3.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(count, self.test_post_11.like_set.count())

        # Post doesn't exist
        response3 = self.client.post(
            reverse("like-toggle-api"),
            {"post": 3948},
            HTTP_AUTHORIZATION=f"Bearer {self.access_token_user1}",
        )

        self.assertEqual(response3.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(count, self.test_post_11.like_set.count())
