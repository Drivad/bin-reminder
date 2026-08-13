#!/usr/bin/env bash
# Install the bin reminder as a systemd timer on a Raspberry Pi (or any Debian box).
# Usage:  sudo ./deploy/install.sh
set -euo pipefail

APP_DIR=/opt/bin-reminder
ENV_FILE=/etc/bin-reminder.env
SERVICE_USER=binbot
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [[ $EUID -ne 0 ]]; then
  echo "Please run with sudo: sudo ./deploy/install.sh" >&2
  exit 1
fi

echo "==> Installing system packages"
apt-get update -qq
apt-get install -y -qq python3 python3-venv git

echo "==> Creating service user '$SERVICE_USER'"
id -u "$SERVICE_USER" &>/dev/null || useradd --system --no-create-home --shell /usr/sbin/nologin "$SERVICE_USER"

echo "==> Installing application to $APP_DIR"
mkdir -p "$APP_DIR"
# Copy the checkout, minus git metadata and local caches.
tar -C "$REPO_DIR" --exclude=.git --exclude=__pycache__ --exclude=.venv -cf - . \
  | tar -C "$APP_DIR" -xf -

echo "==> Building virtualenv"
python3 -m venv "$APP_DIR/.venv"
"$APP_DIR/.venv/bin/pip" install --quiet --upgrade pip
"$APP_DIR/.venv/bin/pip" install --quiet requests beautifulsoup4

chown -R "$SERVICE_USER:$SERVICE_USER" "$APP_DIR"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "==> Writing credential template to $ENV_FILE"
  cat >"$ENV_FILE" <<'EOF'
# Your address, as entered on the council's bin lookup page.
POSTCODE=
HOUSE_NUMBER=
# Gmail account that sends the reminder. GMAIL_APP_PASSWORD must be a
# Google "app password", not your normal account password:
#   https://myaccount.google.com/apppasswords
GMAIL_ADDRESS=
GMAIL_APP_PASSWORD=
RECIPIENT_EMAIL=
EOF
else
  echo "==> Keeping existing $ENV_FILE"
fi
chown root:"$SERVICE_USER" "$ENV_FILE"
chmod 640 "$ENV_FILE"

echo "==> Installing systemd units"
install -m 644 "$REPO_DIR/deploy/bin-reminder.service" /etc/systemd/system/
install -m 644 "$REPO_DIR/deploy/bin-reminder.timer" /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now bin-reminder.timer

cat <<EOF

Done.

Next step - fill in your details:
    sudo nano $ENV_FILE

Then test it end to end (sends a real email if a collection is due tomorrow):
    sudo systemctl start bin-reminder.service
    journalctl -u bin-reminder.service -n 30 --no-pager

Check when it will next fire:
    systemctl list-timers bin-reminder.timer

To change the time, edit OnCalendar in /etc/systemd/system/bin-reminder.timer
then run: sudo systemctl daemon-reload
EOF
