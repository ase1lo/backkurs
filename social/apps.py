from django.apps import AppConfig


class SocialConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "social"
    verbose_name = "Social network"

    def ready(self) -> None:
        from . import signals  # noqa: F401
