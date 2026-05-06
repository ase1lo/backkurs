from django.contrib import admin

from .models import (
    BlockedUser,
    Bookmark,
    Comment,
    Conversation,
    ConversationParticipant,
    Follow,
    Message,
    Notification,
    Post,
    PostAttachment,
    Profile,
    Reaction,
    Report,
    Tag,
)


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "display_name", "is_private", "created_at")
    search_fields = ("user__username", "display_name", "bio")
    list_filter = ("is_private",)


@admin.register(Follow)
class FollowAdmin(admin.ModelAdmin):
    list_display = ("follower", "following", "status", "created_at")
    list_filter = ("status",)
    search_fields = ("follower__username", "following__username")


@admin.register(BlockedUser)
class BlockedUserAdmin(admin.ModelAdmin):
    list_display = ("blocker", "blocked", "created_at")
    search_fields = ("blocker__username", "blocked__username")


class PostAttachmentInline(admin.TabularInline):
    model = PostAttachment
    extra = 0


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "author",
        "visibility",
        "like_count",
        "comment_count",
        "is_archived",
        "created_at",
    )
    list_filter = ("visibility", "is_archived", "is_pinned")
    search_fields = ("content", "author__username", "tags__name")
    filter_horizontal = ("tags",)
    inlines = [PostAttachmentInline]


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "created_at")
    search_fields = ("name", "slug")


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ("id", "post", "author", "is_deleted", "created_at")
    list_filter = ("is_deleted",)
    search_fields = ("content", "author__username", "post__content")


@admin.register(Reaction)
class ReactionAdmin(admin.ModelAdmin):
    list_display = ("post", "user", "kind", "created_at")
    list_filter = ("kind",)
    search_fields = ("user__username", "post__content")


@admin.register(Bookmark)
class BookmarkAdmin(admin.ModelAdmin):
    list_display = ("post", "user", "created_at")
    search_fields = ("user__username", "post__content")


class ConversationParticipantInline(admin.TabularInline):
    model = ConversationParticipant
    extra = 0


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ("id", "title", "is_group", "updated_at")
    list_filter = ("is_group",)
    inlines = [ConversationParticipantInline]


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ("conversation", "sender", "is_deleted", "created_at")
    list_filter = ("is_deleted",)
    search_fields = ("body", "sender__username")


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("recipient", "actor", "verb", "is_read", "created_at")
    list_filter = ("verb", "is_read")
    search_fields = ("recipient__username", "actor__username", "text")


@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = ("reporter", "reason", "is_resolved", "created_at")
    list_filter = ("reason", "is_resolved")
    search_fields = ("reporter__username", "details")
