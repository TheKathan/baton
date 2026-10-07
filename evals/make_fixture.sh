#!/usr/bin/env bash
# Build a realistic project with a live baton board: make_fixture.sh <dir>
set -euo pipefail
D="$1"; rm -rf "$D"; mkdir -p "$D/packages/shared/src" "$D/apps/web/src"
cd "$D"; git init -q
printf 'export interface Artifact {\n  id: string;\n  thumbUrl: string | null;\n  imageQa: "pass" | "fail" | null;\n}\n' > packages/shared/src/design.ts
printf '// gallery component (frontend)\n' > apps/web/src/Gallery.tsx
export BATON_ROOT="$D"
baton init --sprint S1 --roles orchestrator,backend,frontend,qa >/dev/null
baton post C --as backend --to frontend,qa --title "Artifact shape for the gallery" --files packages/shared/src/design.ts --cites STORY-703 - >/dev/null <<'B'
`Artifact {id, thumbUrl|null, imageQa: pass|fail|null}` in packages/shared/src/design.ts.
GET /api/runs/:id/artifacts returns Artifact[].
B
baton post Q --as qa --to frontend --title "Does the gallery show image QA status?" - >/dev/null <<'B'
STORY-703 AC-3 says failed image QA must be visible. Will the gallery show a badge for imageQa=fail? I need it for the e2e.
B
baton post B --as frontend --to backend --title "Artifacts endpoint returns 500 for runs without images" --blocks STORY-703 - >/dev/null <<'B'
GET /api/runs/:id/artifacts → 500 when a run has no images yet. Repro: run r-12 in the e2e seed.
B
baton reply B-003 --as backend "Fixed in apps/server (null check). Deployed to the e2e stack." >/dev/null
baton post D --as orchestrator --to all --title "Sprint S1 scope: gallery + image QA only" - >/dev/null <<'B'
S1 ships STORY-703 (gallery) and STORY-706 (image QA).
B
baton post H --as backend --to qa --title "S1 backend: artifacts endpoint + image QA" - >/dev/null <<'B'
- STORY-706 image QA stage done; artifacts endpoint per C-001. Gates green.
B
baton status --as backend --phase S1 --state "DONE pending QA" --handoff H-005 >/dev/null
baton status --as frontend --phase S1 --state "building gallery" >/dev/null
baton status --as qa --phase S1 --state "waiting for frontend" >/dev/null
baton post Q --as backend --to orchestrator --title "Can S2 change the artifact field names?" - >/dev/null <<'B'
Design wants thumbnailUrl instead of thumbUrl. Breaking for frontend and qa. OK for S2?
B
baton reply Q-006 --as orchestrator "Yes, in S2, announced as a contract change first." >/dev/null
