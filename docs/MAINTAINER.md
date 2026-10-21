# Maintainer guide: repository access controls

Settings applied to restrict changes so **people outside the Akeyless org must be reviewed and approved** before code lands on `main` or ships to PyPI.

## What is enforced

| Control | Effect |
|---------|--------|
| **Branch protection on `main`** | No direct pushes; changes only via pull request |
| **Push restrictions** | Only `@akeyless-community/cs-admin` can push or merge to `main` |
| **CODEOWNERS** (`@akeyless-community/cs-admin`) | PRs require approval from a `cs-admin` team member |
| **CI required** | `ci-success` must pass before merge |
| **Stale review dismissal** | New commits invalidate prior approvals |
| **Last-push approval** | Re-approval required after new commits |
| **`pypi` environment** | PyPI publish requires approval from a maintainer |

> **Note:** This repo is **public**, so push restrictions are available on **GitHub Free for organizations** and limit merge/push to `main` to `cs-admin`.

## Files in this repo

- [`.github/CODEOWNERS`](../.github/CODEOWNERS) — routes all paths to `@akeyless-community/cs-admin`
- [`.github/pull_request_template.md`](../.github/pull_request_template.md) — reminds external contributors about review
- [`.github/workflows/ci.yml`](../.github/workflows/ci.yml) — `ci-success` gate for branch protection
- [`.github/workflows/publish.yml`](../.github/workflows/publish.yml) — uses protected `pypi` environment

## Org settings (verify in GitHub UI)

These are **organization-level** and cannot be stored in the repo. An org admin should confirm:

1. **Member privileges → Base permissions** — recommended **Read** for non-maintainers
2. **Actions → Fork pull request workflows** — require approval for outside collaborators
3. **Teams → cs-admin** — maintainers who can approve PRs and PyPI releases

## Re-applying branch protection

```bash
gh api \
  --method PUT \
  repos/akeyless-community/bedrock-agentcore-akeyless-rta/branches/main/protection \
  --input - <<'EOF'
{
  "required_status_checks": {
    "strict": true,
    "checks": [
      { "context": "ci-success" }
    ]
  },
  "enforce_admins": true,
  "required_pull_request_reviews": {
    "dismiss_stale_reviews": true,
    "require_code_owner_reviews": true,
    "required_approving_review_count": 1,
    "require_last_push_approval": true
  },
  "restrictions": {
    "users": [],
    "teams": ["cs-admin"],
    "apps": []
  },
  "required_linear_history": true,
  "allow_force_pushes": false,
  "allow_deletions": false,
  "required_conversation_resolution": true
}
EOF
```

If `restrictions` fails or comes back empty, set **Restrict who can push** to `@akeyless-community/cs-admin` in **Settings → Branches → main**.

## PyPI environment

**Repository → Settings → Environments → pypi → Required reviewers** from `@akeyless-community/cs-admin`.

Also configure **Trusted publishing** on PyPI for project `akeyless-agentcore-rta` (see [PYPI_PUBLISHING.md](PYPI_PUBLISHING.md)). Publishing a GitHub Release starts the workflow; a reviewer must approve the environment deployment.
