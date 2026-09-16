#!/usr/bin/env bash

set -Eeuo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_BIN="${PROJECT_DIR}/.venv/bin/python"
PIP_BIN="${PROJECT_DIR}/.venv/bin/pip"
SERVER_PID=""

cleanup() {
    exit_code=$?

    if [[ -n "${SERVER_PID}" ]] && kill -0 "${SERVER_PID}" 2>/dev/null; then
        echo
        echo "Deteniendo el servidor..."
        kill -TERM "${SERVER_PID}" 2>/dev/null || true
        wait "${SERVER_PID}" 2>/dev/null || true
    fi

    exit "${exit_code}"
}

handle_interrupt() {
    echo
    echo "Interrupción recibida. Cerrando de forma segura..."
    exit 130
}

trap cleanup EXIT
trap handle_interrupt INT TERM

cd "${PROJECT_DIR}"
APP_URL="http://127.0.0.1:8000/"

if ! command -v python3 >/dev/null 2>&1; then
    echo "Error: no se encontró python3 en el sistema." >&2
    exit 1
fi

if [[ ! -f ".env" ]]; then
    echo "Error: falta el archivo .env con la configuración de la base de datos." >&2
    echo "Copia .env.example como .env y completa sus valores." >&2
    exit 1
fi

if [[ ! -x "${PYTHON_BIN}" ]]; then
    echo "Creando entorno virtual..."
    python3 -m venv .venv
fi

echo "Instalando o comprobando dependencias..."
"${PIP_BIN}" install --quiet -r requirements.txt

echo "Comprobando configuración de Django..."
"${PYTHON_BIN}" manage.py check

echo "Aplicando migraciones..."
"${PYTHON_BIN}" manage.py migrate --noinput

echo "Aplicación disponible en ${APP_URL}"
echo "Pulsa Ctrl+C para detenerla de forma segura."

"${PYTHON_BIN}" manage.py runserver 0.0.0.0:8000 --noreload &
SERVER_PID=$!

if [[ -n "${BROWSER:-}" ]]; then
    "${BROWSER}" "${APP_URL}" >/dev/null 2>&1 &
fi

wait "${SERVER_PID}"