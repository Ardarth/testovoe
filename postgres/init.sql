-- Выполняется один раз, при первой инициализации пустого тома pgdata
CREATE TABLE IF NOT EXISTS visits (
    id         BIGSERIAL PRIMARY KEY,
    session_id TEXT        NOT NULL,
    client_ip  INET,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
