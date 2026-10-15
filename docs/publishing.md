# Publishing to PyPI and npm

baton is published as **`agent-baton`** on PyPI and npm, so newcomers can run `uvx agent-baton`, `pipx install agent-baton` or `npx agent-baton`. (The PyPI name `baton` belongs to an unrelated project.)

The release workflow ([`.github/workflows/release.yml`](../.github/workflows/release.yml)) publishes every release, but only once the owner has done the one-time setup below. Until then the publish jobs are skipped and a release only creates the tag and the GitHub release.

| Job | Runs when | Publishes with |
|---|---|---|
| `build`, `pypi` | repository variable `PUBLISH_PYPI` is `true` | PyPI Trusted Publishing (OIDC), environment `pypi`. No token is stored |
| `npm` | repository variable `PUBLISH_NPM` is `true` | `npm publish --provenance`, environment `npm`. Trusted publishing, or an `NPM_TOKEN` secret until that is set up |

Both jobs check out the release tag without the deploy key, and only they get `id-token: write`. A version that is already on the registry is skipped, so re-running a workflow is safe.

## One-time setup

The repository allows only GitHub-owned and `TheKathan/*` actions, plus `pypa/gh-action-pypi-publish` at the commit `release.yml` pins. A workflow that names any other action is rejected before it starts, so when Dependabot bumps that pin, allow the new commit first (Settings → Actions → General, or the API below), then merge:

```bash
gh api -X PUT repos/TheKathan/baton/actions/permissions/selected-actions \
  -F github_owned_allowed=true -F verified_allowed=false \
  -f 'patterns_allowed[]=TheKathan/*' -f 'patterns_allowed[]=pypa/gh-action-pypi-publish@<new sha>'
```

Use the names below exactly; they are the ones the workflow expects.

### 1. GitHub environments

Create two environments, each limited to `main` (Settings → Environments → New environment → Deployment branches: *Selected branches* → `main`). With the GitHub CLI:

```bash
for env in pypi npm; do
  gh api -X PUT "repos/TheKathan/baton/environments/$env" \
    -F 'deployment_branch_policy[protected_branches]=false' \
    -F 'deployment_branch_policy[custom_branch_policies]=true'
  gh api -X POST "repos/TheKathan/baton/environments/$env/deployment-branch-policies" -f name=main -f type=branch
done
```

Adding yourself as a required reviewer on these environments is optional; every publish then waits for your approval.

### 2. PyPI

1. Sign in at [pypi.org](https://pypi.org) (2FA on), open *Your account → Publishing*, and **add a new pending publisher** (GitHub tab):
   - PyPI project name: `agent-baton`
   - Owner: `TheKathan`
   - Repository name: `baton`
   - Workflow name: `release.yml`
   - Environment name: `pypi`
2. The first upload creates the project and turns the pending publisher into a normal trusted publisher. No API token is needed at any point.

### 3. npm

npm can only add a trusted publisher to a package that exists, so the first release is published with a short-lived token:

1. On [npmjs.com](https://www.npmjs.com) (2FA on), create a **granular access token**: *Read and write* on packages, the shortest expiry (7 days), and *Bypass two-factor authentication* so CI can publish.
2. Store it as the secret `NPM_TOKEN` in the **`npm` environment** (not as a repository secret):
   `gh secret set NPM_TOKEN --env npm --repo TheKathan/baton`
3. After the first publish (step 5), open *agent-baton → Settings → Trusted publisher → GitHub Actions* and enter: organization or user `TheKathan`, repository `baton`, workflow filename `release.yml`, environment `npm`.
4. On the same page set *Publishing access* to **Require two-factor authentication and disallow tokens**. Then delete the secret (`gh secret delete NPM_TOKEN --env npm --repo TheKathan/baton`) and revoke the token on npmjs.com. Later releases publish through OIDC, still with provenance.

### 4. Switch the jobs on

```bash
gh variable set PUBLISH_PYPI --body true --repo TheKathan/baton
gh variable set PUBLISH_NPM --body true --repo TheKathan/baton
```

Either can be enabled on its own. To stop publishing, set the variable to `false` or delete it.

### 5. Verify

The next merged PR releases and publishes. Then check:

- the release run shows `build`, `pypi` and `npm` as green (not skipped);
- `https://pypi.org/project/agent-baton/` shows the new version, the README with its images, and *Verified details* for the repository;
- `npm view agent-baton version` prints the new version, and `npm audit signatures` in a project that installs it reports a verified provenance attestation;
- from a clean shell: `uvx agent-baton --version`, `pipx run agent-baton --version` and `npx agent-baton --version` all print `baton X.Y.Z`.

A release made before the variables were set is not published retroactively; the next release is the first one on the registries.

## How the launcher picks Python

The npm package only ships a launcher (`bin/baton`) and the Python sources, so `npx agent-baton` needs a Python 3.11 or newer. When `python3` is older (a stock macOS has 3.9), the launcher re-runs itself with the newest `python3.14` … `python3.11` on `PATH`; when there is none, it exits with a message that says what to install, or to use `uvx agent-baton`, which fetches a suitable Python itself.
