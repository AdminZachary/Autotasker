#!/bin/sh
set -eu

printf '\n[1/4] Backend unit and integration tests\n'
python3 -B -m unittest discover -s tests -v

printf '\n[2/4] Frontend syntax checks\n'
node --check static/state-helpers.js
node --check static/app.js

printf '\n[3/4] Frontend state smoke tests\n'
node --test tests_js/*.cjs

printf '\n[4/4] FastAPI import smoke\n'
python3 - <<'PY'
from app.main import app

paths = {route.path for route in app.routes}
required = {
    "/",
    "/new.html",
    "/styles.css",
    "/app.js",
    "/state-helpers.js",
    "/api/goals/analyze",
    "/api/goals/discuss",
    "/api/goals/confirm",
}
missing = sorted(required - paths)
if missing:
    raise SystemExit(f"Missing routes: {missing}")
print("Route smoke passed.")
PY

printf '\nPre-release checks passed.\n'
