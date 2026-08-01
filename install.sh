#!/usr/bin/env bash
set -euo pipefail

APP_DIR="/opt/medtender-agent"
APP_USER="medtender"

if [[ "${EUID}" -ne 0 ]]; then
  echo "Run as root: sudo ./install.sh"
  exit 1
fi

id -u "${APP_USER}" >/dev/null 2>&1 || useradd --system --create-home --shell /usr/sbin/nologin "${APP_USER}"

mkdir -p "${APP_DIR}" "${APP_DIR}/data"
rsync -a --delete --exclude '.git' --exclude '.env' ./ "${APP_DIR}/"

python3.12 -m venv "${APP_DIR}/.venv"
"${APP_DIR}/.venv/bin/pip" install --upgrade pip
"${APP_DIR}/.venv/bin/pip" install -r "${APP_DIR}/requirements.txt"

if [[ ! -f "${APP_DIR}/.env" ]]; then
  cp "${APP_DIR}/.env.example" "${APP_DIR}/.env"
  chmod 600 "${APP_DIR}/.env"
fi

chown -R "${APP_USER}:${APP_USER}" "${APP_DIR}"
install -m 0644 "${APP_DIR}/medtender.service" /etc/systemd/system/medtender.service
install -m 0644 "${APP_DIR}/medtender.timer" /etc/systemd/system/medtender.timer
install -m 0644 "${APP_DIR}/medtender-afternoon.timer" /etc/systemd/system/medtender-afternoon.timer

systemctl daemon-reload
systemctl enable --now medtender.timer medtender-afternoon.timer

echo "Installed. Edit ${APP_DIR}/.env, then run: systemctl start medtender.service"
