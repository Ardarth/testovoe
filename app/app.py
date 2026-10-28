"""Тестовый backend: показывает заголовки от Nginx, хранит сессии в Redis, пишет визиты в PostgreSQL."""
import os
import uuid

import psycopg
import redis
from flask import Flask, jsonify, request
from werkzeug.middleware.proxy_fix import ProxyFix

SESSION_TTL = int(os.environ.get("SESSION_TTL_SECONDS", "1800"))
DB_DSN = (
    f"host={os.environ['DB_HOST']} port={os.environ.get('DB_PORT', '5432')} "
    f"dbname={os.environ['DB_NAME']} user={os.environ['DB_USER']} "
    f"password={os.environ['DB_PASSWORD']} connect_timeout=3"
)

app = Flask(__name__)
# Доверяем X-Forwarded-* ровно от одного прокси — Nginx
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_port=1)

cache = redis.Redis(
    host=os.environ["REDIS_HOST"],
    port=int(os.environ.get("REDIS_PORT", "6379")),
    password=os.environ["REDIS_PASSWORD"],
    socket_timeout=3,
    decode_responses=True,
)


@app.get("/")
def index():
    # Сессия: id в cookie, данные — в Redis с TTL
    sid = request.cookies.get("sid") or uuid.uuid4().hex
    key = f"session:{sid}"
    visits = cache.hincrby(key, "visits", 1)
    cache.expire(key, SESSION_TTL)

    with psycopg.connect(DB_DSN) as conn:
        conn.execute("INSERT INTO visits (session_id, client_ip) VALUES (%s, %s)", (sid, request.remote_addr))
        total = conn.execute("SELECT count(*) FROM visits").fetchone()[0]

    resp = jsonify(
        client_ip=request.remote_addr,
        scheme=request.scheme,
        host=request.host,
        forwarded_headers={
            h: request.headers.get(h)
            for h in ("X-Real-IP", "X-Forwarded-For", "X-Forwarded-Proto", "X-Forwarded-Host", "X-Forwarded-Port")
        },
        session={"id": sid, "visits": visits, "ttl_seconds": cache.ttl(key)},
        total_visits_in_db=total,
    )
    resp.set_cookie("sid", sid, max_age=SESSION_TTL, httponly=True, secure=True, samesite="Lax")
    return resp


@app.post("/upload")
def upload():
    # Для проверки client_max_body_size: тело больше 10 МБ отсекает Nginx
    return jsonify(received_bytes=len(request.get_data()))


@app.get("/healthz")
def healthz():
    status = {}
    try:
        with psycopg.connect(DB_DSN) as conn:
            conn.execute("SELECT 1")
        status["postgres"] = "ok"
    except Exception as e:
        status["postgres"] = f"error: {e}"
    try:
        cache.ping()
        status["redis"] = "ok"
    except Exception as e:
        status["redis"] = f"error: {e}"
    healthy = all(v == "ok" for v in status.values())
    return jsonify(status), 200 if healthy else 503
