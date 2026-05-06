from __future__ import annotations

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F, Q
from django.utils import timezone
from django.utils.text import Truncator


class Profile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="profile",
    )
    display_name = models.CharField(max_length=80, blank=True)
    bio = models.TextField(max_length=500, blank=True)
    location = models.CharField(max_length=120, blank=True)
    website = models.URLField(blank=True)
    avatar_url = models.URLField(blank=True)
    birth_date = models.DateField(null=True, blank=True)
    is_private = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["user__username"]

    def __str__(self) -> str:
        return self.display_name or self.user.get_username()


class Follow(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        ACTIVE = "active", "Active"

    follower = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="following_relations",
    )
    following = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="follower_relations",
    )
    status = models.CharField(
        max_length=12,
        choices=Status.choices,
        default=Status.ACTIVE,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["follower", "following"],
                name="unique_follow_pair",
            ),
            models.CheckConstraint(
                condition=~Q(follower=F("following")),
                name="prevent_self_follow",
            ),
        ]
        indexes = [
            models.Index(fields=["follower", "status"]),
            models.Index(fields=["following", "status"]),
        ]

    def clean(self) -> None:
        if self.follower_id and self.follower_id == self.following_id:
            raise ValidationError("User cannot follow themselves.")

    def approve(self) -> None:
        self.status = self.Status.ACTIVE
        self.save(update_fields=["status", "updated_at"])

    def __str__(self) -> str:
        return f"{self.follower} -> {self.following} ({self.status})"


class BlockedUser(models.Model):
    blocker = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="blocked_users",
    )
    blocked = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="blocked_by_users",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["blocker", "blocked"],
                name="unique_block_pair",
            ),
            models.CheckConstraint(
                condition=~Q(blocker=F("blocked")),
                name="prevent_self_block",
            ),
        ]

    def clean(self) -> None:
        if self.blocker_id and self.blocker_id == self.blocked_id:
            raise ValidationError("User cannot block themselves.")

    def __str__(self) -> str:
        return f"{self.blocker} blocked {self.blocked}"


class Tag(models.Model):
    name = models.CharField(max_length=50, unique=True)
    slug = models.SlugField(max_length=60, unique=True, allow_unicode=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class PostQuerySet(models.QuerySet):
    def active(self) -> "PostQuerySet":
        return self.filter(is_archived=False)

    def visible_to(self, user) -> "PostQuerySet":
        qs = self.active()
        if not getattr(user, "is_authenticated", False):
            return qs.filter(visibility=Post.Visibility.PUBLIC)

        following_ids = Follow.objects.filter(
            follower=user,
            status=Follow.Status.ACTIVE,
        ).values("following_id")
        blocked_by_me = BlockedUser.objects.filter(blocker=user).values("blocked_id")
        blocked_me = BlockedUser.objects.filter(blocked=user).values("blocker_id")

        return (
            qs.exclude(author_id__in=blocked_by_me)
            .exclude(author_id__in=blocked_me)
            .filter(
                Q(visibility=Post.Visibility.PUBLIC)
                | Q(author=user)
                | Q(
                    visibility=Post.Visibility.FOLLOWERS,
                    author_id__in=following_ids,
                )
            )
            .distinct()
        )


class Post(models.Model):
    class Visibility(models.TextChoices):
        PUBLIC = "public", "Public"
        FOLLOWERS = "followers", "Followers"
        PRIVATE = "private", "Private"

    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="posts",
    )
    content = models.TextField(max_length=5000)
    visibility = models.CharField(
        max_length=16,
        choices=Visibility.choices,
        default=Visibility.PUBLIC,
    )
    tags = models.ManyToManyField(Tag, blank=True, related_name="posts")
    image_url = models.URLField(blank=True)
    like_count = models.PositiveIntegerField(default=0)
    comment_count = models.PositiveIntegerField(default=0)
    share_count = models.PositiveIntegerField(default=0)
    is_pinned = models.BooleanField(default=False)
    is_archived = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = PostQuerySet.as_manager()

    class Meta:
        ordering = ["-is_pinned", "-created_at"]
        indexes = [
            models.Index(fields=["author", "-created_at"]),
            models.Index(fields=["visibility", "-created_at"]),
        ]

    def clean(self) -> None:
        if not self.content or not self.content.strip():
            raise ValidationError({"content": "Post content cannot be empty."})

    def __str__(self) -> str:
        return Truncator(self.content).chars(48)


class PostAttachment(models.Model):
    class Kind(models.TextChoices):
        IMAGE = "image", "Image"
        VIDEO = "video", "Video"
        FILE = "file", "File"

    post = models.ForeignKey(
        Post,
        on_delete=models.CASCADE,
        related_name="attachments",
    )
    kind = models.CharField(max_length=12, choices=Kind.choices, default=Kind.IMAGE)
    url = models.URLField()
    caption = models.CharField(max_length=140, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self) -> str:
        return f"{self.kind}: {self.url}"


class Comment(models.Model):
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="comments")
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="comments",
    )
    parent = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="replies",
    )
    content = models.TextField(max_length=2000)
    is_deleted = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["created_at"]
        indexes = [
            models.Index(fields=["post", "created_at"]),
            models.Index(fields=["author", "-created_at"]),
        ]

    def clean(self) -> None:
        if not self.content or not self.content.strip():
            raise ValidationError({"content": "Comment content cannot be empty."})
        if self.parent_id and self.parent.post_id != self.post_id:
            raise ValidationError({"parent": "Reply must belong to the same post."})

    def soft_delete(self) -> None:
        self.is_deleted = True
        self.content = "[deleted]"
        self.save(update_fields=["is_deleted", "content", "updated_at"])

    def __str__(self) -> str:
        return Truncator(self.content).chars(48)


class Reaction(models.Model):
    class Kind(models.TextChoices):
        LIKE = "like", "Like"
        LOVE = "love", "Love"
        SUPPORT = "support", "Support"

    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="reactions")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="reactions",
    )
    kind = models.CharField(max_length=12, choices=Kind.choices, default=Kind.LIKE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["post", "user"],
                name="unique_reaction_per_post_user",
            )
        ]
        indexes = [models.Index(fields=["post", "kind"])]

    def __str__(self) -> str:
        return f"{self.user} {self.kind} {self.post_id}"


class Bookmark(models.Model):
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="bookmarks")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="bookmarks",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["post", "user"],
                name="unique_bookmark_per_post_user",
            )
        ]

    def __str__(self) -> str:
        return f"{self.user} bookmarked {self.post_id}"


class Conversation(models.Model):
    title = models.CharField(max_length=120, blank=True)
    is_group = models.BooleanField(default=False)
    participants = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        through="ConversationParticipant",
        related_name="conversations",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self) -> str:
        return self.title or f"Conversation #{self.pk}"


class ConversationParticipant(models.Model):
    class Role(models.TextChoices):
        OWNER = "owner", "Owner"
        MEMBER = "member", "Member"

    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name="memberships",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="conversation_memberships",
    )
    role = models.CharField(max_length=12, choices=Role.choices, default=Role.MEMBER)
    joined_at = models.DateTimeField(auto_now_add=True)
    last_read_at = models.DateTimeField(null=True, blank=True)
    is_muted = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["conversation", "user"],
                name="unique_conversation_participant",
            )
        ]

    def mark_read(self) -> None:
        self.last_read_at = timezone.now()
        self.save(update_fields=["last_read_at"])

    def __str__(self) -> str:
        return f"{self.user} in {self.conversation_id}"


class Message(models.Model):
    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name="messages",
    )
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="sent_messages",
    )
    body = models.TextField(max_length=4000)
    created_at = models.DateTimeField(auto_now_add=True)
    edited_at = models.DateTimeField(null=True, blank=True)
    is_deleted = models.BooleanField(default=False)

    class Meta:
        ordering = ["created_at"]
        indexes = [
            models.Index(fields=["conversation", "created_at"]),
            models.Index(fields=["sender", "-created_at"]),
        ]

    def clean(self) -> None:
        if not self.body or not self.body.strip():
            raise ValidationError({"body": "Message body cannot be empty."})

    def delete_for_everyone(self) -> None:
        self.is_deleted = True
        self.body = "[deleted]"
        self.save(update_fields=["is_deleted", "body"])

    def __str__(self) -> str:
        return Truncator(self.body).chars(48)


class Notification(models.Model):
    class Verb(models.TextChoices):
        FOLLOWED = "followed", "Followed"
        FOLLOW_REQUESTED = "follow_requested", "Follow requested"
        LIKED = "liked", "Liked"
        COMMENTED = "commented", "Commented"
        MESSAGED = "messaged", "Messaged"

    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="actor_notifications",
    )
    verb = models.CharField(max_length=24, choices=Verb.choices)
    post = models.ForeignKey(
        Post,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="notifications",
    )
    comment = models.ForeignKey(
        Comment,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="notifications",
    )
    message = models.ForeignKey(
        Message,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="notifications",
    )
    text = models.CharField(max_length=255, blank=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["recipient", "is_read", "-created_at"]),
        ]

    def mark_read(self) -> None:
        self.is_read = True
        self.save(update_fields=["is_read"])

    def __str__(self) -> str:
        return f"{self.recipient}: {self.verb}"


class Report(models.Model):
    class Reason(models.TextChoices):
        SPAM = "spam", "Spam"
        ABUSE = "abuse", "Abuse"
        OTHER = "other", "Other"

    reporter = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="reports",
    )
    post = models.ForeignKey(
        Post,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="reports",
    )
    comment = models.ForeignKey(
        Comment,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="reports",
    )
    reason = models.CharField(max_length=20, choices=Reason.choices)
    details = models.TextField(max_length=1000, blank=True)
    is_resolved = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(
                condition=Q(post__isnull=False) | Q(comment__isnull=False),
                name="report_has_target",
            )
        ]

    def __str__(self) -> str:
        target = self.post_id or self.comment_id
        return f"{self.reporter} reported {target}"
