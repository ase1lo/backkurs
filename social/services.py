from __future__ import annotations

from typing import Iterable

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Count, Q
from django.utils import timezone
from django.utils.text import slugify

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
    Profile,
    Reaction,
    Tag,
)


User = get_user_model()


def ensure_profile(user):
    profile, _ = Profile.objects.get_or_create(user=user)
    return profile


def users_are_blocked(first, second) -> bool:
    return BlockedUser.objects.filter(
        Q(blocker=first, blocked=second) | Q(blocker=second, blocked=first)
    ).exists()


def can_view_post(user, post: Post) -> bool:
    if post.is_archived:
        return getattr(user, "is_authenticated", False) and (
            user == post.author or user.is_staff
        )
    if getattr(user, "is_authenticated", False) and users_are_blocked(user, post.author):
        return False
    if post.visibility == Post.Visibility.PUBLIC:
        return True
    if not getattr(user, "is_authenticated", False):
        return False
    if user == post.author or user.is_staff:
        return True
    if post.visibility == Post.Visibility.FOLLOWERS:
        return Follow.objects.filter(
            follower=user,
            following=post.author,
            status=Follow.Status.ACTIVE,
        ).exists()
    return False


def _normalize_tag_names(tag_names: Iterable[str]) -> list[str]:
    normalized = []
    seen = set()
    for tag_name in tag_names:
        cleaned = tag_name.strip().lower()
        if cleaned and cleaned not in seen:
            normalized.append(cleaned[:50])
            seen.add(cleaned)
    return normalized


def _unique_slug_for_tag(name: str) -> str:
    base_slug = slugify(name, allow_unicode=True)[:50] or "tag"
    slug = base_slug
    suffix = 2
    while Tag.objects.filter(slug=slug).exists():
        tail = f"-{suffix}"
        slug = f"{base_slug[: 60 - len(tail)]}{tail}"
        suffix += 1
    return slug


def _get_or_create_tag(name: str) -> Tag:
    existing = Tag.objects.filter(name__iexact=name).first()
    if existing:
        return existing
    return Tag.objects.create(name=name, slug=_unique_slug_for_tag(name))


@transaction.atomic
def create_post(
    *,
    author,
    content: str,
    visibility: str = Post.Visibility.PUBLIC,
    tag_names: Iterable[str] = (),
    image_url: str = "",
) -> Post:
    post = Post(
        author=author,
        content=content.strip(),
        visibility=visibility,
        image_url=image_url.strip(),
    )
    post.full_clean()
    post.save()
    tags = [_get_or_create_tag(name) for name in _normalize_tag_names(tag_names)]
    if tags:
        post.tags.set(tags)
    return post


@transaction.atomic
def follow_user(*, follower, following) -> Follow:
    ensure_profile(following)
    relation = Follow(follower=follower, following=following)
    relation.clean()
    if users_are_blocked(follower, following):
        raise PermissionDenied("Follow is not allowed between blocked users.")

    status = (
        Follow.Status.PENDING
        if following.profile.is_private
        else Follow.Status.ACTIVE
    )
    relation, created = Follow.objects.get_or_create(
        follower=follower,
        following=following,
        defaults={"status": status},
    )
    if not created and relation.status != status:
        relation.status = status
        relation.save(update_fields=["status", "updated_at"])

    verb = (
        Notification.Verb.FOLLOW_REQUESTED
        if relation.status == Follow.Status.PENDING
        else Notification.Verb.FOLLOWED
    )
    if created:
        Notification.objects.create(
            recipient=following,
            actor=follower,
            verb=verb,
            text=f"{follower.username} wants to follow you",
        )
    return relation


@transaction.atomic
def approve_follow_request(*, owner, follower) -> Follow:
    relation = Follow.objects.get(
        follower=follower,
        following=owner,
        status=Follow.Status.PENDING,
    )
    relation.approve()
    Notification.objects.create(
        recipient=follower,
        actor=owner,
        verb=Notification.Verb.FOLLOWED,
        text=f"{owner.username} approved your follow request",
    )
    return relation


def unfollow_user(*, follower, following) -> int:
    deleted, _ = Follow.objects.filter(follower=follower, following=following).delete()
    return deleted


@transaction.atomic
def block_user(*, blocker, blocked) -> BlockedUser:
    block = BlockedUser(blocker=blocker, blocked=blocked)
    block.clean()
    block, _ = BlockedUser.objects.get_or_create(blocker=blocker, blocked=blocked)
    Follow.objects.filter(
        Q(follower=blocker, following=blocked) | Q(follower=blocked, following=blocker)
    ).delete()
    return block


@transaction.atomic
def toggle_reaction(*, user, post: Post, kind: str = Reaction.Kind.LIKE):
    if not can_view_post(user, post):
        raise PermissionDenied("You cannot react to this post.")

    reaction = Reaction.objects.filter(user=user, post=post).first()
    if reaction and reaction.kind == kind:
        reaction.delete()
        return None, False
    if reaction:
        reaction.kind = kind
        reaction.full_clean()
        reaction.save(update_fields=["kind", "updated_at"])
        return reaction, True

    reaction = Reaction(user=user, post=post, kind=kind)
    reaction.full_clean()
    reaction.save()
    if user != post.author:
        Notification.objects.create(
            recipient=post.author,
            actor=user,
            verb=Notification.Verb.LIKED,
            post=post,
            text=f"{user.username} reacted to your post",
        )
    return reaction, True


@transaction.atomic
def add_comment(*, user, post: Post, content: str, parent: Comment | None = None) -> Comment:
    if not can_view_post(user, post):
        raise PermissionDenied("You cannot comment on this post.")

    comment = Comment(post=post, author=user, content=content.strip(), parent=parent)
    comment.full_clean()
    comment.save()
    recipients = {post.author}
    if parent:
        recipients.add(parent.author)
    recipients.discard(user)
    for recipient in recipients:
        Notification.objects.create(
            recipient=recipient,
            actor=user,
            verb=Notification.Verb.COMMENTED,
            post=post,
            comment=comment,
            text=f"{user.username} commented on a post",
        )
    return comment


@transaction.atomic
def soft_delete_comment(*, user, comment: Comment) -> Comment:
    if user != comment.author and user != comment.post.author and not user.is_staff:
        raise PermissionDenied("You cannot delete this comment.")
    comment.soft_delete()
    return comment


def get_feed_for_user(user):
    return (
        Post.objects.visible_to(user)
        .select_related("author", "author__profile")
        .prefetch_related("tags")
    )


def toggle_bookmark(*, user, post: Post):
    if not can_view_post(user, post):
        raise PermissionDenied("You cannot bookmark this post.")
    bookmark = Bookmark.objects.filter(user=user, post=post).first()
    if bookmark:
        bookmark.delete()
        return None, False
    try:
        return Bookmark.objects.create(user=user, post=post), True
    except IntegrityError:
        return Bookmark.objects.get(user=user, post=post), True


def get_or_create_direct_conversation(*, first, second) -> Conversation:
    if first == second:
        raise ValidationError("Cannot create a direct conversation with yourself.")
    if users_are_blocked(first, second):
        raise PermissionDenied("Messages are not allowed between blocked users.")

    conversation = (
        Conversation.objects.filter(
            is_group=False,
            memberships__user=first,
        )
        .filter(memberships__user=second)
        .annotate(participant_count=Count("memberships", distinct=True))
        .filter(participant_count=2)
        .first()
    )
    if conversation:
        return conversation

    conversation = Conversation.objects.create(is_group=False)
    ConversationParticipant.objects.bulk_create(
        [
            ConversationParticipant(
                conversation=conversation,
                user=first,
                role=ConversationParticipant.Role.OWNER,
            ),
            ConversationParticipant(conversation=conversation, user=second),
        ]
    )
    return conversation


@transaction.atomic
def create_group_conversation(*, owner, users: Iterable, title: str) -> Conversation:
    unique_users = []
    seen = set()
    for user in [owner, *users]:
        if user.pk not in seen:
            unique_users.append(user)
            seen.add(user.pk)
    if len(unique_users) < 2:
        raise ValidationError("Group conversation requires at least two users.")

    conversation = Conversation.objects.create(title=title.strip(), is_group=True)
    ConversationParticipant.objects.bulk_create(
        [
            ConversationParticipant(
                conversation=conversation,
                user=user,
                role=(
                    ConversationParticipant.Role.OWNER
                    if user == owner
                    else ConversationParticipant.Role.MEMBER
                ),
            )
            for user in unique_users
        ]
    )
    return conversation


@transaction.atomic
def send_message_to_conversation(
    *,
    sender,
    conversation: Conversation,
    body: str,
) -> Message:
    if not ConversationParticipant.objects.filter(
        conversation=conversation,
        user=sender,
    ).exists():
        raise PermissionDenied("You are not a participant of this conversation.")

    message = Message(conversation=conversation, sender=sender, body=body.strip())
    message.full_clean()
    message.save()
    Conversation.objects.filter(pk=conversation.pk).update(updated_at=timezone.now())

    recipients = conversation.participants.exclude(pk=sender.pk)
    notifications = [
        Notification(
            recipient=recipient,
            actor=sender,
            verb=Notification.Verb.MESSAGED,
            message=message,
            text=f"{sender.username} sent you a message",
        )
        for recipient in recipients
    ]
    Notification.objects.bulk_create(notifications)
    return message


@transaction.atomic
def send_direct_message(*, sender, recipient, body: str) -> Message:
    conversation = get_or_create_direct_conversation(first=sender, second=recipient)
    return send_message_to_conversation(
        sender=sender,
        conversation=conversation,
        body=body,
    )


def search_users(query: str):
    query = query.strip()
    if not query:
        return User.objects.none()
    return (
        User.objects.filter(
            Q(username__icontains=query)
            | Q(first_name__icontains=query)
            | Q(last_name__icontains=query)
            | Q(profile__display_name__icontains=query)
        )
        .select_related("profile")
        .distinct()
        .order_by("username")
    )


def search_posts(query: str, user):
    query = query.strip()
    if not query:
        return Post.objects.none()
    return get_feed_for_user(user).filter(
        Q(content__icontains=query) | Q(tags__name__icontains=query)
    ).distinct()
