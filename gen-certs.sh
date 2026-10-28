#!/usr/bin/env bash
# Самоподписанный сертификат для локального стенда: certs/server.crt и certs/server.key.
# Повторный запуск не перезаписывает сертификат; -f — выпустить заново.
set -euo pipefail

CERT_DIR="$(cd "$(dirname "$0")" && pwd)/certs"
DAYS="${DAYS:-365}"
CN="${CN:-localhost}"

if [[ -f "$CERT_DIR/server.crt" && "${1:-}" != "-f" ]]; then
  echo "Сертификат уже есть: $CERT_DIR/server.crt (выпустить заново: $0 -f)"
  exit 0
fi

mkdir -p "$CERT_DIR"

openssl req -x509 -newkey rsa:2048 -nodes -sha256 \
  -days "$DAYS" \
  -subj "/CN=$CN" \
  -addext "subjectAltName=DNS:$CN,DNS:localhost,IP:127.0.0.1" \
  -keyout "$CERT_DIR/server.key" \
  -out "$CERT_DIR/server.crt"

# Ключ читает Nginx внутри контейнера (не root на хосте), поэтому 644, а не 600
chmod 644 "$CERT_DIR/server.key"

openssl x509 -in "$CERT_DIR/server.crt" -noout -subject -enddate
