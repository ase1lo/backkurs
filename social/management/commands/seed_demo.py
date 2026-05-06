from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from social import services
from social.models import Follow, Post


class Command(BaseCommand):
    help = "Create demo users, posts, follows and messages."

    def handle(self, *args, **options):
        User = get_user_model()
        users = {}
        for username in ["alice", "bob", "carol"]:
            user, created = User.objects.get_or_create(username=username)
            if created:
                user.set_password("password123")
                user.save(update_fields=["password"])
            services.ensure_profile(user)
            user.profile.display_name = username.title()
            user.profile.bio = f"Demo profile for {username}."
            user.profile.save()
            users[username] = user

        users["carol"].profile.is_private = True
        users["carol"].profile.save(update_fields=["is_private"])

        if not Post.objects.filter(author=users["alice"]).exists():
            services.create_post(
                author=users["alice"],
                content="Hello from the demo social network backend.",
                tag_names=["django", "backend"],
            )
            services.create_post(
                author=users["bob"],
                content="Followers-only post with privacy rules.",
                visibility=Post.Visibility.FOLLOWERS,
                tag_names=["privacy"],
            )

        if not Follow.objects.filter(follower=users["alice"], following=users["bob"]).exists():
            services.follow_user(follower=users["alice"], following=users["bob"])
        if not Follow.objects.filter(follower=users["bob"], following=users["alice"]).exists():
            services.follow_user(follower=users["bob"], following=users["alice"])

        if not users["bob"].sent_messages.exists():
            services.send_direct_message(
                sender=users["bob"],
                recipient=users["alice"],
                body="Demo direct message.",
            )

        self.stdout.write(self.style.SUCCESS("Demo data created. Password: password123"))
