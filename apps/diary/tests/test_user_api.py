from django.core.exceptions import FieldError

from rest_framework import status
from rest_framework.reverse import reverse

from apps.diary.models import CustomUser
from apps.diary.serializers import (
    UserDetailSerializer,
    UserSerializer,
)

from .test_fixture import DiaryAPITestCase


class PostAPITestCase(DiaryAPITestCase):
    def test_user_list(self):
        # Unauthorized
        response1 = self.client.get(reverse("user-list-create-api"))
        self.assertEqual(response1.status_code, status.HTTP_401_UNAUTHORIZED)

        # Authorized as non-staff user
        response2 = self.client.get(
            reverse("user-list-create-api"),
            HTTP_AUTHORIZATION=f"Bearer {self.access_token_user1}",
        )
        self.assertEqual(response2.status_code, status.HTTP_403_FORBIDDEN)

        # Authorized as admin
        response3 = self.client.get(
            reverse("user-list-create-api"),
            HTTP_AUTHORIZATION=f"Bearer {self.access_token_admin}",
        )
        self.assertEqual(response3.status_code, status.HTTP_200_OK)
        # Verify we got paginated results with all users
        self.assertEqual(len(response3.data["results"]), CustomUser.objects.count())
        # Verify response contains properly serialized user data
        response_usernames = {u["username"] for u in response3.data["results"]}
        expected_usernames = set(CustomUser.objects.values_list("username", flat=True))
        self.assertEqual(response_usernames, expected_usernames)

    def test_user_create(self):
        # Authorized
        response1 = self.client.post(
            reverse("user-list-create-api"),
            {
                "username": "NewTestUser",
                "email": "somemail@gmail.com",
                "password": "ribark8903",
                "password2": "ribark8903",
            },
            HTTP_AUTHORIZATION=f"Bearer {self.access_token_user1}",
        )
        self.assertEqual(response1.status_code, status.HTTP_403_FORBIDDEN)
        self.assertRaises(
            CustomUser.DoesNotExist, CustomUser.objects.get, username="NewTestUser"
        )

        # Unauthorized, correct data
        response2 = self.client.post(
            reverse("user-list-create-api"),
            {
                "username": "NewTestUser",
                "email": "somemail@gmail.com",
                "password": "ribark8903",
                "password2": "ribark8903",
            },
        )
        serializer = UserSerializer(
            CustomUser.objects.get(username="NewTestUser"),
            context={"request": response2.wsgi_request},
        )
        self.assertEqual(response2.status_code, status.HTTP_201_CREATED)
        self.assertTrue(CustomUser.objects.get(username="NewTestUser"))
        self.assertEqual(serializer.data, response2.data)

        # Password2 missed
        response3 = self.client.post(
            reverse("user-list-create-api"),
            {
                "username": "NewTestUser2",
                "email": "somemail2@gmail.com",
                "password": "ribark8903cz",
            },
        )
        self.assertEqual(response3.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertRaises(
            CustomUser.DoesNotExist, CustomUser.objects.get, username="NewTestUser2"
        )

        # Email missed
        response4 = self.client.post(
            reverse("user-list-create-api"),
            {
                "username": "NewTestUser2",
                "password": "ribark8903cz",
                "password2": "ribark8903cz",
            },
        )
        self.assertEqual(response4.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertRaises(
            CustomUser.DoesNotExist, CustomUser.objects.get, username="NewTestUser2"
        )

        # Invalid email
        response5 = self.client.post(
            reverse("user-list-create-api"),
            {
                "username": "NewTestUser2",
                "email": "sdncsja.io",
                "password": "ribark8903cz",
                "password2": "ribark8903cz",
            },
        )
        self.assertEqual(response5.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertRaises(
            CustomUser.DoesNotExist, CustomUser.objects.get, username="NewTestUser2"
        )

        # Passwords doesn't match
        response6 = self.client.post(
            reverse("user-list-create-api"),
            {
                "username": "NewTestUser2",
                "email": "sdncsja.io",
                "password": "ribark8903cz",
                "password2": "ribark8903",
            },
        )
        self.assertEqual(response6.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertRaises(
            CustomUser.DoesNotExist, CustomUser.objects.get, username="NewTestUser2"
        )

        # Passwords similar with username
        response7 = self.client.post(
            reverse("user-list-create-api"),
            {
                "username": "NewTestUser2",
                "email": "somemail2@gmail.com",
                "password": "newtestuser2",
                "password2": "newtestuser2",
            },
        )
        self.assertEqual(response7.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertRaises(
            CustomUser.DoesNotExist, CustomUser.objects.get, username="NewTestUser2"
        )

        # Unnessesary fields
        response8 = self.client.post(
            reverse("user-list-create-api"),
            {
                "username": "NewTestUser2",
                "email": "somemail2@gmail.com",
                "password": "ribark8903cz",
                "password2": "ribark8903cz",
                "sex": "Male",
            },
        )
        object = CustomUser.objects.get(username="NewTestUser2")
        serializer8 = UserSerializer(
            object, context={"request": response2.wsgi_request}
        )
        self.assertEqual(response2.status_code, status.HTTP_201_CREATED)
        self.assertFalse(getattr(object, "sex", False))
        self.assertRaises(FieldError, CustomUser.objects.get, sex="Male")
        self.assertEqual(serializer8.data, response8.data)

    def test_user_detail(self):
        def compare_user_data(serializer_data, response_data):
            """Compare user data excluding last_request (updated by middleware after response)."""
            s_data = {k: v for k, v in serializer_data.items() if k != "last_request"}
            r_data = {k: v for k, v in response_data.items() if k != "last_request"}
            return s_data == r_data

        # Authorized by owner
        response = self.client.get(
            reverse("user-detail-update-destroy-api", args=[self.test_user_1.id]),
            HTTP_AUTHORIZATION=f"Bearer {self.access_token_user1}",
        )
        serializer = UserDetailSerializer(
            self.test_user_1,
            context={"request": response.wsgi_request},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(compare_user_data(serializer.data, response.data))

        # Authorized by admin
        response = self.client.get(
            reverse("user-detail-update-destroy-api", args=[self.test_user_1.id]),
            HTTP_AUTHORIZATION=f"Bearer {self.access_token_admin}",
        )
        serializer = UserDetailSerializer(
            self.test_user_1,
            context={"request": response.wsgi_request},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(compare_user_data(serializer.data, response.data))

        # Authorized by non-owner (and non-admin)
        response = self.client.get(
            reverse("user-detail-update-destroy-api", args=[self.test_user_1.id]),
            HTTP_AUTHORIZATION=f"Bearer {self.access_token_user2}",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        # Unauthorized
        response = self.client.get(
            reverse("user-detail-update-destroy-api", args=[self.test_user_1.id]),
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_user_update(self):
        """
        User detail endpoint does not support updates.

        All profile updates must use dedicated endpoints:
        - /api/v1/auth/password/change/
        - /api/v1/auth/username/change/
        - /api/v1/auth/email/change/
        """

        # Snapshot user before requests
        response_initial = self.client.get("/")
        serializer_before = UserDetailSerializer(
            self.test_user_1, context={"request": response_initial.wsgi_request}
        )

        url = reverse("user-detail-update-destroy-api", args=[self.test_user_1.id])

        # Unauthorized PUT
        response = self.client.put(url, {"email": "newemail@ukr.net"})
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

        # Authorized PUT (owner)
        response = self.client.put(
            url,
            {"email": "newemail@ukr.net"},
            HTTP_AUTHORIZATION=f"Bearer {self.access_token_user1}",
        )
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

        # Authorized PATCH (owner)
        response = self.client.patch(
            url,
            {"email": "newemail@ukr.net"},
            HTTP_AUTHORIZATION=f"Bearer {self.access_token_user1}",
        )
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

        # Ensure user has not changed
        serializer_after = UserDetailSerializer(
            CustomUser.objects.get(id=self.test_user_1.id),
            context={"request": response_initial.wsgi_request},
        )
        self.assertEqual(serializer_before.data, serializer_after.data)

    def test_user_delete(self):
        # Unauthorized
        response = self.client.delete(
            reverse("user-detail-update-destroy-api", args=[self.test_user_2.id])
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertTrue(CustomUser.objects.get(id=self.test_user_2.id))

        # Authorized by owner
        response = self.client.delete(
            reverse("user-detail-update-destroy-api", args=[self.test_user_2.id]),
            HTTP_AUTHORIZATION=f"Bearer {self.access_token_user2}",
        )
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertRaises(
            CustomUser.DoesNotExist, CustomUser.objects.get, username="TestUser2"
        )

        # Authorized by admin
        response = self.client.delete(
            reverse("user-detail-update-destroy-api", args=[self.test_user_3.id]),
            HTTP_AUTHORIZATION=f"Bearer {self.access_token_admin}",
        )
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertRaises(
            CustomUser.DoesNotExist, CustomUser.objects.get, username="TestUser3"
        )

    def test_password_change(self):
        """Test the dedicated password change endpoint."""

        # Unauthorized request
        response = self.client.post(
            reverse("password-change-api"),
            {
                "old_password": "fokker123",
                "new_password": "newpassword123",
                "new_password2": "newpassword123",
            },
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

        # Authorized but wrong old password
        response = self.client.post(
            reverse("password-change-api"),
            {
                "old_password": "wrongpassword",
                "new_password": "newpassword123",
                "new_password2": "newpassword123",
            },
            HTTP_AUTHORIZATION=f"Bearer {self.access_token_user1}",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("old_password", response.data)

        # Authorized but passwords don't match
        response = self.client.post(
            reverse("password-change-api"),
            {
                "old_password": "fokker123",
                "new_password": "newpassword123",
                "new_password2": "differentpassword123",
            },
            HTTP_AUTHORIZATION=f"Bearer {self.access_token_user1}",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("new_password2", response.data)

        # Authorized but new password too simple
        response = self.client.post(
            reverse("password-change-api"),
            {
                "old_password": "fokker123",
                "new_password": "123",
                "new_password2": "123",
            },
            HTTP_AUTHORIZATION=f"Bearer {self.access_token_user1}",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        # Successful password change
        original_password_hash = self.test_user_1.password
        response = self.client.post(
            reverse("password-change-api"),
            {
                "old_password": "fokker123",
                "new_password": "newpassword123",
                "new_password2": "newpassword123",
            },
            HTTP_AUTHORIZATION=f"Bearer {self.access_token_user1}",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("detail", response.data)

        # Verify password was actually changed
        self.test_user_1.refresh_from_db()
        self.assertNotEqual(self.test_user_1.password, original_password_hash)
        self.assertTrue(self.test_user_1.check_password("newpassword123"))

    def test_username_change(self):
        """Test the dedicated username change endpoint."""
        from datetime import timedelta

        from django.utils import timezone

        # Unauthorized request
        response = self.client.post(
            reverse("username-change-api"),
            {
                "password": "fokker123",
                "new_username": "NewTestUser1",
            },
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

        # Authorized but wrong password
        response = self.client.post(
            reverse("username-change-api"),
            {
                "password": "wrongpassword",
                "new_username": "NewTestUser1",
            },
            HTTP_AUTHORIZATION=f"Bearer {self.access_token_user1}",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("password", response.data)

        # Authorized but username already taken (case-insensitive)
        response = self.client.post(
            reverse("username-change-api"),
            {
                "password": "fokker123",
                "new_username": "testuser2",  # TestUser2 exists (case-insensitive check)
            },
            HTTP_AUTHORIZATION=f"Bearer {self.access_token_user1}",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("new_username", response.data)

        # Successful username change
        original_username = self.test_user_1.username
        response = self.client.post(
            reverse("username-change-api"),
            {
                "password": "fokker123",
                "new_username": "NewTestUser1",
            },
            HTTP_AUTHORIZATION=f"Bearer {self.access_token_user1}",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("detail", response.data)
        self.assertEqual(response.data["username"], "NewTestUser1")

        # Verify username was actually changed
        self.test_user_1.refresh_from_db()
        self.assertNotEqual(self.test_user_1.username, original_username)
        self.assertEqual(self.test_user_1.username, "NewTestUser1")
        self.assertIsNotNone(self.test_user_1.username_changed_at)

        # Test 30-day cooldown - immediate second change should fail
        response = self.client.post(
            reverse("username-change-api"),
            {
                "password": "fokker123",
                "new_username": "AnotherUsername",
            },
            HTTP_AUTHORIZATION=f"Bearer {self.access_token_user1}",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("new_username", response.data)
        # Username should remain unchanged
        self.test_user_1.refresh_from_db()
        self.assertEqual(self.test_user_1.username, "NewTestUser1")

        # Simulate cooldown period passed (set username_changed_at to 31 days ago)
        self.test_user_1.username_changed_at = timezone.now() - timedelta(days=31)
        self.test_user_1.save()

        # Now username change should succeed
        response = self.client.post(
            reverse("username-change-api"),
            {
                "password": "fokker123",
                "new_username": "AnotherUsername",
            },
            HTTP_AUTHORIZATION=f"Bearer {self.access_token_user1}",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.test_user_1.refresh_from_db()
        self.assertEqual(self.test_user_1.username, "AnotherUsername")
