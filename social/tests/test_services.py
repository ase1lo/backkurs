from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase

from social import services
from social.models import (
    Bookmark,
    Conversation,
    Follow,
    Message,
    Notification,
    Post,
    Reaction,
)


User = get_user_model()


class SocialServiceTests(TestCase):
    def setUp(self):
        self.alice = User.objects.create_user(username="alice", password="pass")
        self.bob = User.objects.create_user(username="bob", password="pass")
        self.carol = User.objects.create_user(username="carol", password="pass")

    def test_create_post_strips_content_and_creates_unique_tags(self):
        post = services.create_post(
            author=self.alice,
            content="  Hello world  ",
            tag_names=["Django", "django", "Backend"],
        )

        self.assertEqual(post.content, "Hello world")
        self.assertEqual(list(post.tags.order_by("name").values_list("name", flat=True)), ["backend", "django"])

    def test_public_post_is_visible_to_anonymous_user(self):
        post = services.create_post(author=self.alice, content="public")

        self.assertTrue(services.can_view_post(AnonymousUser(), post))

    def test_followers_only_post_visible_only_to_active_followers(self):
        post = services.create_post(
            author=self.alice,
            content="followers",
            visibility=Post.Visibility.FOLLOWERS,
        )

        self.assertFalse(services.can_view_post(self.bob, post))
        Follow.objects.create(follower=self.bob, following=self.alice)
        self.assertTrue(services.can_view_post(self.bob, post))

    def test_private_profile_creates_pending_follow_request(self):
        self.alice.profile.is_private = True
        self.alice.profile.save()

        relation = services.follow_user(follower=self.bob, following=self.alice)

        self.assertEqual(relation.status, Follow.Status.PENDING)
        self.assertEqual(self.alice.notifications.count(), 1)
        self.assertEqual(
            self.alice.notifications.first().verb,
            Notification.Verb.FOLLOW_REQUESTED,
        )

    def test_private_profile_is_visible_only_to_active_followers(self):
        self.alice.profile.is_private = True
        self.alice.profile.save()

        self.assertFalse(services.can_view_profile(AnonymousUser(), self.alice))
        self.assertFalse(services.can_view_profile(self.bob, self.alice))

        relation = services.follow_user(follower=self.bob, following=self.alice)
        self.assertEqual(relation.status, Follow.Status.PENDING)
        self.assertFalse(services.can_view_profile(self.bob, self.alice))

        relation.approve()
        self.assertTrue(services.can_view_profile(self.bob, self.alice))

    def test_approve_follow_request_activates_relation(self):
        self.alice.profile.is_private = True
        self.alice.profile.save()
        services.follow_user(follower=self.bob, following=self.alice)

        relation = services.approve_follow_request(owner=self.alice, follower=self.bob)

        self.assertEqual(relation.status, Follow.Status.ACTIVE)
        self.assertTrue(
            Notification.objects.filter(
                recipient=self.bob,
                actor=self.alice,
                verb=Notification.Verb.FOLLOWED,
            ).exists()
        )

    def test_block_user_removes_follow_relations_and_prevents_visibility(self):
        post = services.create_post(author=self.alice, content="hello")
        Follow.objects.create(follower=self.bob, following=self.alice)

        services.block_user(blocker=self.alice, blocked=self.bob)

        self.assertFalse(Follow.objects.filter(follower=self.bob, following=self.alice).exists())
        self.assertFalse(services.can_view_post(self.bob, post))

    def test_toggle_reaction_creates_updates_and_removes_reaction(self):
        post = services.create_post(author=self.alice, content="hello")

        reaction, active = services.toggle_reaction(user=self.bob, post=post)
        self.assertTrue(active)
        self.assertEqual(reaction.kind, Reaction.Kind.LIKE)
        self.assertEqual(self.alice.notifications.filter(verb=Notification.Verb.LIKED).count(), 1)

        reaction, active = services.toggle_reaction(
            user=self.bob,
            post=post,
            kind=Reaction.Kind.LOVE,
        )
        self.assertTrue(active)
        self.assertEqual(reaction.kind, Reaction.Kind.LOVE)
        self.assertEqual(Reaction.objects.count(), 1)

        reaction, active = services.toggle_reaction(
            user=self.bob,
            post=post,
            kind=Reaction.Kind.LOVE,
        )
        self.assertFalse(active)
        self.assertIsNone(reaction)
        self.assertEqual(Reaction.objects.count(), 0)

    def test_comment_creates_notification_and_updates_count(self):
        post = services.create_post(author=self.alice, content="hello")

        comment = services.add_comment(user=self.bob, post=post, content="nice")

        post.refresh_from_db()
        self.assertEqual(post.comment_count, 1)
        self.assertEqual(comment.author, self.bob)
        self.assertTrue(self.alice.notifications.filter(verb=Notification.Verb.COMMENTED).exists())

    def test_hidden_post_cannot_be_reacted_to_by_non_follower(self):
        post = services.create_post(
            author=self.alice,
            content="hidden",
            visibility=Post.Visibility.FOLLOWERS,
        )

        with self.assertRaises(PermissionDenied):
            services.toggle_reaction(user=self.bob, post=post)

    def test_search_posts_respects_feed_visibility(self):
        services.create_post(
            author=self.alice,
            content="secret django",
            visibility=Post.Visibility.FOLLOWERS,
        )

        self.assertEqual(services.search_posts("django", self.bob).count(), 0)
        Follow.objects.create(follower=self.bob, following=self.alice)
        self.assertEqual(services.search_posts("django", self.bob).count(), 1)

    def test_public_posts_from_private_profiles_require_profile_access(self):
        self.alice.profile.is_private = True
        self.alice.profile.save()
        post = services.create_post(author=self.alice, content="profile secret")

        self.assertFalse(services.can_view_post(self.bob, post))
        self.assertEqual(services.get_feed_for_user(self.bob).count(), 0)

        Follow.objects.create(follower=self.bob, following=self.alice)
        self.assertTrue(services.can_view_post(self.bob, post))
        self.assertEqual(services.get_feed_for_user(self.bob).count(), 1)

    def test_soft_delete_comment_requires_permission(self):
        post = services.create_post(author=self.alice, content="hello")
        comment = services.add_comment(user=self.bob, post=post, content="nice")

        with self.assertRaises(PermissionDenied):
            services.soft_delete_comment(user=self.carol, comment=comment)

        services.soft_delete_comment(user=self.alice, comment=comment)
        comment.refresh_from_db()
        self.assertTrue(comment.is_deleted)

    def test_toggle_bookmark_is_idempotent(self):
        post = services.create_post(author=self.alice, content="hello")

        _, active = services.toggle_bookmark(user=self.bob, post=post)
        self.assertTrue(active)
        self.assertEqual(Bookmark.objects.count(), 1)

        _, active = services.toggle_bookmark(user=self.bob, post=post)
        self.assertFalse(active)
        self.assertEqual(Bookmark.objects.count(), 0)

    def test_direct_message_creates_conversation_and_notifications(self):
        message = services.send_direct_message(
            sender=self.alice,
            recipient=self.bob,
            body="Hello Bob",
        )

        self.assertEqual(Conversation.objects.count(), 1)
        self.assertEqual(Message.objects.count(), 1)
        self.assertEqual(message.conversation.participants.count(), 2)
        self.assertTrue(self.bob.notifications.filter(verb=Notification.Verb.MESSAGED).exists())

    def test_blocked_users_cannot_send_direct_messages(self):
        services.block_user(blocker=self.alice, blocked=self.bob)

        with self.assertRaises(PermissionDenied):
            services.send_direct_message(
                sender=self.bob,
                recipient=self.alice,
                body="hello",
            )

    def test_direct_conversation_with_self_is_invalid(self):
        with self.assertRaises(ValidationError):
            services.get_or_create_direct_conversation(first=self.alice, second=self.alice)
