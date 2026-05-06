from django import forms
from django.contrib.auth import get_user_model

from . import services
from .models import Comment, Message, Post, Profile, Reaction


User = get_user_model()


class PostForm(forms.Form):
    content = forms.CharField(
        label="Текст публикации",
        widget=forms.Textarea(attrs={"rows": 4, "placeholder": "Что нового?"}),
        max_length=5000,
    )
    visibility = forms.ChoiceField(
        label="Доступ",
        choices=Post.Visibility.choices,
        initial=Post.Visibility.PUBLIC,
    )
    tags = forms.CharField(
        label="Теги",
        required=False,
        help_text="Через запятую",
    )
    image_url = forms.URLField(label="Ссылка на изображение", required=False)

    def save(self, *, author):
        return services.create_post(
            author=author,
            content=self.cleaned_data["content"],
            visibility=self.cleaned_data["visibility"],
            tag_names=self.cleaned_data["tags"].split(","),
            image_url=self.cleaned_data["image_url"],
        )


class CommentForm(forms.ModelForm):
    class Meta:
        model = Comment
        fields = ["content"]
        labels = {"content": "Комментарий"}
        widgets = {
            "content": forms.Textarea(
                attrs={"rows": 3, "placeholder": "Написать комментарий"}
            )
        }


class ProfileForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = [
            "display_name",
            "bio",
            "location",
            "website",
            "avatar_url",
            "birth_date",
            "is_private",
        ]
        labels = {
            "display_name": "Отображаемое имя",
            "bio": "О себе",
            "location": "Город",
            "website": "Сайт",
            "avatar_url": "Ссылка на аватар",
            "birth_date": "Дата рождения",
            "is_private": "Закрытый профиль",
        }
        widgets = {
            "bio": forms.Textarea(attrs={"rows": 4}),
            "birth_date": forms.DateInput(attrs={"type": "date"}),
        }


class ReactionForm(forms.Form):
    kind = forms.ChoiceField(choices=Reaction.Kind.choices, initial=Reaction.Kind.LIKE)


class DirectMessageForm(forms.Form):
    recipient_username = forms.CharField(label="Получатель", max_length=150)
    body = forms.CharField(
        label="Сообщение",
        widget=forms.Textarea(attrs={"rows": 4}),
        max_length=4000,
    )

    def clean_recipient_username(self):
        username = self.cleaned_data["recipient_username"]
        try:
            return User.objects.get(username=username)
        except User.DoesNotExist as exc:
            raise forms.ValidationError("Пользователь не найден.") from exc

    def save(self, *, sender):
        return services.send_direct_message(
            sender=sender,
            recipient=self.cleaned_data["recipient_username"],
            body=self.cleaned_data["body"],
        )


class ConversationMessageForm(forms.ModelForm):
    class Meta:
        model = Message
        fields = ["body"]
        labels = {"body": "Сообщение"}
        widgets = {
            "body": forms.Textarea(attrs={"rows": 3, "placeholder": "Введите текст"})
        }
