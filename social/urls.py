from django.urls import path

from . import views


urlpatterns = [
    path("", views.home, name="home"),
    path("accounts/register/", views.register, name="register"),
    path("search/", views.search, name="search"),
    path("posts/<int:pk>/", views.post_detail, name="post_detail"),
    path("posts/<int:pk>/react/", views.toggle_reaction, name="toggle_reaction"),
    path("posts/<int:pk>/bookmark/", views.toggle_bookmark, name="toggle_bookmark"),
    path("comments/<int:pk>/delete/", views.delete_comment, name="delete_comment"),
    path("tags/<slug:slug>/", views.tag_posts, name="tag_posts"),
    path("users/<str:username>/", views.profile_detail, name="profile_detail"),
    path("users/<str:username>/follow/", views.toggle_follow, name="toggle_follow"),
    path("users/<str:username>/approve/", views.approve_follow, name="approve_follow"),
    path("users/<str:username>/block/", views.block_user, name="block_user"),
    path("profile/edit/", views.edit_profile, name="edit_profile"),
    path("notifications/", views.notifications, name="notifications"),
    path(
        "notifications/read-all/",
        views.mark_all_notifications_read,
        name="mark_all_notifications_read",
    ),
    path(
        "notifications/<int:pk>/read/",
        views.mark_notification_read,
        name="mark_notification_read",
    ),
    path("messages/", views.inbox, name="inbox"),
    path("messages/<int:pk>/", views.conversation_detail, name="conversation_detail"),
    path("api/feed/", views.api_feed, name="api_feed"),
    path("api/posts/<int:pk>/", views.api_post_detail, name="api_post_detail"),
]
