from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.test import TestCase

from social.models import Comment, Follow, Post, Reaction


User = get_user_model()


class ModelIntegrityTests(TestCase):
    def setUp(self):
        self.alice = User.objects.create_user(username="alice", password="pass")
        self.bob = User.objects.create_user(username="bob", password="pass")

    def test_profile_is_created_for_new_user(self):
        self.assertEqual(self.alice.profile.user, self.alice)
        self.assertFalse(self.alice.profile.is_private)

    def test_follow_cannot_target_self(self):
        relation = Follow(follower=self.alice, following=self.alice)
        with self.assertRaises(ValidationError):
            relation.full_clean()

    def test_follow_pair_is_unique(self):
        Follow.objects.create(follower=self.alice, following=self.bob)
        with self.assertRaises(IntegrityError):
            Follow.objects.create(follower=self.alice, following=self.bob)

    def test_empty_post_is_invalid(self):
        post = Post(author=self.alice, content="   ")
        with self.assertRaises(ValidationError):
            post.full_clean()

    def test_reply_must_belong_to_same_post(self):
        first = Post.objects.create(author=self.alice, content="first")
        second = Post.objects.create(author=self.alice, content="second")
        parent = Comment.objects.create(post=first, author=self.bob, content="parent")
        reply = Comment(post=second, author=self.alice, parent=parent, content="reply")

        with self.assertRaises(ValidationError):
            reply.full_clean()

    def test_like_count_is_synced_by_signals(self):
        post = Post.objects.create(author=self.alice, content="hello")

        reaction = Reaction.objects.create(post=post, user=self.bob)
        post.refresh_from_db()
        self.assertEqual(post.like_count, 1)

        reaction.delete()
        post.refresh_from_db()
        self.assertEqual(post.like_count, 0)

    def test_comment_count_ignores_soft_deleted_comments(self):
        post = Post.objects.create(author=self.alice, content="hello")
        comment = Comment.objects.create(post=post, author=self.bob, content="hey")
        post.refresh_from_db()
        self.assertEqual(post.comment_count, 1)

        comment.soft_delete()
        post.refresh_from_db()
        self.assertEqual(post.comment_count, 0)
