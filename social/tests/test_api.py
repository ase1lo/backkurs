from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from social import services
from social.models import Bookmark, Comment, Follow, Notification, Post, Reaction, Report


User = get_user_model()


class SocialApiTests(APITestCase):
    def setUp(self):
        self.alice = User.objects.create_user(username="alice", password="password123")
        self.bob = User.objects.create_user(username="bob", password="password123")
        self.carol = User.objects.create_user(username="carol", password="password123")

    def authenticate(self, user):
        token, _ = Token.objects.get_or_create(user=user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")

    def test_register_returns_token_and_user(self):
        response = self.client.post(
            "/api/v1/auth/register/",
            {
                "username": "student",
                "password": "StrongPassword123",
                "email": "student@example.com",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertIn("token", response.data)
        self.assertEqual(response.data["user"]["username"], "student")

    def test_token_login_returns_existing_user(self):
        response = self.client.post(
            "/api/v1/auth/token/",
            {"username": "alice", "password": "password123"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("token", response.data)
        self.assertEqual(response.data["user"]["username"], "alice")

    def test_me_endpoint_updates_nested_profile(self):
        self.authenticate(self.alice)

        response = self.client.patch(
            "/api/v1/auth/me/",
            {
                "first_name": "Alice",
                "profile": {
                    "display_name": "Alice Dev",
                    "bio": "Backend",
                    "is_private": True,
                },
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.alice.refresh_from_db()
        self.alice.profile.refresh_from_db()
        self.assertEqual(self.alice.first_name, "Alice")
        self.assertTrue(self.alice.profile.is_private)

    def test_api_docs_and_schema_are_available(self):
        schema_response = self.client.get("/api/schema/")
        swagger_response = self.client.get("/api/docs/")
        redoc_response = self.client.get("/api/redoc/")

        self.assertEqual(schema_response.status_code, 200)
        self.assertEqual(swagger_response.status_code, 200)
        self.assertEqual(redoc_response.status_code, 200)

    def test_post_api_creates_publication_with_tags(self):
        self.authenticate(self.alice)

        response = self.client.post(
            "/api/v1/posts/",
            {
                "content": "API post",
                "visibility": Post.Visibility.PUBLIC,
                "tag_names": ["django", "api"],
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["content"], "API post")
        self.assertEqual(Post.objects.get().tags.count(), 2)

    def test_feed_respects_followers_only_visibility(self):
        services.create_post(author=self.alice, content="public")
        services.create_post(
            author=self.alice,
            content="hidden",
            visibility=Post.Visibility.FOLLOWERS,
        )

        anonymous_response = self.client.get("/api/v1/posts/")
        self.assertContains(anonymous_response, "public")
        self.assertNotContains(anonymous_response, "hidden")

        Follow.objects.create(follower=self.bob, following=self.alice)
        self.authenticate(self.bob)
        follower_response = self.client.get("/api/v1/posts/")
        self.assertContains(follower_response, "hidden")

    def test_user_actions_follow_approve_and_block(self):
        self.alice.profile.is_private = True
        self.alice.profile.save()
        self.authenticate(self.bob)

        follow_response = self.client.post("/api/v1/users/alice/follow/")
        self.assertEqual(follow_response.status_code, 200)
        self.assertEqual(follow_response.data["status"], Follow.Status.PENDING)

        self.authenticate(self.alice)
        approve_response = self.client.post("/api/v1/users/bob/approve-follow-request/")
        self.assertEqual(approve_response.status_code, 200)
        self.assertEqual(approve_response.data["status"], Follow.Status.ACTIVE)

        block_response = self.client.post("/api/v1/users/bob/block/")
        self.assertEqual(block_response.status_code, 200)
        self.assertFalse(Follow.objects.filter(follower=self.bob, following=self.alice).exists())

    def test_reaction_bookmark_and_comment_actions(self):
        post = services.create_post(author=self.alice, content="hello")
        self.authenticate(self.bob)

        reaction_response = self.client.post(
            f"/api/v1/posts/{post.pk}/react/",
            {"kind": Reaction.Kind.LOVE},
            format="json",
        )
        bookmark_response = self.client.post(f"/api/v1/posts/{post.pk}/bookmark/")
        comment_response = self.client.post(
            "/api/v1/comments/",
            {"post": post.pk, "content": "nice"},
            format="json",
        )

        self.assertEqual(reaction_response.status_code, 200)
        self.assertTrue(reaction_response.data["active"])
        self.assertEqual(bookmark_response.status_code, 200)
        self.assertTrue(bookmark_response.data["active"])
        self.assertEqual(comment_response.status_code, 201)
        self.assertEqual(Reaction.objects.count(), 1)
        self.assertEqual(Bookmark.objects.count(), 1)
        self.assertEqual(Comment.objects.count(), 1)

    def test_notifications_can_be_read_via_api(self):
        Notification.objects.create(
            recipient=self.alice,
            actor=self.bob,
            verb=Notification.Verb.FOLLOWED,
            text="Bob followed you",
        )
        self.authenticate(self.alice)

        list_response = self.client.get("/api/v1/notifications/?unread=true")
        read_all_response = self.client.post("/api/v1/notifications/read-all/")

        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(list_response.data["count"], 1)
        self.assertEqual(read_all_response.status_code, 200)
        self.assertEqual(read_all_response.data["updated"], 1)

    def test_direct_conversation_and_messages(self):
        self.authenticate(self.alice)

        direct_response = self.client.post(
            "/api/v1/conversations/direct/",
            {"recipient_username": "bob", "body": "Hello Bob"},
            format="json",
        )
        conversation_id = direct_response.data["id"]
        message_response = self.client.post(
            f"/api/v1/conversations/{conversation_id}/messages/",
            {"body": "Second message"},
            format="json",
        )

        self.assertEqual(direct_response.status_code, 200)
        self.assertEqual(message_response.status_code, 201)
        self.assertEqual(direct_response.data["message_count"], 1)

    def test_report_post(self):
        post = services.create_post(author=self.alice, content="spam")
        self.authenticate(self.bob)

        response = self.client.post(
            "/api/v1/reports/",
            {"post": post.pk, "reason": Report.Reason.SPAM, "details": "Looks like spam"},
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(Report.objects.count(), 1)
