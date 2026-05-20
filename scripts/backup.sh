#!/usr/bin/env bash
set -euo pipefail

# Env:
#   PGUSER, PGPASSWORD, PGDATABASE, PGHOST  (Postgres connection)
#   B2_BUCKET, B2_KEY_ID, B2_APP_KEY        (Backblaze creds)

STAMP=$(date -u +%Y%m%dT%H%M%SZ)
TMP_DIR=$(mktemp -d)
DUMP_FILE="$TMP_DIR/nbtool-${STAMP}.sql.gz"

echo "==> dumping $PGDATABASE"
pg_dump --no-owner --no-privileges "$PGDATABASE" | gzip -9 > "$DUMP_FILE"

echo "==> uploading to B2 bucket $B2_BUCKET"
# Requires b2 CLI installed and authorized: b2 authorize-account $B2_KEY_ID $B2_APP_KEY
b2 upload-file "$B2_BUCKET" "$DUMP_FILE" "nbtool/${STAMP}.sql.gz"

echo "==> pruning local dumps older than 7 days"
find /opt/nbtool/backups -name "*.sql.gz" -mtime +7 -delete 2>/dev/null || true

rm -rf "$TMP_DIR"
echo "backup OK"
