#!/bin/sh
set -e

# Faqat API konteyneri migratsiya va seed qiladi (bot konteyneri RUN_MIGRATIONS=0 bilan ishga tushadi)
if [ "${RUN_MIGRATIONS:-1}" = "1" ]; then
  alembic upgrade head
  python -m app.seed
fi

exec "$@"
