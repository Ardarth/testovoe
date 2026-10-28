# Локальный стенд веб-приложения

Nginx (TLS, reverse proxy) → backend на Python (Flask, :8080) → PostgreSQL 15 и Redis.

| Сервис | Что делает | Наружу |
|---|---|---|
| `nginx` | TLS termination, проксирование на backend, rate limit 10 req/s на IP, тело запроса до 10 МБ, редирект HTTP → HTTPS | `:443`, `:80` |
| `app` | показывает заголовки `X-Forwarded-*`, хранит сессии в Redis, пишет визиты в PostgreSQL | нет |
| `postgres` | PostgreSQL 15, таблица `visits` создаётся при первом запуске (`postgres/init.sql`) | нет |
| `redis` | кэш сессий с TTL, пароль, `maxmemory 128mb` | нет |

У всех четырёх сервисов есть healthcheck. Порядок запуска задают `depends_on: service_healthy`: БД и Redis → `app` → `nginx`.
Сети разделены: `nginx` видит только `app`, а БД и Redis доступны только из `app`.

## Запуск

Нужны Docker с Compose v2 и `openssl`.

```bash
cp -n .env.example .env              # .env с паролями (если его ещё нет)
./gen-certs.sh                       # самоподписанный сертификат в certs/
docker compose up -d --build --wait  # сборка и запуск, ждёт healthy у всех сервисов
curl -k https://localhost/           # ответ backend с заголовками и сессией
```

Остановить и удалить данные: `docker compose down -v`.

## Проверка требований

```bash
docker compose ps                                     # все сервисы в статусе healthy
curl -kc jar -b jar https://localhost/                # X-Forwarded-For/Proto/Host; повтор — visits растёт (сессия в Redis)
head -c 11000000 /dev/zero | curl -sk -o /dev/null -w '%{http_code}\n' --data-binary @- https://localhost/upload   # 413
seq 60 | xargs -P 60 -I{} curl -sk -o /dev/null -w '%{http_code}\n' https://localhost/ | sort | uniq -c            # часть ответов — 429
```

## Файлы

- `docker-compose.yml` — сервисы, healthcheck'и, сети, том `pgdata`
- `nginx/nginx.conf` — TLS, заголовки `X-Forwarded-*`, `limit_req` (10r/s, burst 20, ответ 429), `client_max_body_size 10m`
- `gen-certs.sh` — сертификат на `localhost` и `127.0.0.1` (SAN), на 365 дней; `./gen-certs.sh -f` — выпустить заново
- `.env.example` — переменные и пароли; `.env` и `certs/` в `.gitignore`
- `app/` — backend: `app.py`, `Dockerfile` (запуск не от root), `requirements.txt`
- `postgres/init.sql` — схема БД
