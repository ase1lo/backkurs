from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from social import services
from social.models import (
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
    Report,
    Tag,
)


User = get_user_model()


class ProfileSerializer(serializers.ModelSerializer):
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
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at"]


class UserPublicSerializer(serializers.ModelSerializer):
    profile = ProfileSerializer(read_only=True)
    followers_count = serializers.IntegerField(read_only=True)
    following_count = serializers.IntegerField(read_only=True)
    posts_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "first_name",
            "last_name",
            "profile",
            "followers_count",
            "following_count",
            "posts_count",
            "date_joined",
        ]
        read_only_fields = fields

    def to_representation(self, instance):
        services.ensure_profile(instance)
        data = super().to_representation(instance)
        request = self.context.get("request")
        if request and not services.can_view_profile(request.user, instance):
            data["first_name"] = ""
            data["last_name"] = ""
            data["followers_count"] = None
            data["following_count"] = None
            data["posts_count"] = None
            data["profile"] = {
                "display_name": "",
                "bio": "",
                "location": "",
                "website": "",
                "avatar_url": "",
                "birth_date": None,
                "is_private": instance.profile.is_private,
                "created_at": data["profile"].get("created_at"),
                "updated_at": data["profile"].get("updated_at"),
            }
        return data


class UserMeSerializer(serializers.ModelSerializer):
    profile = ProfileSerializer()

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "first_name",
            "last_name",
            "email",
            "profile",
            "date_joined",
        ]
        read_only_fields = ["id", "username", "date_joined"]

    def update(self, instance, validated_data):
        profile_data = validated_data.pop("profile", None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if profile_data is not None:
            profile = services.ensure_profile(instance)
            for attr, value in profile_data.items():
                setattr(profile, attr, value)
            profile.save()
        return instance


class RegisterSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150)
    password = serializers.CharField(write_only=True, style={"input_type": "password"})
    email = serializers.EmailField(required=False, allow_blank=True)
    first_name = serializers.CharField(required=False, allow_blank=True, max_length=150)
    last_name = serializers.CharField(required=False, allow_blank=True, max_length=150)

    def validate_username(self, value):
        if User.objects.filter(username=value).exists():
            raise serializers.ValidationError("Пользователь с таким username уже есть.")
        return value

    def validate_password(self, value):
        validate_password(value)
        return value

    def create(self, validated_data):
        password = validated_data.pop("password")
        user = User(**validated_data)
        user.set_password(password)
        user.save()
        services.ensure_profile(user)
        return user


class TokenResponseSerializer(serializers.Serializer):
    token = serializers.CharField()
    user = UserPublicSerializer()


class TagSerializer(serializers.ModelSerializer):
    posts_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Tag
        fields = ["id", "name", "slug", "posts_count", "created_at"]
        read_only_fields = ["id", "slug", "posts_count", "created_at"]


class PostSerializer(serializers.ModelSerializer):
    author = UserPublicSerializer(read_only=True)
    tags = TagSerializer(many=True, read_only=True)
    tag_names = serializers.ListField(
        child=serializers.CharField(max_length=50),
        write_only=True,
        required=False,
        help_text="Список тегов без символа #.",
    )
    user_reaction = serializers.SerializerMethodField()
    is_bookmarked = serializers.SerializerMethodField()

    class Meta:
        model = Post
        fields = [
            "id",
            "author",
            "content",
            "visibility",
            "tags",
            "tag_names",
            "image_url",
            "like_count",
            "comment_count",
            "share_count",
            "is_pinned",
            "is_archived",
            "user_reaction",
            "is_bookmarked",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "author",
            "tags",
            "like_count",
            "comment_count",
            "share_count",
            "is_pinned",
            "is_archived",
            "user_reaction",
            "is_bookmarked",
            "created_at",
            "updated_at",
        ]

    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_user_reaction(self, obj):
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return None
        reaction = obj.reactions.filter(user=request.user).first()
        return reaction.kind if reaction else None

    @extend_schema_field(serializers.BooleanField())
    def get_is_bookmarked(self, obj):
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return False
        return obj.bookmarks.filter(user=request.user).exists()

    def create(self, validated_data):
        tag_names = validated_data.pop("tag_names", [])
        request = self.context["request"]
        return services.create_post(
            author=request.user,
            tag_names=tag_names,
            **validated_data,
        )

    def update(self, instance, validated_data):
        tag_names = validated_data.pop("tag_names", None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.full_clean()
        instance.save()
        if tag_names is not None:
            instance.tags.set(services.resolve_tags(tag_names))
        return instance


class PostCreateExampleSerializer(serializers.Serializer):
    content = serializers.CharField()
    visibility = serializers.ChoiceField(choices=Post.Visibility.choices)
    tag_names = serializers.ListField(child=serializers.CharField(), required=False)
    image_url = serializers.URLField(required=False, allow_blank=True)


class ReactionSerializer(serializers.ModelSerializer):
    user = UserPublicSerializer(read_only=True)

    class Meta:
        model = Reaction
        fields = ["id", "post", "user", "kind", "created_at", "updated_at"]
        read_only_fields = ["id", "post", "user", "created_at", "updated_at"]


class ReactionRequestSerializer(serializers.Serializer):
    kind = serializers.ChoiceField(
        choices=Reaction.Kind.choices,
        default=Reaction.Kind.LIKE,
    )


class ReactionResultSerializer(serializers.Serializer):
    active = serializers.BooleanField()
    reaction = ReactionSerializer(allow_null=True)


class CommentShortSerializer(serializers.ModelSerializer):
    author = UserPublicSerializer(read_only=True)

    class Meta:
        model = Comment
        fields = ["id", "author", "content", "is_deleted", "created_at"]
        read_only_fields = fields


class CommentSerializer(serializers.ModelSerializer):
    author = UserPublicSerializer(read_only=True)
    replies = serializers.SerializerMethodField()

    class Meta:
        model = Comment
        fields = [
            "id",
            "post",
            "author",
            "parent",
            "content",
            "is_deleted",
            "replies",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "author", "is_deleted", "replies", "created_at", "updated_at"]

    @extend_schema_field(CommentShortSerializer(many=True))
    def get_replies(self, obj):
        replies = obj.replies.select_related("author", "author__profile").all()
        return CommentShortSerializer(replies, many=True, context=self.context).data

    def validate(self, attrs):
        request = self.context["request"]
        post = attrs.get("post") or getattr(self.instance, "post", None)
        parent = attrs.get("parent")
        if post and not services.can_view_post(request.user, post):
            raise serializers.ValidationError("Нет доступа к публикации.")
        if parent and post and parent.post_id != post.pk:
            raise serializers.ValidationError("Ответ должен относиться к той же публикации.")
        return attrs

    def create(self, validated_data):
        request = self.context["request"]
        return services.add_comment(
            user=request.user,
            post=validated_data["post"],
            content=validated_data["content"],
            parent=validated_data.get("parent"),
        )


class BookmarkSerializer(serializers.ModelSerializer):
    post = PostSerializer(read_only=True)

    class Meta:
        model = Bookmark
        fields = ["id", "post", "created_at"]
        read_only_fields = fields


class BookmarkResultSerializer(serializers.Serializer):
    active = serializers.BooleanField()
    bookmark_id = serializers.IntegerField(allow_null=True)


class FollowSerializer(serializers.ModelSerializer):
    follower = UserPublicSerializer(read_only=True)
    following = UserPublicSerializer(read_only=True)

    class Meta:
        model = Follow
        fields = ["id", "follower", "following", "status", "created_at", "updated_at"]
        read_only_fields = fields


class BlockedUserSerializer(serializers.ModelSerializer):
    blocker = UserPublicSerializer(read_only=True)
    blocked = UserPublicSerializer(read_only=True)

    class Meta:
        model = BlockedUser
        fields = ["id", "blocker", "blocked", "created_at"]
        read_only_fields = fields


class NotificationSerializer(serializers.ModelSerializer):
    actor = UserPublicSerializer(read_only=True)

    class Meta:
        model = Notification
        fields = [
            "id",
            "actor",
            "verb",
            "post",
            "comment",
            "message",
            "text",
            "is_read",
            "created_at",
        ]
        read_only_fields = fields


class ConversationParticipantSerializer(serializers.ModelSerializer):
    user = UserPublicSerializer(read_only=True)

    class Meta:
        model = ConversationParticipant
        fields = ["user", "role", "joined_at", "last_read_at", "is_muted"]
        read_only_fields = fields


class MessageSerializer(serializers.ModelSerializer):
    sender = UserPublicSerializer(read_only=True)

    class Meta:
        model = Message
        fields = [
            "id",
            "conversation",
            "sender",
            "body",
            "created_at",
            "edited_at",
            "is_deleted",
        ]
        read_only_fields = ["id", "sender", "created_at", "edited_at", "is_deleted"]

    def validate(self, attrs):
        request = self.context["request"]
        conversation = attrs.get("conversation") or getattr(self.instance, "conversation", None)
        if conversation and not conversation.participants.filter(pk=request.user.pk).exists():
            raise serializers.ValidationError("Вы не участвуете в этом диалоге.")
        return attrs

    def create(self, validated_data):
        request = self.context["request"]
        return services.send_message_to_conversation(sender=request.user, **validated_data)


class MessageCreateSerializer(serializers.Serializer):
    body = serializers.CharField(max_length=4000)


class ConversationSerializer(serializers.ModelSerializer):
    participants = ConversationParticipantSerializer(
        source="memberships",
        many=True,
        read_only=True,
    )
    last_message = serializers.SerializerMethodField()
    message_count = serializers.SerializerMethodField()

    class Meta:
        model = Conversation
        fields = [
            "id",
            "title",
            "is_group",
            "participants",
            "message_count",
            "last_message",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "is_group",
            "participants",
            "message_count",
            "last_message",
            "created_at",
            "updated_at",
        ]

    @extend_schema_field(MessageSerializer(allow_null=True))
    def get_last_message(self, obj):
        message = obj.messages.order_by("-created_at").first()
        if not message:
            return None
        return MessageSerializer(message, context=self.context).data

    @extend_schema_field(serializers.IntegerField())
    def get_message_count(self, obj):
        return getattr(obj, "message_count", obj.messages.count())


class DirectConversationSerializer(serializers.Serializer):
    recipient_username = serializers.CharField(max_length=150)
    body = serializers.CharField(required=False, allow_blank=True, max_length=4000)

    def validate_recipient_username(self, value):
        try:
            return User.objects.get(username=value)
        except User.DoesNotExist as exc:
            raise serializers.ValidationError("Пользователь не найден.") from exc


class GroupConversationSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=120)
    usernames = serializers.ListField(
        child=serializers.CharField(max_length=150),
        min_length=1,
    )

    def validate_usernames(self, value):
        users = list(User.objects.filter(username__in=value))
        found = {user.username for user in users}
        missing = sorted(set(value) - found)
        if missing:
            raise serializers.ValidationError(f"Пользователи не найдены: {', '.join(missing)}.")
        return users


class ReportSerializer(serializers.ModelSerializer):
    reporter = UserPublicSerializer(read_only=True)

    class Meta:
        model = Report
        fields = [
            "id",
            "reporter",
            "post",
            "comment",
            "reason",
            "details",
            "is_resolved",
            "created_at",
        ]
        read_only_fields = ["id", "reporter", "is_resolved", "created_at"]

    def validate(self, attrs):
        if not attrs.get("post") and not attrs.get("comment"):
            raise serializers.ValidationError("Нужно указать публикацию или комментарий.")
        return attrs

    def create(self, validated_data):
        request = self.context["request"]
        report = Report(reporter=request.user, **validated_data)
        report.full_clean()
        report.save()
        return report
