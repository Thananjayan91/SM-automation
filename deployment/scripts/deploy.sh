#!/bin/bash
# Deployment script for AI Social Publisher on Ubuntu EC2
set -e

APP_DIR="/opt/ai-social-publisher"
BACKEND_DIR="$APP_DIR/backend"

echo "=== AI Social Publisher Deployment ==="

# 1. Pull latest code
cd "$APP_DIR"
git pull origin main

# 2. Install dependencies
cd "$BACKEND_DIR"
"$APP_DIR/.venv/bin/pip" install -r requirements.txt --quiet

# 3. Run database migrations
"$APP_DIR/.venv/bin/flask" db upgrade

# 4. Restart services
sudo systemctl reload-or-restart ai-social-publisher
sudo systemctl reload-or-restart ai-social-publisher-worker

echo "=== Deployment complete ==="

