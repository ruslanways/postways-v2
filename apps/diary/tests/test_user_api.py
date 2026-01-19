from pprint import pprint
import random
import re
from unittest import skip

from .test_fixture import DiaryAPITestCase
from apps.diary.serializers import (
    UserSerializer,
    UserDetailSerializer,
)
from apps.diary.models import CustomUser
from rest_framework import status
from rest_framework.reverse import reverse
from django.core.exceptions import FieldError


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
        IMHO.
        It's worth noting that Post objects reachable with self.test_post_*
        only accessibe for retrieving so they don't change their state.
        In case we need to see wether the object is changed we should retrieve it from the object manager.
        """

        # Make a response just to obtain the wsgi_request for serializer to get serializer of clear Post object
        response_initial = self.client.get("/")
        serializer_before_update = UserDetailSerializer(
            self.test_user_1, context={"request": response_initial.wsgi_request}
        )

        # Unathorized
        response = self.client.put(
            reverse("user-detail-update-destroy-api", args=[self.test_user_1.id]),
            {
                "username": "TestUser1 UPDATED by put",
                "email": "newemail@ukr.net",
            },
        )
        serializer_after_update1 = UserDetailSerializer(
            CustomUser.objects.get(id=self.test_user_1.id),
            context={"request": response.wsgi_request},
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(serializer_before_update.data, serializer_after_update1.data)

        # Authorized by owner
        response = self.client.put(
            reverse("user-detail-update-destroy-api", args=[self.test_user_1.id]),
            {
                "username": "TestUser1PUTed",
                "email": "newemail@ukr.net",
            },
            HTTP_AUTHORIZATION=f"Bearer {self.access_token_user1}",
        )
        serializer_after_update2 = UserDetailSerializer(
            CustomUser.objects.get(id=self.test_user_1.id),
            context={"request": response.wsgi_request},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertNotEqual(
            serializer_after_update1.data, serializer_after_update2.data
        )
        self.assertEqual(serializer_after_update2.data["username"], "TestUser1PUTed")
        self.assertEqual(serializer_after_update2.data["email"], "newemail@ukr.net")

        # Authorized by admin
        response = self.client.put(
            reverse("user-detail-update-destroy-api", args=[self.test_user_1.id]),
            {
                "username": "TestUser1PUTedbyAdmin",
                "email": "newemailadm@ukr.net",
            },
            HTTP_AUTHORIZATION=f"Bearer {self.access_token_admin}",
        )
        serializer_after_update3 = UserDetailSerializer(
            CustomUser.objects.get(id=self.test_user_1.id),
            context={"request": response.wsgi_request},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertNotEqual(
            serializer_after_update2.data, serializer_after_update3.data
        )
        self.assertEqual(
            serializer_after_update3.data["username"], "TestUser1PUTedbyAdmin"
        )
        self.assertEqual(serializer_after_update3.data["email"], "newemailadm@ukr.net")

        ######PATCH
        # Authorized by owner, incorrect email
        response = self.client.patch(
            reverse("user-detail-update-destroy-api", args=[self.test_user_1.id]),
            {"username": "TestUser1PATCHed", "email": "asdnaa1223"},
            HTTP_AUTHORIZATION=f"Bearer {self.access_token_user1}",
        )
        serializer_after_update4 = UserDetailSerializer(
            CustomUser.objects.get(id=self.test_user_1.id),
            context={"request": response.wsgi_request},
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(serializer_after_update3.data, serializer_after_update4.data)

        # Authorized by owner, unnessesary unknown field
        response = self.client.patch(
            reverse("user-detail-update-destroy-api", args=[self.test_user_1.id]),
            {
                "username": "TestUser1PATCHed",
                "email": "asdnaa1223@gmail.com",
                "sex": "Female",
            },
            HTTP_AUTHORIZATION=f"Bearer {self.access_token_user1}",
        )
        serializer_after_update5 = UserDetailSerializer(
            CustomUser.objects.get(id=self.test_user_1.id),
            context={"request": response.wsgi_request},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertNotEqual(
            serializer_after_update4.data, serializer_after_update5.data
        )
        self.assertEqual(serializer_after_update5.data["username"], "TestUser1PATCHed")
        self.assertEqual(serializer_after_update5.data["email"], "asdnaa1223@gmail.com")
        self.assertRaises(FieldError, CustomUser.objects.get, sex="Female")

        # PASSWORD change by owner
        response = self.client.patch(
            reverse("user-detail-update-destroy-api", args=[self.test_user_1.id]),
            {"password": "fokker1234"},
            HTTP_AUTHORIZATION=f"Bearer {self.access_token_user1}",
        )
        # Please recall that self.test_user_1.password reffered to the virgin user on the test start
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertNotEqual(
            CustomUser.objects.get(id=self.test_user_1.id).password,
            self.test_user_1.password,
        )

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

