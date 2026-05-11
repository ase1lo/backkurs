from django.contrib import messages
from django.contrib.auth import get_user_model, login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.core.exceptions import PermissionDenied
from django.db.models import Count, Max
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_POST

from . import services
from .forms import (
    CommentForm,
    ConversationMessageForm,
    DirectMessageForm,
    PostForm,
    ProfileForm,
    ReactionForm,
)
from .models import (
    Bookmark,
    Comment,
    Conversation,
    ConversationParticipant,
    Follow,
    Notification,
    Post,
    Reaction,
    Tag,
)


User = get_user_model()


def register(request):
    if request.user.is_authenticated:
        return redirect("home")
    form = UserCreationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user)
        messages.success(request, "Аккаунт создан. Добро пожаловать!")
        return redirect("home")
    return render(request, "social/register.html", {"form": form})


def home(request):
    post_form = PostForm()
    if request.method == "POST":
        if not request.user.is_authenticated:
            return redirect("login")
        post_form = PostForm(request.POST)
        if post_form.is_valid():
            post = post_form.save(author=request.user)
            messages.success(request, "Публикация создана.")
            return redirect("post_detail", pk=post.pk)

    feed = services.get_feed_for_user(request.user)[:50]
    return render(
        request,
        "social/home.html",
        {
            "feed": feed,
            "post_form": post_form,
            "reaction_kinds": Reaction.Kind.choices,
        },
    )


def post_detail(request, pk):
    post = get_object_or_404(
        Post.objects.select_related("author", "author__profile").prefetch_related("tags"),
        pk=pk,
    )
    if not services.can_view_post(request.user, post):
        raise PermissionDenied("Нет доступа к этой публикации.")

    comment_form = CommentForm()
    if request.method == "POST":
        if not request.user.is_authenticated:
            return redirect("login")
        comment_form = CommentForm(request.POST)
        if comment_form.is_valid():
            services.add_comment(
                user=request.user,
                post=post,
                content=comment_form.cleaned_data["content"],
            )
            messages.success(request, "Комментарий добавлен.")
            return redirect("post_detail", pk=post.pk)

    comments = (
        post.comments.filter(parent__isnull=True)
        .select_related("author", "author__profile")
        .prefetch_related("replies__author", "replies__author__profile")
    )
    user_bookmarked = False
    if request.user.is_authenticated:
        user_bookmarked = Bookmark.objects.filter(user=request.user, post=post).exists()

    return render(
        request,
        "social/post_detail.html",
        {
            "post": post,
            "comments": comments,
            "comment_form": comment_form,
            "reaction_form": ReactionForm(),
            "user_bookmarked": user_bookmarked,
        },
    )


def profile_detail(request, username):
    profile_user = get_object_or_404(
        User.objects.select_related("profile"),
        username=username,
    )
    services.ensure_profile(profile_user)
    can_view_profile = services.can_view_profile(request.user, profile_user)
    posts = Post.objects.none()
    if can_view_profile:
        posts = services.get_feed_for_user(request.user).filter(
            author=profile_user
        )[:30]

    follow_relation = None
    incoming_requests = Follow.objects.none()
    if request.user.is_authenticated:
        follow_relation = Follow.objects.filter(
            follower=request.user,
            following=profile_user,
        ).first()
        if request.user == profile_user:
            incoming_requests = Follow.objects.filter(
                following=request.user,
                status=Follow.Status.PENDING,
            ).select_related("follower", "follower__profile")

    return render(
        request,
        "social/profile.html",
        {
            "profile_user": profile_user,
            "posts": posts,
            "can_view_profile": can_view_profile,
            "follow_relation": follow_relation,
            "incoming_requests": incoming_requests,
            "followers_count": (
                Follow.objects.filter(
                    following=profile_user,
                    status=Follow.Status.ACTIVE,
                ).count()
                if can_view_profile
                else None
            ),
            "following_count": (
                Follow.objects.filter(
                    follower=profile_user,
                    status=Follow.Status.ACTIVE,
                ).count()
                if can_view_profile
                else None
            ),
        },
    )


@login_required
def edit_profile(request):
    profile = services.ensure_profile(request.user)
    form = ProfileForm(request.POST or None, instance=profile)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Профиль обновлен.")
        return redirect("profile_detail", username=request.user.username)
    return render(request, "social/edit_profile.html", {"form": form})


@require_POST
@login_required
def toggle_follow(request, username):
    target = get_object_or_404(User, username=username)
    relation = Follow.objects.filter(follower=request.user, following=target).first()
    if relation:
        services.unfollow_user(follower=request.user, following=target)
        messages.info(request, "Подписка отменена.")
    else:
        relation = services.follow_user(follower=request.user, following=target)
        if relation.status == Follow.Status.PENDING:
            messages.info(request, "Заявка на подписку отправлена.")
        else:
            messages.success(request, "Вы подписались на пользователя.")
    return redirect("profile_detail", username=target.username)


@require_POST
@login_required
def approve_follow(request, username):
    follower = get_object_or_404(User, username=username)
    services.approve_follow_request(owner=request.user, follower=follower)
    messages.success(request, "Заявка подтверждена.")
    return redirect("profile_detail", username=request.user.username)


@require_POST
@login_required
def block_user(request, username):
    target = get_object_or_404(User, username=username)
    services.block_user(blocker=request.user, blocked=target)
    messages.warning(request, "Пользователь заблокирован.")
    return redirect("profile_detail", username=request.user.username)


@require_POST
@login_required
def toggle_reaction(request, pk):
    post = get_object_or_404(Post, pk=pk)
    form = ReactionForm(request.POST)
    if form.is_valid():
        _, active = services.toggle_reaction(
            user=request.user,
            post=post,
            kind=form.cleaned_data["kind"],
        )
        messages.info(request, "Реакция обновлена." if active else "Реакция удалена.")
    next_url = request.POST.get("next")
    if next_url:
        return redirect(next_url)
    return redirect("post_detail", pk=post.pk)


@require_POST
@login_required
def toggle_bookmark(request, pk):
    post = get_object_or_404(Post, pk=pk)
    _, active = services.toggle_bookmark(user=request.user, post=post)
    messages.info(request, "Добавлено в закладки." if active else "Удалено из закладок.")
    return redirect("post_detail", pk=post.pk)


@require_POST
@login_required
def delete_comment(request, pk):
    comment = get_object_or_404(Comment.objects.select_related("post", "author"), pk=pk)
    post_pk = comment.post_id
    services.soft_delete_comment(user=request.user, comment=comment)
    messages.info(request, "Комментарий удален.")
    return redirect("post_detail", pk=post_pk)


@login_required
def notifications(request):
    items = request.user.notifications.select_related("actor", "post")[:50]
    return render(request, "social/notifications.html", {"notifications": items})


@require_POST
@login_required
def mark_notification_read(request, pk):
    notification = get_object_or_404(
        Notification,
        pk=pk,
        recipient=request.user,
    )
    notification.mark_read()
    return redirect("notifications")


@require_POST
@login_required
def mark_all_notifications_read(request):
    request.user.notifications.filter(is_read=False).update(is_read=True)
    return redirect("notifications")


@login_required
def inbox(request):
    form = DirectMessageForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        message = form.save(sender=request.user)
        messages.success(request, "Сообщение отправлено.")
        return redirect("conversation_detail", pk=message.conversation_id)

    conversations = (
        request.user.conversations.annotate(
            last_message_at=Max("messages__created_at"),
            message_count=Count("messages"),
        )
        .prefetch_related("participants", "messages")
        .order_by("-updated_at")
    )
    return render(
        request,
        "social/inbox.html",
        {"form": form, "conversations": conversations},
    )


@login_required
def conversation_detail(request, pk):
    conversation = get_object_or_404(
        Conversation.objects.prefetch_related("participants", "messages__sender"),
        pk=pk,
        participants=request.user,
    )
    form = ConversationMessageForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        services.send_message_to_conversation(
            sender=request.user,
            conversation=conversation,
            body=form.cleaned_data["body"],
        )
        messages.success(request, "Сообщение отправлено.")
        return redirect("conversation_detail", pk=conversation.pk)

    ConversationParticipant.objects.filter(
        conversation=conversation,
        user=request.user,
    ).update(last_read_at=conversation.updated_at)
    return render(
        request,
        "social/conversation_detail.html",
        {"conversation": conversation, "form": form},
    )


def search(request):
    query = request.GET.get("q", "")
    users = services.search_users(query)[:20]
    posts = services.search_posts(query, request.user)[:20]
    return render(
        request,
        "social/search.html",
        {"query": query, "users": users, "posts": posts},
    )


def tag_posts(request, slug):
    tag = get_object_or_404(Tag, slug=slug)
    posts = services.get_feed_for_user(request.user).filter(tags=tag)[:50]
    return render(request, "social/tag_posts.html", {"tag": tag, "posts": posts})


def _post_to_dict(post):
    return {
        "id": post.pk,
        "author": post.author.username,
        "content": post.content,
        "visibility": post.visibility,
        "like_count": post.like_count,
        "comment_count": post.comment_count,
        "tags": [tag.name for tag in post.tags.all()],
        "created_at": post.created_at.isoformat(),
    }


@require_GET
def api_feed(request):
    posts = services.get_feed_for_user(request.user).prefetch_related("tags")[:50]
    return JsonResponse({"results": [_post_to_dict(post) for post in posts]})


@require_GET
def api_post_detail(request, pk):
    post = get_object_or_404(
        Post.objects.select_related("author").prefetch_related("tags"),
        pk=pk,
    )
    if not services.can_view_post(request.user, post):
        raise PermissionDenied("Нет доступа к этой публикации.")
    return JsonResponse(_post_to_dict(post))
