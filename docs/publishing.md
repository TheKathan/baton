# Publishing to PyPI

baton is published on PyPI as **`baton-handoff`**, so newcomers can run `uvx baton-handoff` or `pipx install baton-handoff`; the command it installs is still `baton`. (The PyPI name `baton` belongs to an unrelated project, and `agent-baton` is too close to an existing `agentbaton`.)

The release workflow ([`.github/workflows/release.yml`](../.github/workflows/release.yml)) publishes every release once the one-time setup below is done. Until then its `build` and `pypi` jobs are skipped, and a release only creates the tag and the GitHub release.

| Job | Runs when | Publishes with |
|---|---|---|
| `build`, `pypi` | repository variable `PUBLISH_PYPI` is `true` | PyPI Trusted Publishing (OIDC), environment `pypi`. No token is stored |

Both jobs check out the release tag without the deploy key, and only `pypi` gets `id-token: write`. A version that is already on PyPI is skipped, so re-running a workflow is safe.

## One-time setup

Use the names below exactly; they are the ones the workflow expects.

### 1. The `pypi` environment

Create an environment limited to `main` (Settings → Environments → New environment → Deployment branches: *Selected branches* → `main`). With the GitHub CLI:

```bash
gh api -X PUT repos/TheKathan/baton/environments/pypi \
  -F 'deployment_branch_policy[protected_branches]=false' \
  -F 'deployment_branch_policy[custom_branch_policies]=true'
gh api -X POST repos/TheKathan/baton/environments/pypi/deployment-branch-policies -f name=main -f type=branch
```

Adding yourself as a required reviewer on the environment is optional; every publish then waits for your approval.

### 2. A pending publisher on PyPI

Sign in at [pypi.org](https://pypi.org) (2FA on), open *Your account → Publishing*, and **add a new pending publisher** (GitHub tab):

- PyPI project name: `baton-handoff`
- Owner: `TheKathan`
- Repository name: `baton`
- Workflow name: `release.yml`
- Environment name: `pypi`

The first upload creates the project and turns the pending publisher into a normal trusted publisher. No API token is needed at any point.

### 3. Switch publishing on

```bash
gh variable set PUBLISH_PYPI --body true --repo TheKathan/baton
```

To stop publishing, set the variable to `false` or delete it. A release made before the variable was set is not published retroactively; the next merged PR is the first release on PyPI.

## Check it

- the release run shows `build` and `pypi` as green (not skipped);
- `https://pypi.org/project/baton-handoff/` shows the new version and *Verified details* for the repository;
- from a clean shell, `uvx baton-handoff --version` and `pipx run baton-handoff --version` print `baton <version>`.
