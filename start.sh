#!/bin/sh
# Backend runs internally on 8001 (the Next.js rewrite target).
# The frontend serves the public port: Render sets PORT; 10000 is the local default.
cd /app/backend && uvicorn app.main:app --host 127.0.0.1 --port 8001 &
cd /app/frontend && exec npx next start -p "${PORT:-10000}" -H 0.0.0.0
