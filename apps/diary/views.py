from django.shortcuts import get_object_or_404, redirect, resolve_url
from django.urls import reverse_lazy
from django.views.generic import ListView, DetailView
from django.views.generic.edit import CreateView, UpdateView, DeleteView
from django.views.generic.list import MultipleObjectMixin
from django.contrib.auth.views import (
    LoginView,
    PasswordResetView,
    PasswordResetConfirmView,
)
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.auth import login
from .models import Post, CustomUser, Like
from django.db.models import Count
from .forms import (
    AddPostForm,
    CustomPasswordResetForm,
    CustomUserCreationForm,
    CustomAuthenticationForm,
    CustomSetPasswordForm,
    UpdatePostForm,
)
from django.conf import settings
from django.http import HttpResponse
from rest_framework import generics, status
from .serializers import (
    LikeCreateDestroySerializer,
    LikeSerializer,
    LikeDetailSerializer,
    MyTokenRefreshSerializer,
    PostDetailSerializer,
    PostSerializer,
    TokenRecoverySerializer,
    UserDetailSerializer,
    UserSerializer,
)
from rest_framework.response import Response
from rest_framework import permissions
from .permissions import (
    OwnerOrAdmin,
    OwnerOrAdminOrReadOnly,
    ReadForAdminCreateForAnonymous,
)
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.token_blacklist.models import (
    OutstandingToken,
    BlacklistedToken,
)
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import OrderingFilter
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.reverse import reverse
from rest_framework_simplejwt.views import TokenRefreshView
from .tasks import send_token_recovery_email
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync


class HomeView(ListView):
    paginate_by = 5

    template_name = "diary/index.html"
    queryset = (
        Post.objects.annotate(Count("like"))
        .select_related("author")
        .filter(published=True)
    )
    ordering = ["-updated", "-like__count"]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["ordering"] = "fresh"
        if self.request.user.is_authenticated:
            context["liked_by_user"] = self.queryset.filter(
                like__user=self.request.user
            )
        return context


class HomeViewLikeOrdered(HomeView):
    """Provide ordering by clicking on a link leads to the view."""

    ordering = ["-like__count", "-updated"]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["ordering"] = "liked"
        return context


class SignUp(CreateView):
    form_class = CustomUserCreationForm
    template_name = "registration/signup.html"

    # success_url = reverse_lazy('home')

    def form_valid(self, form):
        """If the form is valid, save the associated model."""
        self.object = form.save()
        """make an authorization after signingup"""
        login(self.request, self.object)
        """and redirect to user profile with user.pk"""
        return redirect("author-detail", self.object.pk)


class Login(LoginView):
    template_name = "registration/login.html"
    form_class = CustomAuthenticationForm

    def get_default_redirect_url(self):
        return resolve_url("author-detail", self.request.user.pk)


class PasswordReset(PasswordResetView):
    form_class = CustomPasswordResetForm


class CustomPasswordResetConfirmView(PasswordResetConfirmView):
    form_class = CustomSetPasswordForm


class AuthorListView(UserPassesTestMixin, ListView):
    template_name = "diary/customuser_list.html"
    permission_denied_message = "Access for staff only!"
    raise_exception = False

    def test_func(self):
        return self.request.user.is_staff

    def get_queryset(self):
        """
        Implement user-ordering using session to store per-user sort preference.
        Toggle between ascending/descending when clicking the same field.
        """
        sortfield = self.kwargs.get("sortfield")
        session_key = "author_list_ordering"

        if sortfield:
            current_ordering = self.request.session.get(session_key, "id")
            if "-" + sortfield == current_ordering:
                ordering = sortfield
            else:
                ordering = "-" + sortfield
            self.request.session[session_key] = ordering
        else:
            ordering = self.request.session.get(session_key, "id")

        return CustomUser.objects.annotate(
            Count("post", distinct=True),
            Count("like", distinct=True),
            Count("post__like", distinct=True),
        ).order_by(ordering)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["posts"] = Post.objects.count()
        context["likes"] = Like.objects.count()
        return context


class AuthorDetailView(UserPassesTestMixin, DetailView, MultipleObjectMixin):
    template_name = "diary/customuser_detail.html"
    model = CustomUser
    paginate_by = 5
    permission_denied_message = "Access for staff or profile owner only!"

    def test_func(self):
        return self.request.user.is_staff or self.request.user.id == self.kwargs["pk"]

    def get_context_data(self, **kwargs):
        object_list = (
            self.get_object()
            .post_set.all()
            .annotate(Count("like"))
            .order_by("-updated", "-like__count")
        )
        context = super().get_context_data(object_list=object_list, **kwargs)
        return context


class PostListView(UserPassesTestMixin, HomeView, ListView):
    template_name = "diary/post_list.html"
    queryset = Post.objects.annotate(Count("like")).select_related("author")
    # ordering = ['-updated', '-like__count'] inherit from parent class

    permission_denied_message = "Access for staff only!"

    def test_func(self):
        return self.request.user.is_staff


class PostCreateView(LoginRequiredMixin, CreateView):
    form_class = AddPostForm
    template_name = "diary/add-post.html"
    success_url = reverse_lazy("home")

    def form_valid(self, form):
        form.instance.author = self.request.user
        return super().form_valid(form)


class PostDetailView(DetailView):
    template_name = "diary/post_detail.html"
    queryset = Post.objects.annotate(Count("like")).select_related("author")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.user.is_authenticated:
            context["liked_by_user"] = self.queryset.filter(
                like__user=self.request.user
            )
        return context


class PostOwnerOrStaffMixin(UserPassesTestMixin):
    """Mixin for views that require post owner or staff access."""

    permission_denied_message = "Access for staff or profile owner!"

    def test_func(self):
        return (
            self.request.user.is_staff
            or self.request.user.pk == self.get_object().author_id
        )


class PostUpdateView(PostOwnerOrStaffMixin, UpdateView):
    model = Post
    form_class = UpdatePostForm
    template_name = "diary/post-update.html"


class PostDeleteView(PostOwnerOrStaffMixin, DeleteView):
    model = Post
    template_name = "diary/post-delete.html"

    def get_success_url(self):
        return reverse_lazy(
            "author-detail", kwargs={"pk": f"{self.get_object().author_id}"}
        )


#######################################################################################################################
# Rest api with DRF


class UserListAPIView(generics.ListCreateAPIView):
    queryset = CustomUser.objects.all().order_by("-last_request")
    serializer_class = UserSerializer
    permission_classes = (ReadForAdminCreateForAnonymous,)


class UserDetailAPIView(generics.RetrieveUpdateDestroyAPIView):
    queryset = CustomUser.objects.all()
    serializer_class = UserDetailSerializer
    permission_classes = (OwnerOrAdmin,)

    def get_object(self):
        """Cache the object to avoid duplicate database queries."""
        if not hasattr(self, "_cached_object"):
            self._cached_object = super().get_object()
        return self._cached_object

    def get_serializer_context(self):
        """
        Override parent's method.
        Add extra context 'obj' for using in serializer validator to get object.
        """
        return {
            "request": self.request,
            "format": self.format_kwarg,
            "view": self,
            "obj": self.get_object(),
        }


class PostAPIView(generics.ListCreateAPIView):
    serializer_class = PostSerializer
    filter_backends = DjangoFilterBackend, OrderingFilter
    ordering_fields = "id", "updated", "created"
    permission_classes = (permissions.IsAuthenticatedOrReadOnly,)

    def get_queryset(self):
        return (
            Post.objects.exclude(published=False)
            .annotate(likes=Count("like"))
            .order_by("-updated")
        )

    def perform_create(self, serializer):
        serializer.save(author=self.request.user)


class PostDetailAPIView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Post.objects.all()
    serializer_class = PostDetailSerializer
    # permissions: Retrieve by All, Update by Author only, Delete by Author or Admin
    permission_classes = (OwnerOrAdminOrReadOnly,)

    def retrieve(self, request, *args, **kwargs):
        """Make visible only published posts if user is not owner or admin."""
        instance = self.get_object()
        if (
            not instance.published
            and instance.author != request.user
            and not request.user.is_staff
        ):
            return Response(
                {"Forbidden": "Unpublished post can be retrieved by owner only!"},
                status=403,
            )
        serializer = self.get_serializer(instance)
        return Response(serializer.data)


class LikeAPIView(generics.ListAPIView):
    queryset = (
        Like.objects.values("created__date")
        .annotate(likes=Count("id"))
        .order_by("-created__date")
    )
    serializer_class = LikeSerializer
    filter_backends = DjangoFilterBackend, OrderingFilter
    filterset_fields = {
        "created": ["gte", "lte", "date__range"],
    }
    ordering_fields = "created", "likes"


class LikeDetailAPIView(generics.RetrieveAPIView):
    queryset = Like.objects.all()
    serializer_class = LikeDetailSerializer


class LikeCreateDestroyAPIView(generics.CreateAPIView):
    """
    Create/Destroy Like with POST request.
    """

    permission_classes = (permissions.IsAuthenticated,)
    queryset = Like.objects.all()
    serializer_class = LikeCreateDestroySerializer

    def create(self, request, *args, **kwargs):
        """
        Override .create:
        1) to add self.request.user to serializer user field,
        2) to implement Destroying Like in case of duplicate Like exist
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        post = serializer.validated_data["post"]
        user = self.request.user
        existing_like = self.queryset.filter(post=post, user=user).first()

        if existing_like:
            existing_like.delete()
            response = Response(status=status.HTTP_204_NO_CONTENT)
        else:
            serializer.save(user=user)
            headers = self.get_success_headers(serializer.data)
            response = Response(
                serializer.data, status=status.HTTP_201_CREATED, headers=headers
            )

        # Broadcast like update to all connected WebSocket clients
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            "likes",
            {
                "type": "like.message",
                "post_id": str(post.id),
                "like_count": str(post.like_set.count()),
                "user_id": user.id,
            },
        )

        return response


def getLikes(request, post_id):
    """
    View to help update likes for updateLike function in fetch.js
    """
    post = get_object_or_404(Post, pk=post_id)
    like_count = post.like_set.count()

    if (
        request.user.is_authenticated
        and post.like_set.filter(user=request.user).exists()
    ):
        heart = "&#10084;"
    else:
        heart = "&#9825;"
    return HttpResponse(f"{heart} {like_count}")


class MyTokenRefreshView(TokenRefreshView):
    serializer_class = MyTokenRefreshSerializer


class TokenRecoveryAPIView(generics.GenericAPIView):
    """
    APIView to recover token in case of user forgot his password.
    All non-blacklisted REFRESH tokens (OutstandingToken) of the user gets blacklisted.
    And the new (pair) will generate and email to user.
    """

    serializer_class = TokenRecoverySerializer

    def post(self, request, *args, **kwargs):
        if len(request.data) != 1 or not request.data.get("email"):
            return Response(
                {"error": "please post email only"}, status=status.HTTP_400_BAD_REQUEST
            )

        serializer = self.serializer_class(data=request.data)

        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        email = serializer.validated_data["email"]

        try:
            user = CustomUser.objects.get(email=email)
        except CustomUser.DoesNotExist:
            return Response(
                {"error": "No user found with this email"},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Blacklist all non-blacklisted tokens for this user
        blacklisted_token_ids = BlacklistedToken.objects.filter(
            token__user=user
        ).values_list("token_id", flat=True)
        tokens_to_blacklist = OutstandingToken.objects.filter(user=user).exclude(
            id__in=blacklisted_token_ids
        )
        BlacklistedToken.objects.bulk_create(
            [BlacklistedToken(token=token) for token in tokens_to_blacklist],
            ignore_conflicts=True,
        )

        refresh = RefreshToken.for_user(user)

        link_to_change_user = reverse(
            "user-detail-update-destroy-api", request=request, args=[user.id]
        )

        # invoke celery task
        send_token_recovery_email.delay(
            link_to_change_user, str(refresh.access_token), user.email
        )

        return Response({"Recovery email send": "Success"}, status=status.HTTP_200_OK)


class MyTokenObtainPairView(TokenObtainPairView):
    """
    Just an attempt to implement jwt-authorization for html site.
    The idea is to save refresh-token in cookies as most secure place
    and throw access-token to frontend (on frontend we can cath access-token
    in JS and store it within a variable (clousure scope) - I think it needs
    to make login-requests using AJAX(fetch)).
    """

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
        except TokenError as e:
            raise InvalidToken(e.args[0])
        response = Response(
            {"access_token": serializer.validated_data["access"]},
            status=status.HTTP_200_OK,
        )
        response.set_cookie(
            key="refresh_token",
            value=serializer.validated_data["refresh"],
            httponly=True,
            samesite="Strict",
            secure=not settings.DEBUG,
        )
        return response


class RootAPIView(generics.GenericAPIView):
    def get(self, request):
        return Response(
            {
                "posts": reverse("post-list-create-api", request=request),
                "users": reverse("user-list-create-api", request=request),
                "likes": reverse("like-list-api", request=request),
            }
        )


# ------------------------------------------------------------------------------
# Error handlers
# ------------------------------------------------------------------------------
def error_403(request, exception=None):
    """Custom 403 Forbidden handler."""
    from django.shortcuts import render

    if request.path.startswith("/api/"):
        from django.http import JsonResponse

        return JsonResponse({"error": "Forbidden"}, status=403)
    return render(request, "403.html", status=403)


def error_404(request, exception=None):
    """Custom 404 Not Found handler."""
    from django.shortcuts import render

    if request.path.startswith("/api/"):
        from django.http import JsonResponse

        return JsonResponse({"error": "Not found"}, status=404)
    return render(request, "404.html", status=404)
