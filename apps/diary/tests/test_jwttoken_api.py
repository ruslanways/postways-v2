from pprint import pprint
import random
import re
from unittest import skip

from .test_fixture import DiaryAPITestCase
from diary.models import CustomUser
from rest_framework import status
from rest_framework.reverse import reverse
from django.core import mail


class PostAPITestCase(DiaryAPITestCase):

    def test_jwt_authentication(self):
        # Create new user
        test_user_4 = CustomUser.objects.create_user(
            email="testuser4@ukr.net", username="TestUser4", password="fokker12345"
        )

        # Login-api icorrect password
        response1 = self.client.post(
            reverse("login-api"),
            {
                "username": test_user_4.username,
                "password": "Kaskmcs12341",
            },
        )
        self.assertEqual(response1.status_code, status.HTTP_401_UNAUTHORIZED)

        # Login-api correct data
        response2 = self.client.post(
            reverse("login-api"),
            {
                "username": test_user_4.username,
                "password": "fokker12345",
            },
        )
        self.assertEqual(response2.status_code, status.HTTP_200_OK)

        # Verify that refresh token (and access token too) is valid
        verify_token = self.client.post(
            reverse("token_verify"), {"token": response2.data["refresh"]}
        )
        self.assertEqual(verify_token.status_code, status.HTTP_200_OK)

        # incorrect token
        verify_token = self.client.post(
            reverse("token_verify"), {"token": "jsndvkajsdnvkajsnv"}
        )
        self.assertEqual(verify_token.status_code, status.HTTP_401_UNAUTHORIZED)

        # Token-refresh-api
        response3 = self.client.post(
            reverse("token-refresh-api"),
            {
                "refresh": response2.data["refresh"],
            },
        )
        self.assertEqual(response3.status_code, status.HTTP_200_OK)
        self.assertTrue(response3.data["access"])
        self.assertTrue(response3.data["refresh"])
        # Check wether new refreshed refresh token is valid
        verify_token = self.client.post(
            reverse("token_verify"), {"token": response3.data["refresh"]}
        )
        self.assertEqual(verify_token.status_code, status.HTTP_200_OK)
        # Check wether OLD refresh token is invalid
        verify_token = self.client.post(
            reverse("token_verify"), {"token": response2.data["refresh"]}
        )
        self.assertEqual(verify_token.status_code, status.HTTP_400_BAD_REQUEST)

        # # Token-recovery-api
        # response = self.client.post(
        #     reverse("token-recovery-api"), {"email": test_user_4.email}
        # )
        # self.assertEqual(response.status_code, status.HTTP_200_OK)
        # # Get the new 'access' token from email which has been emailed to the user
        # # It will be use by user to change password
        # new_access_token = re.search(r"(?<='access': ).+", mail.outbox[0].body)
        # verify_token = self.client.post(
        #     reverse("token_verify"), {"token": new_access_token.group()}
        # )
        # self.assertEqual(verify_token.status_code, status.HTTP_200_OK)
        # # Check wether OLD REFRESHED refresh token is invalid
        # verify_token = self.client.post(
        #     reverse("token_verify"), {"token": response3.data["refresh"]}
        # )
        # self.assertEqual(verify_token.status_code, status.HTTP_400_BAD_REQUEST)
        # # Check wether OLD-OLD refresh token is invalid
        # verify_token = self.client.post(
        #     reverse("token_verify"), {"token": response2.data["refresh"]}
        # )
        # self.assertEqual(verify_token.status_code, status.HTTP_400_BAD_REQUEST)
