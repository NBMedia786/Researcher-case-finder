#!/usr/bin/env bash
set -euo pipefail

cd /opt/nbtool
echo "==> pulling latest"
git pull --ff-only

echo "==> backend deps"
cd backend
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

echo "==> db migrations"
alembic upgrade head

echo "==> frontend build"
cd ../frontend
pnpm install --frozen-lockfile
pnpm build

echo "==> restart services"
sudo systemctl restart nbtool-api.service
sudo systemctl restart nbtool-worker.service
sudo systemctl restart nbtool-beat.service
sudo systemctl restart nbtool-frontend.service

echo "==> health"
curl -fsS http://127.0.0.1:8000/health
echo
echo "deploy OK"
