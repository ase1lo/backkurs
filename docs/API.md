# API documentation

Документ описывает REST API серверной части социальной сети. Интерактивная документация доступна после запуска проекта:

- Swagger UI: `http://127.0.0.1:8000/api/docs/`
- ReDoc: `http://127.0.0.1:8000/api/redoc/`
- OpenAPI schema: `http://127.0.0.1:8000/api/schema/`
- статическая схема в репозитории: `docs/openapi/schema.yaml`

Основной префикс API: `/api/v1/`.

## Авторизация

API поддерживает token authentication из Django REST Framework.

1. Получить token:

```http
POST /api/v1/auth/token/
Content-Type: application/json

{
  "username": "alice",
  "password": "password123"
}
```

2. Передавать token в заголовке:

```http
Authorization: Token <token>
```

В Swagger UI нажмите `Authorize` и вставьте значение в формате `Token <token>`.

## Формат ответов

Списковые endpoints возвращают пагинированный ответ:

```json
{
  "count": 42,
  "next": "http://127.0.0.1:8000/api/v1/posts/?page=2",
  "previous": null,
  "results": []
}
```

Размер страницы задается в `REST_FRAMEWORK.PAGE_SIZE` и сейчас равен `20`.

## Ошибки

Типовые HTTP-коды:

- `200 OK` - запрос выполнен;
- `201 Created` - объект создан;
- `204 No Content` - объект удален или действие выполнено без тела ответа;
- `400 Bad Request` - ошибка валидации;
- `401 Unauthorized` - не передан token;
- `403 Forbidden` - нет прав на действие или объект скрыт приватностью;
- `404 Not Found` - объект не найден;
- `405 Method Not Allowed` - метод не поддерживается endpoint.

Пример ошибки валидации:

```json
{
  "content": [
    "This field may not be blank."
  ]
}
```

## Auth

| Method | URL | Назначение |
| --- | --- | --- |
| `POST` | `/api/v1/auth/register/` | Регистрация пользователя, создание профиля и token |
| `POST` | `/api/v1/auth/token/` | Получение token по username/password |
| `POST` | `/api/v1/auth/logout/` | Удаление текущего token |
| `GET` | `/api/v1/auth/me/` | Данные текущего пользователя |
| `PATCH` | `/api/v1/auth/me/` | Обновление пользователя и вложенного профиля |

Пример обновления профиля:

```json
{
  "first_name": "Nikita",
  "profile": {
    "display_name": "Nikita Backend",
    "bio": "Django API developer",
    "location": "Moscow",
    "is_private": false
  }
}
```

## Users

| Method | URL | Назначение |
| --- | --- | --- |
| `GET` | `/api/v1/users/` | Список пользователей |
| `GET` | `/api/v1/users/?search=bob` | Поиск пользователей |
| `GET` | `/api/v1/users/{username}/` | Публичный профиль пользователя |
| `POST` | `/api/v1/users/{username}/follow/` | Подписаться или отправить заявку |
| `DELETE` | `/api/v1/users/{username}/unfollow/` | Отписаться |
| `POST` | `/api/v1/users/{username}/approve-follow-request/` | Одобрить входящую заявку |
| `POST` | `/api/v1/users/{username}/block/` | Заблокировать пользователя |
| `GET` | `/api/v1/users/{username}/followers/` | Подписчики |
| `GET` | `/api/v1/users/{username}/following/` | Подписки |

Правила:

- если профиль открытый, подписка сразу получает статус `active`;
- если профиль закрытый, создается заявка `pending`;
- данные закрытого профиля, его подписчики, подписки и публикации доступны только владельцу, администраторам и активным подписчикам;
- после блокировки удаляются подписки в обе стороны;
- заблокированные пользователи не видят публикации друг друга и не могут писать личные сообщения.

## Posts

| Method | URL | Назначение |
| --- | --- | --- |
| `GET` | `/api/v1/posts/` | Лента с учетом приватности |
| `GET` | `/api/v1/posts/?search=django` | Поиск по тексту и тегам |
| `GET` | `/api/v1/posts/?tag=backend` | Фильтр по тегу |
| `GET` | `/api/v1/posts/?author=alice` | Фильтр по автору |
| `POST` | `/api/v1/posts/` | Создать публикацию |
| `GET` | `/api/v1/posts/{id}/` | Получить публикацию |
| `PATCH` | `/api/v1/posts/{id}/` | Обновить свою публикацию |
| `DELETE` | `/api/v1/posts/{id}/` | Архивировать свою публикацию |
| `GET` | `/api/v1/posts/mine/` | Мои публикации |
| `POST` | `/api/v1/posts/{id}/react/` | Поставить, изменить или убрать реакцию |
| `POST` | `/api/v1/posts/{id}/bookmark/` | Добавить или убрать закладку |
| `GET` | `/api/v1/posts/{id}/comments/` | Комментарии публикации |

Пример создания публикации:

```json
{
  "content": "Разрабатываю backend социальной сети на Django.",
  "visibility": "public",
  "tag_names": ["django", "backend", "coursework"],
  "image_url": ""
}
```

Доступные значения `visibility`:

- `public` - видно всем;
- `followers` - видно автору и активным подписчикам;
- `private` - видно только автору и администраторам.

Доступные реакции:

- `like`;
- `love`;
- `support`.

## Comments

| Method | URL | Назначение |
| --- | --- | --- |
| `GET` | `/api/v1/comments/` | Комментарии к доступным публикациям |
| `POST` | `/api/v1/comments/` | Создать комментарий или ответ |
| `GET` | `/api/v1/comments/{id}/` | Получить комментарий |
| `DELETE` | `/api/v1/comments/{id}/` | Мягко удалить комментарий |

Пример комментария:

```json
{
  "post": 1,
  "content": "Отличный пост!"
}
```

Пример ответа:

```json
{
  "post": 1,
  "parent": 5,
  "content": "Согласен."
}
```

Мягкое удаление не удаляет запись из базы: `is_deleted` становится `true`, а текст заменяется на `[deleted]`.

## Tags and Bookmarks

| Method | URL | Назначение |
| --- | --- | --- |
| `GET` | `/api/v1/tags/` | Список тегов |
| `GET` | `/api/v1/tags/{slug}/` | Данные тега |
| `GET` | `/api/v1/bookmarks/` | Мои закладки |

Теги создаются автоматически при создании или обновлении публикации через поле `tag_names`.

## Follows and Blocks

| Method | URL | Назначение |
| --- | --- | --- |
| `GET` | `/api/v1/follows/` | Все мои связи подписок |
| `GET` | `/api/v1/follows/?scope=incoming` | Входящие подписки и заявки |
| `GET` | `/api/v1/follows/?scope=outgoing` | Исходящие подписки и заявки |
| `GET` | `/api/v1/follows/?scope=requests` | Только входящие заявки |
| `GET` | `/api/v1/blocks/` | Мои блокировки |

## Notifications

| Method | URL | Назначение |
| --- | --- | --- |
| `GET` | `/api/v1/notifications/` | Мои уведомления |
| `GET` | `/api/v1/notifications/?unread=true` | Только непрочитанные |
| `GET` | `/api/v1/notifications/{id}/` | Уведомление |
| `POST` | `/api/v1/notifications/{id}/read/` | Отметить прочитанным |
| `POST` | `/api/v1/notifications/read-all/` | Отметить все прочитанными |

Уведомления создаются при:

- подписке или заявке на подписку;
- одобрении заявки;
- реакции на публикацию;
- комментарии к публикации;
- личном сообщении.

## Conversations and Messages

| Method | URL | Назначение |
| --- | --- | --- |
| `GET` | `/api/v1/conversations/` | Мои диалоги |
| `GET` | `/api/v1/conversations/{id}/` | Диалог |
| `POST` | `/api/v1/conversations/direct/` | Создать или открыть личный диалог |
| `POST` | `/api/v1/conversations/group/` | Создать групповой диалог |
| `GET` | `/api/v1/conversations/{id}/messages/` | Сообщения диалога |
| `POST` | `/api/v1/conversations/{id}/messages/` | Отправить сообщение в диалог |
| `GET` | `/api/v1/messages/` | Все мои сообщения |
| `POST` | `/api/v1/messages/` | Отправить сообщение в указанный диалог |

Пример личного диалога:

```json
{
  "recipient_username": "bob",
  "body": "Привет!"
}
```

Пример группового диалога:

```json
{
  "title": "Backend group",
  "usernames": ["bob", "carol"]
}
```

## Moderation

| Method | URL | Назначение |
| --- | --- | --- |
| `GET` | `/api/v1/reports/` | Мои жалобы |
| `POST` | `/api/v1/reports/` | Создать жалобу |
| `GET` | `/api/v1/reports/{id}/` | Жалоба |

Пример жалобы на публикацию:

```json
{
  "post": 1,
  "reason": "spam",
  "details": "Похоже на спам."
}
```

Пример жалобы на комментарий:

```json
{
  "comment": 3,
  "reason": "abuse",
  "details": "Нарушение правил общения."
}
```

Причины жалобы:

- `spam`;
- `abuse`;
- `other`.
