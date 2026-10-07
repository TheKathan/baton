#!/usr/bin/env bash
# Turn on the security features GitHub only offers for public repositories.
# Run once, right after making the repository public:
#   GH_TOKEN=<token with repo admin> scripts/enable-public-security.sh [owner/repo]
set -euo pipefail
R="repos/${1:-TheKathan/baton}"

# Fork pull requests run CI only after a maintainer approves the run.
echo '{"approval_policy":"all_external_contributors"}' \
  | gh api -X PUT "$R/actions/permissions/fork-pr-contributor-approval" --input -
# Private vulnerability reporting (SECURITY.md points reporters to it).
gh api -X PUT "$R/private-vulnerability-reporting"
# Secret scanning, plus push protection that blocks pushes containing secrets.
echo '{"security_and_analysis":{"secret_scanning":{"status":"enabled"},"secret_scanning_push_protection":{"status":"enabled"}}}' \
  | gh api -X PATCH "$R" --input - --jq '.security_and_analysis'
echo "public-repository security features enabled for ${R#repos/}"
