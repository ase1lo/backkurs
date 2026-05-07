from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    BlockedUserViewSet,
    BookmarkViewSet,
    CommentViewSet,
    ConversationViewSet,
    FollowViewSet,
    LogoutAPIView,
    MeAPIView,
    MessageViewSet,
    NotificationViewSet,
    PostViewSet,
    RegisterAPIView,
    ReportViewSet,
    TagViewSet,
    TokenLoginAPIView,
    UserViewSet,
)


router = DefaultRouter()
router.register("users", UserViewSet, basename="api-users")
router.register("posts", PostViewSet, basename="api-posts")
router.register("comments", CommentViewSet, basename="api-comments")
router.register("tags", TagViewSet, basename="api-tags")
router.register("bookmarks", BookmarkViewSet, basename="api-bookmarks")
router.register("follows", FollowViewSet, basename="api-follows")
router.register("blocks", BlockedUserViewSet, basename="api-blocks")
router.register("notifications", NotificationViewSet, basename="api-notifications")
router.register("conversations", ConversationViewSet, basename="api-conversations")
router.register("messages", MessageViewSet, basename="api-messages")
router.register("reports", ReportViewSet, basename="api-reports")


urlpatterns = [
    path("auth/register/", RegisterAPIView.as_view(), name="api-register"),
    path("auth/token/", TokenLoginAPIView.as_view(), name="api-token"),
    path("auth/logout/", LogoutAPIView.as_view(), name="api-logout"),
    path("auth/me/", MeAPIView.as_view(), name="api-me"),
    path("", include(router.urls)),
]
