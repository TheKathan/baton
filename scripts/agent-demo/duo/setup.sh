#!/bin/sh
# Usage: setup.sh <dir>   (builds the scratch project)
set -eu
rm -rf "$1" && mkdir -p "$1/src" && cd "$1"
git init -q -b main
cat > src/health.js <<'JS'
// GET /api/health: reports that the service is up.
export function health(_req, res) {
  res.json({ status: "ok" });
}
JS
cat > src/routes.js <<'JS'
import { health } from "./health.js";

export function routes(app) {
  app.get("/api/health", health);
}
JS
baton init --sprint S1 --roles frontend,backend,qa >/dev/null
git add -A && git -c user.name=demo -c user.email=demo@example.com commit -qm "S1-A: health endpoint"
