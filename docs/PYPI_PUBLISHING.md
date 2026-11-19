# Publishing to PyPI

Publish `akeyless-agentcore-rta` with [trusted publishing](https://docs.pypi.org/trusted-publishers/) (no API tokens in GitHub Secrets).

## Prerequisites

- Maintainer access to this repo
- A [PyPI](https://pypi.org) account
- Package name `akeyless-agentcore-rta` available (first publisher claims it)

## Step 1: Register a pending trusted publisher

1. Log in to [pypi.org](https://pypi.org)
2. **Account settings** → **Publishing** → **Add a new pending publisher**
3. Fill in:

| Field | Value |
|-------|-------|
| **PyPI Project Name** | `akeyless-agentcore-rta` |
| **Publisher** | GitHub |
| **Owner** | `akeyless-community` |
| **Repository name** | `bedrock-agentcore-akeyless-rta` |
| **Workflow name** | `publish.yml` |
| **Environment name** | `pypi` |

4. Click **Add**

## Step 2: GitHub `pypi` environment

**Settings → Environments → New environment → `pypi`**

- Required reviewers: members of `@akeyless-community/cs-admin`
- Workflow already uses `environment: pypi` and `id-token: write`

## Step 3: First release

```bash
# bump __version__ in src/akeyless_agentcore_rta/__init__.py (pyproject.toml reads it)
git tag v0.1.0
git push origin v0.1.0
gh release create v0.1.0 --title "v0.1.0" --notes "Initial release: ARA client + MCP for Bedrock AgentCore"
```

Approve the pending `pypi` environment deployment when Actions asks. After success:

```bash
pip install akeyless-agentcore-rta
```
