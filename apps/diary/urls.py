from django.urls import include, path
from .views import (
    HomeView,
    HomeViewLikeOrdered,
   

    SignUp,
    Login,
    PasswordReset,
    CustomPasswordResetConfirmView,

    AuthorListView,
    AuthorDetailView,

    PostListView,
    PostCreateView,
    PostDetailView,
    PostUpdateView,
    PostDeleteView,

    RootAPIView,

    UserListAPIView,
    UserDetailAPIView,
    TokenRecoveryAPIView,
    MyTokenObtainPairView,
    MyTokenRefreshView,

    PostAPIView,
    PostDetailAPIView,

    LikeAPIView,
    LikeCreateDestroyAPIView,
    LikeDetailAPIView,
    getLikes,
)
from django.contrib.auth.views import LogoutView
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.views import TokenVerifyView


urlpatterns = [
    path("", HomeView.as_view(), name="home"),
    path("like_ordered/", HomeViewLikeOrdered.as_view(), name="home-like-ordering"),

    path("signup/", SignUp.as_view(), name="signup"),
    path("login/", Login.as_view(), name="login"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("password_reset/", PasswordReset.as_view(), name="password_reset"),
    path("reset/<uidb64>/<token>/", CustomPasswordResetConfirmView.as_view(), name="password_reset_confirm"),
    # Here we include some other Django default auth views like PasswordChangeView and so on.
    path("", include("django.contrib.auth.urls")),

    path("authors/", AuthorListView.as_view(), name="author-list"),
    path("authors/<sortfield>/", AuthorListView.as_view(), name="author-list"),
    path("author/<int:pk>/", AuthorDetailView.as_view(), name="author-detail"),

    path("posts/", PostListView.as_view(), name="post-list"),
    path("posts/add/", PostCreateView.as_view(), name="post-add"),
    path("posts/<int:pk>/", PostDetailView.as_view(), name="post-detail"),
    path("posts/<int:pk>/update/", PostUpdateView.as_view(), name="post-update"),
    path("posts/<int:pk>/delete/", PostDeleteView.as_view(), name="post-delete"),

    path("api/v1/", RootAPIView.as_view(), name="root-api"),

    path("api/v1/users/", UserListAPIView.as_view(), name="user-list-create-api"),
    path("api/v1/users/<int:pk>/", UserDetailAPIView.as_view(), name="user-detail-update-destroy-api"),
    path("api/v1/auth/login/", TokenObtainPairView.as_view(), name="login-api"),
    path("api/v1/mylogin/", MyTokenObtainPairView.as_view(), name="my-login-api"),
    path('api/v1/auth/token/verify/', TokenVerifyView.as_view(), name='token_verify'),
    path("api/v1/auth/token-refresh/", MyTokenRefreshView.as_view(), name="token-refresh-api"),
    path("api/v1/auth/token-recovery/", TokenRecoveryAPIView.as_view(), name="token-recovery-api"),

    path("api/v1/posts/", PostAPIView.as_view(), name="post-list-create-api"),
    path("api/v1/posts/<int:pk>/", PostDetailAPIView.as_view(), name="post-detail-api"),

    path("api/v1/likes/", LikeAPIView.as_view(), name="like-list-api"),
    path("api/v1/likes/<int:pk>/", LikeDetailAPIView.as_view(), name="like-detail-api"),
    path("api/v1/likes/add/", LikeCreateDestroyAPIView.as_view(), name="like-create-destroy-post-api"),
    path("likes_count_on_post/<int:post_id>/", getLikes, name="like-count-on-post"),
]
