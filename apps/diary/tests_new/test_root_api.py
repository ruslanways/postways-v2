import pytest
from rest_framework.reverse import reverse
from rest_framework.test import APIClient


@pytest.fixture
def api_client():
    return APIClient()


class TestRootAPI:
    """Test suite for the Root API endpoint."""

    def test_returns_200_status_code(self, api_client):
        """Test that the root API endpoint returns HTTP 200 OK."""
        response = api_client.get(reverse("root-api"))
        assert response.status_code == 200

    def test_allows_get_head_options(self, api_client):
        """Test that only GET, HEAD, OPTIONS methods are allowed."""
        response = api_client.options(reverse("root-api"))
        allow_header = response.get("Allow")

        # Allowed methods
        assert "GET" in allow_header
        assert "HEAD" in allow_header
        assert "OPTIONS" in allow_header

        # Not allowed methods
        assert "POST" not in allow_header
        assert "PUT" not in allow_header
        assert "PATCH" not in allow_header
        assert "DELETE" not in allow_header

    def test_returns_hyperlinks(self, api_client):
        """Test that the response contains posts, users, likes hyperlinks."""
        response = api_client.get(reverse("root-api"))

        assert "posts" in response.data
        assert "users" in response.data
        assert "likes" in response.data

        assert response.data["posts"].startswith("http")
        assert response.data["users"].startswith("http")
        assert response.data["likes"].startswith("http")
