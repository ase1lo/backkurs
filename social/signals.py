from django.contrib.auth import get_user_model
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from .models import Comment, Post, Profile, Reaction


User = get_user_model()


@receiver(post_save, sender=User)
def ensure_profile(sender, instance, created, **kwargs) -> None:
    if created:
        Profile.objects.create(user=instance)


def _sync_like_count(post_id: int) -> None:
    Post.objects.filter(pk=post_id).update(
        like_count=Reaction.objects.filter(post_id=post_id).count()
    )


def _sync_comment_count(post_id: int) -> None:
    Post.objects.filter(pk=post_id).update(
        comment_count=Comment.objects.filter(post_id=post_id, is_deleted=False).count()
    )


@receiver(post_save, sender=Reaction)
def reaction_saved(sender, instance, **kwargs) -> None:
    _sync_like_count(instance.post_id)


@receiver(post_delete, sender=Reaction)
def reaction_deleted(sender, instance, **kwargs) -> None:
    _sync_like_count(instance.post_id)


@receiver(post_save, sender=Comment)
def comment_saved(sender, instance, **kwargs) -> None:
    _sync_comment_count(instance.post_id)


@receiver(post_delete, sender=Comment)
def comment_deleted(sender, instance, **kwargs) -> None:
    _sync_comment_count(instance.post_id)
