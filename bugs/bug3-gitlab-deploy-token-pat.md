# Bug: dbt Cloud API returns 500 when creating GitLab `deploy_token` repository via PAT

**Severity:** High
**Component:** `sinter/services/repositories/legacy_create.py`
**Reproducible:** Yes (100%)
**Environment:** Multi-tenant (cloud.getdbt.com / *.dbt.com)

## Summary

The dbt Cloud v3 API returns HTTP 500 (Internal Server Error) when creating a repository with `git_clone_strategy: deploy_token` and a valid `gitlab_project_id` via a Personal Access Token (PAT) or Service Token. The identical operation succeeds when performed through the browser UI.

## Root Cause

The repository creation flow for GitLab `deploy_token` repos requires a user-specific GitLab OAuth token to call the GitLab API (create deploy tokens, webhooks, etc.). This token is stored in `UserSocialAuth` and is obtained via `get_gitlab_access_token(user_id)`.

When the request is made via PAT:

1. `RequestContext.current().user_id` resolves to the PAT-owning user's ID
2. `get_gitlab_access_token(user_id)` returns `None` because:
   - The user's GitLab OAuth linkage (`UserSocialAuth`) was established through a browser OAuth flow
   - The PAT request context may not have the same user, or the user's OAuth session may not be discoverable in this context
3. `None` is passed to `GitLabApplicationIntegration.create_deploy_token(gitlab_access_token=None)`
4. `_instantiate_oauth_gitlab(None)` calls `gitlab.Gitlab(url, oauth_token=None).auth()`
5. This raises an exception that is **not** caught by the existing `except DisassociatedAccountException` / `except GitlabCreateError` handlers, resulting in an unhandled 500

### Why the browser works

When a user creates the same repository through the dbt Cloud UI:

- The browser session contains the user's active OAuth context
- `get_gitlab_access_token(user_id)` finds the `UserSocialAuth` record and returns a valid token
- The full deploy_token + webhook + credentials flow completes successfully

## Code Trace

### Entry point

```
POST /api/v3/accounts/{account_id}/projects/{project_id}/repositories/
Payload: { "remote_url": "group/project", "git_clone_strategy": "deploy_token", "gitlab_project_id": 12345 }
Auth: PAT (dbt Cloud Personal Access Token)
```

### Flow

```
api/v3/views/repository.py
  → services/repositories/legacy_create.py::find_or_create()
    → create()
      Line 99:  git_clone_strategy = deploy_token (because gitlab_project_id is truthy)
      Line 108: user_id = RequestContext.current().user_id  (resolves to PAT-owner)
      Line 126: if user_id and gitlab_project_id:  → True
      Line 137:   get_gitlab_access_token(user_id) → None
      Line 136:   integration.create_deploy_token(gitlab_access_token=None, ...)
        → clients/gitlab/integration.py::create_deploy_token()
          → _instantiate_oauth_gitlab(None)
            → gitlab.Gitlab(url, oauth_token=None).auth()
            → UNHANDLED EXCEPTION → 500
```

### Key files

| File | Role |
|------|------|
| `sinter/services/repositories/legacy_create.py` | Repository creation orchestration |
| `sinter/oauth/utils/gitlab.py` | `get_gitlab_access_token()` — retrieves user OAuth token |
| `sinter/clients/gitlab/integration.py` | `GitLabApplicationIntegration` — GitLab API operations |
| `sinter/services/account_gitlab_application/__init__.py` | `get_gitlab_base_url()` — account GitLab config |

## Steps to Reproduce

1. Configure a GitLab Application integration on a dbt Cloud account (Account Settings → Integrations → GitLab)
2. As a user, authorize GitLab through Profile → Linked Accounts → GitLab
3. Create a PAT for that user (Account Settings → Service Tokens or Profile → API Access)
4. Call the repository creation API with that PAT:

```bash
curl -X POST "https://<host>/api/v3/accounts/<account_id>/projects/<project_id>/repositories/" \
  -H "Authorization: Token <PAT>" \
  -H "Content-Type: application/json" \
  -d '{
    "account_id": <account_id>,
    "project_id": <project_id>,
    "remote_url": "group/project",
    "gitlab_project_id": 12345,
    "state": 1
  }'
```

**Expected:** 200 OK with repository created (or 400 with a clear error about missing GitLab credentials)
**Actual:** 500 Internal Server Error

```json
{
  "status": {
    "code": 500,
    "is_success": false,
    "user_message": "internal-server-error",
    "developer_message": ""
  }
}
```

## Fix Layers

There are three independent layers to this problem. The first two are implemented; the third is what would fully resolve the issue.

### Layer 1: Crash prevention + token resilience (PR: `fix/gitlab-deploy-token-pat-500`)

The PR addresses two independent bugs in a single branch:

#### Fix A — Token refresh fallback (`sinter/oauth/utils/gitlab.py`)

When `get_gitlab_access_token` detects an expired token and the refresh fails (network error, invalid refresh token, etc.), the function previously returned `None` — discarding the stored token entirely. The stored token may still be valid (clock skew, grace period, or GitLab's conservative expiry). This fix falls back to the stored token instead of giving up:

```python
except Exception as e:
    ...
    # Refresh failed — fall back to the stored token
    gitlab_token = _stored_access_token(social_auth)
```

**This is the Layer 3 fix.** For PAT callers, the mechanism is identical to the browser UI — the PAT resolves to the same `user_id` (via `RequestContext.build_account_scoped_pat_context()`), and the token is looked up from `UserSocialAuth` in the database. No secrets are passed through the API. The only prerequisite is that the PAT-owning user has previously linked their GitLab account via Profile → Linked Accounts.

#### Fix B — Null guard with clear error (`sinter/services/repositories/legacy_create.py`)

If no token is available at all (user hasn't linked GitLab, no `UserSocialAuth` record exists), the previous code passed `None` to `_instantiate_oauth_gitlab()`, causing an unhandled exception → 500. The fix checks for `None` before the GitLab API call and returns a 400 with an actionable message:

```json
{
  "status": {
    "code": 400,
    "data": {
      "authentication_error": "No GitLab credentials found for the current user. To create repositories with the GitLab native integration, link your GitLab account via Profile → Linked Accounts."
    }
  }
}
```

The same guard is applied to `_save_gitlab_info()`, which could also crash with a `None` token on the `create_deploy_key` path.

### Layer 2: Terraform module workaround (implemented in `terraform-dbtcloud-yaml`)

**What it does:** Automatically downgrades `deploy_token` → `deploy_key` for all GitLab repos in the migration module. Converts the GitLab project path (`group/project`) to an SSH URL (`git@gitlab.com:group/project.git`) and nulls out `gitlab_project_id`.

**What it loses:** Native GitLab features — deploy tokens, webhooks, commit status reporting, and PR comments are not configured. The repo is connected via SSH deploy key only.

**This is what currently unblocks the Terraform provider.**

### Layer 3: Make `deploy_token` work via PAT (included in PR — Fix A)

**No new secrets or API parameters needed.** The mechanism is the same one the browser UI already uses:

1. User links GitLab once via browser (Profile → Linked Accounts → GitLab)
2. dbt Cloud stores the user's GitLab OAuth token server-side in `UserSocialAuth`
3. On repository creation, the backend looks up this stored token by `user_id`
4. The backend uses the token internally to call the GitLab API (create deploy token, webhook, etc.)
5. The API caller **never sees the GitLab OAuth token** — it stays entirely server-side

For PAT requests, `RequestContext.build_account_scoped_pat_context()` resolves the PAT to the same `user` object as a browser session. The `user_id` is identical. The DB lookup in `get_gitlab_access_token(user_id)` is a pure database query — no session, no cookie, no browser context required.

**The only remaining failure case** after this fix is Path 1 — the PAT-owning user has never linked their personal GitLab account (no `UserSocialAuth` record). This requires a one-time browser action (Profile → Linked Accounts → GitLab) and cannot be automated. Fix B handles this case with a clear 400 error.

## Impact

| Audience | Current behavior | After PR (Layers 1+3) |
|----------|-----------------|----------------------|
| **Browser UI users** | Works | Works |
| **PAT callers (user linked GitLab)** | 500 crash | **200 success** |
| **PAT callers (user NOT linked)** | 500 crash | 400 clear error |
| **Terraform provider (user linked)** | `apply` fails (500) | **`apply` succeeds** |
| **Terraform provider (user not linked)** | `apply` fails (500) | `apply` fails (400) with actionable message |
| **Migration module** | Uses `deploy_key` fallback | Can remove fallback after PR ships |

**Prerequisite for success:** The PAT-owning user must have completed the one-time personal GitLab OAuth link (Profile → Linked Accounts → GitLab). This is separate from the account-level GitLab Application integration. No secrets are passed through the API — the backend looks up the stored OAuth token from `UserSocialAuth` using the same `user_id` the browser uses.

## Who is affected

Any customer using Terraform, the dbt Cloud API, or any automation tool to create repositories with GitLab native integration (`git_clone_strategy: deploy_token`).

## Current workaround

In the migration module (`terraform-dbtcloud-yaml`), we automatically downgrade `deploy_token` → `deploy_key` for GitLab repos, converting the GitLab project path to an SSH URL. This loses native GitLab features (deploy token, webhooks, commit status) but allows repository creation to succeed via the Terraform provider.
