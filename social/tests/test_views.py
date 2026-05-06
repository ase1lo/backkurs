from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from social import services
from social.models import Follow, Notification, Post, Reaction


User = get_user_model()


class SocialViewTests(TestCase):
    def setUp(self):
        self.alice = User.objects.create_user(username="alice", password="pass12345")
        self.bob = User.objects.create_user(username="bob", password="pass12345")

    def test_home_shows_public_feed_for_anonymous_user(self):
        services.create_post(author=self.alice, content="public post")
        services.create_post(
            author=self.alice,
            content="followers post",
            visibility=Post.Visibility.FOLLOWERS,
        )

        response = self.client.get(reverse("home"))

        self.assertContains(response, "public post")
        self.assertNotContains(response, "followers post")

    def test_authenticated_user_can_create_post_from_home(self):
        self.client.force_login(self.alice)

        response = self.client.post(
            reverse("home"),
            {
                "content": "New backend post",
                "visibility": Post.Visibility.PUBLIC,
                "tags": "django, tests",
                "image_url": "",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(Post.objects.filter(content="New backend post").exists())

    def test_profile_follow_button_creates_relation(self):
        self.client.force_login(self.bob)

        response = self.client.post(reverse("toggle_follow", args=[self.alice.username]))

        self.assertRedirects(response, reverse("profile_detail", args=[self.alice.username]))
        self.assertTrue(Follow.objects.filter(follower=self.bob, following=self.alice).exists())

    def test_private_profile_follow_request_can_be_approved(self):
        self.alice.profile.is_private = True
        self.alice.profile.save()
        services.follow_user(follower=self.bob, following=self.alice)
        self.client.force_login(self.alice)

        response = self.client.post(reverse("approve_follow", args=[self.bob.username]))

        self.assertRedirects(response, reverse("profile_detail", args=[self.alice.username]))
        self.assertEqual(
            Follow.objects.get(follower=self.bob, following=self.alice).status,
            Follow.Status.ACTIVE,
        )

    def test_post_detail_allows_comment_for_authenticated_user(self):
        post = services.create_post(author=self.alice, content="hello")
        self.client.force_login(self.bob)

        response = self.client.post(reverse("post_detail", args=[post.pk]), {"content": "nice"})

        self.assertRedirects(response, reverse("post_detail", args=[post.pk]))
        post.refresh_from_db()
        self.assertEqual(post.comment_count, 1)

    def test_edit_profile_updates_profile_settings(self):
        self.client.force_login(self.alice)

        response = self.client.post(
            reverse("edit_profile"),
            {
                "display_name": "Alice Dev",
                "bio": "Backend student",
                "location": "Moscow",
                "website": "",
                "avatar_url": "",
                "birth_date": "",
                "is_private": "on",
            },
        )

        self.assertRedirects(response, reverse("profile_detail", args=[self.alice.username]))
        self.alice.profile.refresh_from_db()
        self.assertEqual(self.alice.profile.display_name, "Alice Dev")
        self.assertTrue(self.alice.profile.is_private)

    def test_reaction_endpoint_toggles_like(self):
        post = services.create_post(author=self.alice, content="hello")
        self.client.force_login(self.bob)

        response = self.client.post(
            reverse("toggle_reaction", args=[post.pk]),
            {"kind": Reaction.Kind.LIKE},
        )

        self.assertRedirects(response, reverse("post_detail", args=[post.pk]))
        self.assertEqual(Reaction.objects.filter(post=post, user=self.bob).count(), 1)

    def test_inbox_sends_direct_message(self):
        self.client.force_login(self.alice)

        response = self.client.post(
            reverse("inbox"),
            {"recipient_username": "bob", "body": "hello"},
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(Notification.objects.filter(recipient=self.bob).exists())

    def test_notifications_can_be_marked_as_read(self):
        Notification.objects.create(
            recipient=self.alice,
            actor=self.bob,
            verb=Notification.Verb.FOLLOWED,
            text="followed",
        )
        self.client.force_login(self.alice)

        response = self.client.post(reverse("mark_all_notifications_read"))

        self.assertRedirects(response, reverse("notifications"))
        self.assertFalse(self.alice.notifications.filter(is_read=False).exists())

    def test_search_finds_users_and_posts(self):
        services.create_post(author=self.alice, content="Django backend")

        response = self.client.get(reverse("search"), {"q": "django"})

        self.assertContains(response, "Django backend")
        self.assertContains(response, "@alice")

    def test_tag_page_lists_matching_posts(self):
        post = services.create_post(
            author=self.alice,
            content="tagged post",
            tag_names=["backend"],
        )
        tag = post.tags.get()

        response = self.client.get(reverse("tag_posts", args=[tag.slug]))

        self.assertContains(response, "tagged post")

    def test_api_feed_returns_json(self):
        post = services.create_post(author=self.alice, content="json post")

        response = self.client.get(reverse("api_feed"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["results"][0]["id"], post.pk)

    def test_api_post_detail_respects_visibility(self):
        post = services.create_post(
            author=self.alice,
            content="hidden",
            visibility=Post.Visibility.FOLLOWERS,
        )

        response = self.client.get(reverse("api_post_detail", args=[post.pk]))

        self.assertEqual(response.status_code, 403)
