# Postman guide

Файл коллекции:

```text
docs/postman/social-course-api.postman_collection.json
```

## Импорт

1. Откройте Postman.
2. Нажмите `Import`.
3. Выберите файл `docs/postman/social-course-api.postman_collection.json`.
4. После импорта откройте коллекцию `Social Course API`.
5. Проверьте collection variables.

## Переменные коллекции

| Переменная | Значение по умолчанию | Назначение |
| --- | --- | --- |
| `base_url` | `http://127.0.0.1:8000` | Адрес Django-сервера |
| `token` | пусто | Token авторизации |
| `username` | `alice` | Текущий пользователь |
| `password` | `password123` | Пароль демо-пользователя |
| `target_username` | `bob` | Пользователь для подписок, сообщений и блокировки |
| `post_id` | `1` | Текущая публикация |
| `comment_id` | `1` | Текущий комментарий |
| `conversation_id` | `1` | Текущий диалог |
| `notification_id` | `1` | Текущее уведомление |
| `tag_slug` | `django` | Текущий тег |

Если сервер запущен на другом порту, измените `base_url`, например на `http://127.0.0.1:8001`.

## Рекомендуемый порядок запуска

Перед Postman подготовьте проект:

```bash
python manage.py migrate
python manage.py seed_demo
python manage.py runserver
```

Затем в Postman:

1. `01 Auth / Login Token` - получает token и сохраняет его в переменную `token`.
2. `01 Auth / Current User` - проверяет авторизацию.
3. `03 Posts / Create Post` - создает публикацию и сохраняет `post_id`.
4. `04 Comments and Tags / Create Comment` - создает комментарий и сохраняет `comment_id`.
5. `03 Posts / React to Post` - проверяет реакции.
6. `03 Posts / Toggle Bookmark` - проверяет закладки.
7. `06 Messages / Open Direct Conversation` - создает диалог и сохраняет `conversation_id`.
8. `06 Messages / Send Message to Conversation` - отправляет сообщение.
9. `05 Bookmarks and Notifications / List Notifications` - сохраняет `notification_id`, если уведомления есть.
10. `07 Moderation / Create Post Report` - создает жалобу.

## Авторизация в коллекции

Коллекция использует header:

```http
Authorization: Token {{token}}
```

Этот header задан на уровне всей коллекции. Запросы регистрации и логина используют `noauth`, потому что token для них еще не нужен.

## Автоматические scripts

В коллекции есть небольшие Postman scripts:

- после регистрации сохраняется `token` и `username`;
- после логина сохраняется `token` и `username`;
- после создания публикации сохраняется `post_id` и первый `tag_slug`;
- после создания комментария сохраняется `comment_id`;
- после открытия диалога сохраняется `conversation_id`;
- после списка уведомлений сохраняется `notification_id`, если есть хотя бы одно уведомление;
- перед каждым запросом создается переменная `timestamp`, чтобы можно было генерировать уникальные тестовые значения.

## Что демонстрирует коллекция

Коллекция разделена на папки:

- `00 Documentation` - OpenAPI schema, Swagger UI, ReDoc;
- `01 Auth` - регистрация, login, текущий пользователь, профиль, logout;
- `02 Users and Social Graph` - пользователи, подписки, заявки, блокировки;
- `03 Posts` - лента, создание, обновление, реакции, закладки, комментарии, архивирование;
- `04 Comments and Tags` - комментарии и теги;
- `05 Bookmarks and Notifications` - закладки и уведомления;
- `06 Messages` - личные и групповые диалоги, сообщения;
- `07 Moderation` - жалобы.

## Частые проблемы

`401 Unauthorized`:

- выполните `Login Token`;
- убедитесь, что переменная `token` заполнена;
- проверьте, что header выглядит как `Authorization: Token <token>`.

`403 Forbidden`:

- объект может быть скрыт правилами приватности;
- пользователь может быть заблокирован;
- вы пытаетесь изменить чужую публикацию;
- вы не являетесь участником диалога.

`404 Not Found`:

- проверьте `post_id`, `comment_id`, `conversation_id`;
- выполните `seed_demo`;
- создайте объект через соответствующий POST-запрос коллекции.

`400 Bad Request`:

- проверьте тело JSON;
- для публикации нужен `content`;
- для комментария нужен `post` и `content`;
- для жалобы нужен `post` или `comment`;
- для группового диалога нужен `title` и список `usernames`.
