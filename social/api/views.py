from django.contrib.auth import get_user_model
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import (
    OpenApiExample,
    OpenApiParameter,
    OpenApiResponse,
    extend_schema,
    extend_schema_view,
)
from rest_framework import mixins, status, viewsets
from rest_framework.authtoken.models import Token
from rest_framework.authtoken.serializers import AuthTokenSerializer
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import AllowAny, IsAuthenticated, IsAuthenticatedOrReadOnly
from rest_framework.response import Response
from rest_framework.views import APIView

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
    Report,
    Tag,
)

from .serializers import (
    BlockedUserSerializer,
    BookmarkResultSerializer,
    BookmarkSerializer,
    CommentSerializer,
    ConversationSerializer,
    DirectConversationSerializer,
    FollowSerializer,
    GroupConversationSerializer,
    MessageSerializer,
    MessageCreateSerializer,
    NotificationSerializer,
    PostCreateExampleSerializer,
    PostSerializer,
    ReactionRequestSerializer,
    ReactionResultSerializer,
    ReactionSerializer,
    RegisterSerializer,
    ReportSerializer,
    TagSerializer,
    TokenResponseSerializer,
    UserMeSerializer,
    UserPublicSerializer,
)


User = get_user_model()


def _user_queryset():
    return (
        User.objects.select_related("profile")
        .annotate(
            followers_count=Count(
                "follower_relations",
                filter=Q(follower_relations__status=Follow.Status.ACTIVE),
                distinct=True,
            ),
            following_count=Count(
                "following_relations",
                filter=Q(following_relations__status=Follow.Status.ACTIVE),
                distinct=True,
            ),
            posts_count=Count("posts", filter=Q(posts__is_archived=False), distinct=True),
        )
        .order_by("username")
    )


class IsAuthorOrReadOnly(IsAuthenticatedOrReadOnly):
    def has_object_permission(self, request, view, obj):
        if request.method in ("GET", "HEAD", "OPTIONS"):
            return True
        return obj.author == request.user or request.user.is_staff


class IsParticipant(IsAuthenticated):
    def has_object_permission(self, request, view, obj):
        if isinstance(obj, Conversation):
            return obj.participants.filter(pk=request.user.pk).exists()
        if isinstance(obj, Message):
            return obj.conversation.participants.filter(pk=request.user.pk).exists()
        return True


@extend_schema(tags=["Auth"])
class RegisterAPIView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        summary="Регистрация пользователя",
        description="Создает пользователя, профиль и возвращает token для авторизации в API.",
        request=RegisterSerializer,
        responses={201: TokenResponseSerializer},
        examples=[
            OpenApiExample(
                "Новый пользователь",
                value={
                    "username": "student",
                    "password": "StrongPassword123",
                    "email": "student@example.com",
                    "first_name": "Никита",
                    "last_name": "Червов",
                },
                request_only=True,
            )
        ],
    )
    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        token, _ = Token.objects.get_or_create(user=user)
        return Response(
            {"token": token.key, "user": UserPublicSerializer(user).data},
            status=status.HTTP_201_CREATED,
        )


@extend_schema(tags=["Auth"])
class TokenLoginAPIView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        summary="Получить token",
        description="Возвращает token по username и password. Для Postman используйте Authorization: Token <token>.",
        request=AuthTokenSerializer,
        responses={200: TokenResponseSerializer},
        examples=[
            OpenApiExample(
                "Демо-пользователь",
                value={"username": "alice", "password": "password123"},
                request_only=True,
            )
        ],
    )
    def post(self, request):
        serializer = AuthTokenSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]
        token, _ = Token.objects.get_or_create(user=user)
        return Response({"token": token.key, "user": UserPublicSerializer(user).data})


@extend_schema(tags=["Auth"])
class LogoutAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Удалить текущий token",
        request=None,
        responses={204: OpenApiResponse(description="Token удален.")},
    )
    def post(self, request):
        Token.objects.filter(user=request.user).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


@extend_schema(tags=["Auth"])
class MeAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(summary="Текущий пользователь", responses=UserMeSerializer)
    def get(self, request):
        return Response(UserMeSerializer(request.user, context={"request": request}).data)

    @extend_schema(
        summary="Обновить текущего пользователя и профиль",
        request=UserMeSerializer,
        responses=UserMeSerializer,
    )
    def patch(self, request):
        serializer = UserMeSerializer(
            request.user,
            data=request.data,
            partial=True,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


@extend_schema_view(
    list=extend_schema(
        tags=["Users"],
        summary="Список пользователей",
        parameters=[
            OpenApiParameter("search", str, description="Поиск по username, имени и профилю."),
        ],
    ),
    retrieve=extend_schema(tags=["Users"], summary="Профиль пользователя"),
)
class UserViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = UserPublicSerializer
    lookup_field = "username"

    def get_queryset(self):
        queryset = _user_queryset()
        query = self.request.query_params.get("search", "").strip()
        if query:
            queryset = queryset.filter(
                Q(username__icontains=query)
                | Q(first_name__icontains=query)
                | Q(last_name__icontains=query)
                | Q(profile__display_name__icontains=query)
            )
        return queryset

    @extend_schema(tags=["Users"], summary="Подписаться или отправить заявку")
    @action(detail=True, methods=["post"], permission_classes=[IsAuthenticated])
    def follow(self, request, username=None):
        target = self.get_object()
        relation = services.follow_user(follower=request.user, following=target)
        return Response(FollowSerializer(relation, context={"request": request}).data)

    @extend_schema(tags=["Users"], summary="Отписаться")
    @action(detail=True, methods=["delete"], permission_classes=[IsAuthenticated])
    def unfollow(self, request, username=None):
        target = self.get_object()
        services.unfollow_user(follower=request.user, following=target)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @extend_schema(tags=["Users"], summary="Заблокировать пользователя", responses=BlockedUserSerializer)
    @action(detail=True, methods=["post"], permission_classes=[IsAuthenticated])
    def block(self, request, username=None):
        target = self.get_object()
        block = services.block_user(blocker=request.user, blocked=target)
        return Response(BlockedUserSerializer(block, context={"request": request}).data)

    @extend_schema(tags=["Users"], summary="Одобрить заявку на подписку")
    @action(
        detail=True,
        methods=["post"],
        url_path="approve-follow-request",
        permission_classes=[IsAuthenticated],
    )
    def approve_follow_request(self, request, username=None):
        follower = self.get_object()
        relation = services.approve_follow_request(owner=request.user, follower=follower)
        return Response(FollowSerializer(relation, context={"request": request}).data)

    @extend_schema(tags=["Users"], summary="Подписчики пользователя")
    @action(detail=True, methods=["get"])
    def followers(self, request, username=None):
        user = self.get_object()
        relations = Follow.objects.filter(
            following=user,
            status=Follow.Status.ACTIVE,
        ).select_related("follower", "follower__profile")
        page = self.paginate_queryset(relations)
        serializer = FollowSerializer(page or relations, many=True, context={"request": request})
        if page is not None:
            return self.get_paginated_response(serializer.data)
        return Response(serializer.data)

    @extend_schema(tags=["Users"], summary="Подписки пользователя")
    @action(detail=True, methods=["get"])
    def following(self, request, username=None):
        user = self.get_object()
        relations = Follow.objects.filter(
            follower=user,
            status=Follow.Status.ACTIVE,
        ).select_related("following", "following__profile")
        page = self.paginate_queryset(relations)
        serializer = FollowSerializer(page or relations, many=True, context={"request": request})
        if page is not None:
            return self.get_paginated_response(serializer.data)
        return Response(serializer.data)


@extend_schema_view(
    list=extend_schema(
        tags=["Posts"],
        summary="Лента публикаций",
        parameters=[
            OpenApiParameter("search", str, description="Поиск по тексту и тегам."),
            OpenApiParameter("tag", str, description="Фильтр по slug тега."),
            OpenApiParameter("author", str, description="Фильтр по username автора."),
        ],
    ),
    retrieve=extend_schema(tags=["Posts"], summary="Публикация"),
    create=extend_schema(
        tags=["Posts"],
        summary="Создать публикацию",
        request=PostCreateExampleSerializer,
        responses={201: PostSerializer},
        examples=[
            OpenApiExample(
                "Публикация с тегами",
                value={
                    "content": "Разрабатываю backend социальной сети на Django.",
                    "visibility": "public",
                    "tag_names": ["django", "backend", "coursework"],
                    "image_url": "",
                },
                request_only=True,
            )
        ],
    ),
    update=extend_schema(tags=["Posts"], summary="Полностью обновить публикацию"),
    partial_update=extend_schema(tags=["Posts"], summary="Частично обновить публикацию"),
    destroy=extend_schema(tags=["Posts"], summary="Архивировать публикацию"),
)
class PostViewSet(viewsets.ModelViewSet):
    serializer_class = PostSerializer
    permission_classes = [IsAuthorOrReadOnly]

    def get_queryset(self):
        queryset = services.get_feed_for_user(self.request.user)
        query = self.request.query_params.get("search", "").strip()
        tag = self.request.query_params.get("tag", "").strip()
        author = self.request.query_params.get("author", "").strip()
        if query:
            queryset = queryset.filter(Q(content__icontains=query) | Q(tags__name__icontains=query))
        if tag:
            queryset = queryset.filter(tags__slug=tag)
        if author:
            queryset = queryset.filter(author__username=author)
        return queryset.distinct()

    def get_object(self):
        post = get_object_or_404(
            Post.objects.select_related("author", "author__profile").prefetch_related("tags"),
            pk=self.kwargs["pk"],
        )
        if not services.can_view_post(self.request.user, post):
            raise PermissionDenied("Нет доступа к публикации.")
        self.check_object_permissions(self.request, post)
        return post

    def perform_destroy(self, instance):
        instance.is_archived = True
        instance.save(update_fields=["is_archived", "updated_at"])

    @extend_schema(tags=["Posts"], summary="Публикации текущего пользователя")
    @action(detail=False, methods=["get"], permission_classes=[IsAuthenticated])
    def mine(self, request):
        queryset = self.get_queryset().filter(author=request.user)
        page = self.paginate_queryset(queryset)
        serializer = self.get_serializer(page or queryset, many=True)
        if page is not None:
            return self.get_paginated_response(serializer.data)
        return Response(serializer.data)

    @extend_schema(
        tags=["Posts"],
        summary="Поставить, изменить или удалить реакцию",
        request=ReactionRequestSerializer,
        responses={200: ReactionResultSerializer},
    )
    @action(detail=True, methods=["post"], permission_classes=[IsAuthenticated])
    def react(self, request, pk=None):
        post = self.get_object()
        serializer = ReactionRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        reaction, active = services.toggle_reaction(
            user=request.user,
            post=post,
            kind=serializer.validated_data["kind"],
        )
        return Response(
            {
                "active": active,
                "reaction": (
                    None
                    if reaction is None
                    else ReactionSerializer(reaction, context={"request": request}).data
                ),
            }
        )

    @extend_schema(
        tags=["Posts"],
        summary="Добавить или удалить публикацию из закладок",
        responses={200: BookmarkResultSerializer},
    )
    @action(detail=True, methods=["post"], permission_classes=[IsAuthenticated])
    def bookmark(self, request, pk=None):
        post = self.get_object()
        bookmark, active = services.toggle_bookmark(user=request.user, post=post)
        return Response({"active": active, "bookmark_id": bookmark.pk if bookmark else None})

    @extend_schema(tags=["Comments"], summary="Комментарии публикации", responses=CommentSerializer(many=True))
    @action(detail=True, methods=["get"])
    def comments(self, request, pk=None):
        post = self.get_object()
        queryset = post.comments.filter(parent__isnull=True).select_related(
            "author",
            "author__profile",
        )
        page = self.paginate_queryset(queryset)
        serializer = CommentSerializer(page or queryset, many=True, context={"request": request})
        if page is not None:
            return self.get_paginated_response(serializer.data)
        return Response(serializer.data)


@extend_schema_view(
    list=extend_schema(tags=["Comments"], summary="Комментарии доступных публикаций"),
    retrieve=extend_schema(tags=["Comments"], summary="Комментарий"),
    create=extend_schema(tags=["Comments"], summary="Создать комментарий"),
    destroy=extend_schema(tags=["Comments"], summary="Мягко удалить комментарий"),
)
class CommentViewSet(viewsets.ModelViewSet):
    serializer_class = CommentSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]
    http_method_names = ["get", "post", "delete", "head", "options"]

    def get_queryset(self):
        visible_posts = services.get_feed_for_user(self.request.user).values("pk")
        return (
            Comment.objects.filter(post_id__in=visible_posts)
            .select_related("post", "author", "author__profile")
            .prefetch_related("replies__author", "replies__author__profile")
        )

    def perform_destroy(self, instance):
        services.soft_delete_comment(user=self.request.user, comment=instance)


@extend_schema_view(
    list=extend_schema(tags=["Posts"], summary="Список тегов"),
    retrieve=extend_schema(tags=["Posts"], summary="Тег"),
)
class TagViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = TagSerializer
    lookup_field = "slug"

    def get_queryset(self):
        return Tag.objects.annotate(posts_count=Count("posts", distinct=True)).order_by("name")


@extend_schema_view(
    list=extend_schema(tags=["Posts"], summary="Мои закладки"),
    retrieve=extend_schema(tags=["Posts"], summary="Закладка"),
)
class BookmarkViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = BookmarkSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        if not self.request.user.is_authenticated:
            return Bookmark.objects.none()
        return (
            Bookmark.objects.filter(user=self.request.user)
            .select_related("post", "post__author", "post__author__profile")
            .prefetch_related("post__tags")
        )


@extend_schema_view(
    list=extend_schema(tags=["Users"], summary="Мои подписки и заявки"),
    retrieve=extend_schema(tags=["Users"], summary="Связь подписки"),
)
class FollowViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = FollowSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        if not self.request.user.is_authenticated:
            return Follow.objects.none()
        scope = self.request.query_params.get("scope", "all")
        queryset = Follow.objects.select_related(
            "follower",
            "follower__profile",
            "following",
            "following__profile",
        ).filter(Q(follower=self.request.user) | Q(following=self.request.user))
        if scope == "incoming":
            queryset = queryset.filter(following=self.request.user)
        elif scope == "outgoing":
            queryset = queryset.filter(follower=self.request.user)
        elif scope == "requests":
            queryset = queryset.filter(following=self.request.user, status=Follow.Status.PENDING)
        return queryset.order_by("-created_at")


@extend_schema_view(
    list=extend_schema(tags=["Users"], summary="Мои блокировки"),
    retrieve=extend_schema(tags=["Users"], summary="Блокировка"),
)
class BlockedUserViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = BlockedUserSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        if not self.request.user.is_authenticated:
            return BlockedUser.objects.none()
        return BlockedUser.objects.filter(blocker=self.request.user).select_related(
            "blocker",
            "blocker__profile",
            "blocked",
            "blocked__profile",
        )


@extend_schema_view(
    list=extend_schema(tags=["Notifications"], summary="Мои уведомления"),
    retrieve=extend_schema(tags=["Notifications"], summary="Уведомление"),
)
class NotificationViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        if not self.request.user.is_authenticated:
            return Notification.objects.none()
        unread = self.request.query_params.get("unread")
        queryset = self.request.user.notifications.select_related("actor", "actor__profile")
        if unread in {"1", "true", "yes"}:
            queryset = queryset.filter(is_read=False)
        return queryset

    @extend_schema(tags=["Notifications"], summary="Отметить уведомление прочитанным")
    @action(detail=True, methods=["post"])
    def read(self, request, pk=None):
        notification = self.get_object()
        notification.mark_read()
        return Response(self.get_serializer(notification).data)

    @extend_schema(tags=["Notifications"], summary="Отметить все уведомления прочитанными")
    @action(detail=False, methods=["post"], url_path="read-all")
    def read_all(self, request):
        updated = request.user.notifications.filter(is_read=False).update(is_read=True)
        return Response({"updated": updated})


@extend_schema_view(
    list=extend_schema(tags=["Messages"], summary="Мои диалоги"),
    retrieve=extend_schema(tags=["Messages"], summary="Диалог"),
)
class ConversationViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = ConversationSerializer
    permission_classes = [IsParticipant]

    def get_queryset(self):
        if not self.request.user.is_authenticated:
            return Conversation.objects.none()
        return (
            self.request.user.conversations.annotate(message_count=Count("messages"))
            .prefetch_related("memberships__user", "memberships__user__profile", "messages__sender")
            .order_by("-updated_at")
        )

    @extend_schema(
        tags=["Messages"],
        summary="Создать или открыть личный диалог",
        request=DirectConversationSerializer,
        responses={200: ConversationSerializer},
        examples=[
            OpenApiExample(
                "Диалог с сообщением",
                value={"recipient_username": "bob", "body": "Привет, Боб!"},
                request_only=True,
            )
        ],
    )
    @action(detail=False, methods=["post"])
    def direct(self, request):
        serializer = DirectConversationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        recipient = serializer.validated_data["recipient_username"]
        conversation = services.get_or_create_direct_conversation(first=request.user, second=recipient)
        body = serializer.validated_data.get("body", "").strip()
        if body:
            services.send_message_to_conversation(
                sender=request.user,
                conversation=conversation,
                body=body,
            )
            conversation.refresh_from_db()
        return Response(ConversationSerializer(conversation, context={"request": request}).data)

    @extend_schema(
        tags=["Messages"],
        summary="Создать групповой диалог",
        request=GroupConversationSerializer,
        responses={201: ConversationSerializer},
    )
    @action(detail=False, methods=["post"])
    def group(self, request):
        serializer = GroupConversationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        conversation = services.create_group_conversation(
            owner=request.user,
            users=serializer.validated_data["usernames"],
            title=serializer.validated_data["title"],
        )
        return Response(
            ConversationSerializer(conversation, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )

    @extend_schema(
        tags=["Messages"],
        summary="Сообщения диалога",
        request=MessageSerializer,
        responses=MessageSerializer(many=True),
    )
    @action(detail=True, methods=["get", "post"])
    def messages(self, request, pk=None):
        conversation = self.get_object()
        if request.method == "POST":
            serializer = MessageCreateSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            message = services.send_message_to_conversation(
                sender=request.user,
                conversation=conversation,
                body=serializer.validated_data["body"],
            )
            return Response(
                MessageSerializer(message, context={"request": request}).data,
                status=status.HTTP_201_CREATED,
            )

        queryset = conversation.messages.select_related("sender", "sender__profile")
        page = self.paginate_queryset(queryset)
        serializer = MessageSerializer(page or queryset, many=True, context={"request": request})
        if page is not None:
            return self.get_paginated_response(serializer.data)
        return Response(serializer.data)


@extend_schema_view(
    list=extend_schema(tags=["Messages"], summary="Сообщения во всех моих диалогах"),
    retrieve=extend_schema(tags=["Messages"], summary="Сообщение"),
    create=extend_schema(tags=["Messages"], summary="Отправить сообщение в диалог"),
)
class MessageViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = MessageSerializer
    permission_classes = [IsParticipant]

    def get_queryset(self):
        if not self.request.user.is_authenticated:
            return Message.objects.none()
        return Message.objects.filter(conversation__participants=self.request.user).select_related(
            "conversation",
            "sender",
            "sender__profile",
        )


@extend_schema_view(
    list=extend_schema(tags=["Moderation"], summary="Мои жалобы"),
    retrieve=extend_schema(tags=["Moderation"], summary="Жалоба"),
    create=extend_schema(tags=["Moderation"], summary="Создать жалобу"),
)
class ReportViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = ReportSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        if not self.request.user.is_authenticated:
            return Report.objects.none()
        return Report.objects.filter(reporter=self.request.user).select_related(
            "reporter",
            "reporter__profile",
            "post",
            "comment",
        )
