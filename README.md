# Серверная часть веб-приложения «Социальная сеть»

Курсовой проект по дисциплине «Бэкенд-разработка». Проект реализован на Python и Django по паттерну MVT, использует SQLite3, Django REST Framework, Swagger/OpenAPI и простые HTML-шаблоны для демонстрации серверной логики.

## Что реализовано

- регистрация, вход и выход пользователей;
- token authentication для API;
- расширенный профиль: отображаемое имя, описание, город, сайт, аватар по URL, приватность;
- публикации с уровнями доступа: публично, только подписчики, приватно;
- теги, поиск по пользователям и публикациям;
- подписки, заявки на подписку для закрытых профилей, подтверждение заявок;
- блокировки пользователей;
- реакции, комментарии, мягкое удаление комментариев;
- закладки;
- уведомления о подписках, реакциях, комментариях и сообщениях;
- личные и групповые диалоги;
- жалобы на публикации и комментарии;
- административная панель Django;
- полноценный REST API на Django REST Framework;
- Swagger UI, ReDoc и OpenAPI schema;
- Postman collection с переменными и scripts;
- команда для наполнения демонстрационными данными;
- тесты моделей, сервисного слоя, HTML views и API.

## Стек

- Python 3.13;
- Django 5.2;
- Django REST Framework;
- drf-spectacular;
- SQLite3;
- Django Templates;
- Django TestCase и DRF APITestCase.

## Документация

- [API documentation](docs/API.md) - все endpoints, авторизация, примеры запросов и правила доступа;
- [Architecture documentation](docs/ARCHITECTURE.md) - модель данных, сервисный слой, MVT, безопасность;
- [Postman guide](docs/POSTMAN.md) - импорт коллекции, переменные, порядок запуска запросов;
- [Testing documentation](docs/TESTING.md) - структура и сценарии тестов;
- [OpenAPI schema](docs/openapi/schema.yaml) - статическая OpenAPI-схема;
- [Postman collection](docs/postman/social-course-api.postman_collection.json) - готовая коллекция для импорта.

## Быстрый запуск

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py seed_demo
python manage.py runserver
```

После запуска откройте:

- HTML-интерфейс: http://127.0.0.1:8000/
- админка: http://127.0.0.1:8000/admin/
- REST API: http://127.0.0.1:8000/api/v1/
- Swagger UI: http://127.0.0.1:8000/api/docs/
- ReDoc: http://127.0.0.1:8000/api/redoc/
- OpenAPI schema: http://127.0.0.1:8000/api/schema/

Демонстрационные пользователи после `seed_demo`:

- `alice`;
- `bob`;
- `carol`.

Пароль для всех: `password123`.

## API авторизация

Получить token:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/auth/token/ \
  -H "Content-Type: application/json" \
  -d '{"username": "alice", "password": "password123"}'
```

Использовать token:

```bash
curl http://127.0.0.1:8000/api/v1/auth/me/ \
  -H "Authorization: Token <token>"
```

В Swagger UI нажмите `Authorize` и вставьте значение в формате:

```text
Token <token>
```

## Postman

Импортируйте файл:

```text
docs/postman/social-course-api.postman_collection.json
```

Коллекция содержит папки:

- Documentation;
- Auth;
- Users and Social Graph;
- Posts;
- Comments and Tags;
- Bookmarks and Notifications;
- Messages;
- Moderation.

Коллекция автоматически сохраняет `token`, `post_id`, `comment_id`, `conversation_id`, `notification_id` и `tag_slug` из ответов.

## Архитектура

Проект разделен по MVT и дополнен сервисным слоем:

- `config/` - настройки проекта, корневые URL, WSGI/ASGI;
- `social/models.py` - слой данных: профили, подписки, посты, теги, комментарии, реакции, уведомления, сообщения;
- `social/services.py` - бизнес-логика: приватность, подписки, блокировки, реакции, комментарии, сообщения;
- `social/views.py` - HTML views;
- `social/api/serializers.py` - JSON-сериализация и валидация API;
- `social/api/views.py` - DRF API views и viewsets;
- `social/forms.py` - формы для HTML-интерфейса;
- `social/templates/` - демонстрационный frontend;
- `social/tests/` - автоматические тесты.

## Создание администратора

```bash
source .venv/bin/activate
python manage.py createsuperuser
```

## Тесты

```bash
source .venv/bin/activate
python manage.py test
```

На текущей версии проходит 46 тестов:

- ограничения и сигналы моделей;
- приватность публикаций;
- подписки и закрытые профили;
- блокировки;
- реакции, комментарии и закладки;
- личные сообщения и уведомления;
- HTML routes;
- DRF API;
- Swagger/OpenAPI endpoints.

## Полезные маршруты

HTML:

- `/` - лента;
- `/accounts/register/` - регистрация;
- `/accounts/login/` - вход;
- `/users/<username>/` - профиль пользователя;
- `/posts/<id>/` - публикация и комментарии;
- `/search/?q=django` - поиск;
- `/notifications/` - уведомления;
- `/messages/` - диалоги.

API:

- `/api/v1/auth/register/` - регистрация;
- `/api/v1/auth/token/` - получение token;
- `/api/v1/auth/me/` - текущий пользователь;
- `/api/v1/users/` - пользователи;
- `/api/v1/posts/` - лента и публикации;
- `/api/v1/comments/` - комментарии;
- `/api/v1/tags/` - теги;
- `/api/v1/bookmarks/` - закладки;
- `/api/v1/follows/` - подписки и заявки;
- `/api/v1/blocks/` - блокировки;
- `/api/v1/notifications/` - уведомления;
- `/api/v1/conversations/` - диалоги;
- `/api/v1/messages/` - сообщения;
- `/api/v1/reports/` - жалобы.

Документация API:

- `/api/schema/` - OpenAPI schema;
- `/api/docs/` - Swagger UI;
- `/api/redoc/` - ReDoc.

## Примечания для защиты

Основной акцент сделан на backend: правила приватности вынесены в сервисный слой, счетчики реакций и комментариев синхронизируются сигналами, на уровне базы данных добавлены уникальные ограничения и проверки от самоподписки, самоблокировки и дублей. REST API покрывает ключевые сценарии социальной сети и документируется автоматически через OpenAPI. HTML-интерфейс нужен для демонстрации сценариев, поэтому он намеренно простой.
