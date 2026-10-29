# Deployment

**Status: prepared, not yet deployed.** No public URL exists yet. URLs will be added
to the README only after the smoke test in §5 passes against them.

## 1. Chosen hosting (checked 2026-10-29)

| Part | Provider | Plan | Why |
|---|---|---|---|
| PostgreSQL | **Neon** | Free | Permanent free plan, no card required, 1 GB storage per project, connection pooling. Compute suspends after 5 min idle and resumes on the next query |
| FastAPI backend | **Render** web service | Free | Native Python runtime, Frankfurt region, HTTPS, deploys from GitHub |
| React frontend | **Render** static site | Free | Same account and Blueprint as the API; CDN; SPA rewrites; security headers |
| CI | GitHub Actions | Free | Already running (backend, frontend, e2e) |

Rejected options:
- **Render free Postgres**: expires 30 days after creation (then a 14-day grace period
  and deletion), which breaks the persistence requirement.
- **Vercel Hobby** for the frontend: viable (personal, non-commercial use), but it
  would add a third account for no functional gain.

**Trade-offs and costs.** Free Render web services spin down after 15 minutes without
traffic and take about one minute to wake, so the first request after idle is slow.
The UI shows a loading state while it waits. Removing the sleep requires a paid Render
instance (about $7/month as of 2026). The free tier includes 750 instance hours per
workspace per month, enough for one always-on service. Neon's first query after
suspension adds a short delay.

Sources: [Render free tier](https://render.com/docs/free) ·
[Render Blueprint spec](https://render.com/docs/blueprint-spec) ·
[Neon pricing](https://neon.com/pricing) ·
[Vercel Hobby plan](https://vercel.com/docs/plans/hobby-plan). Re-check these before
relying on them: free tiers change.

## 2. Configuration

Backend (Render → review-harness-api → Environment):

| Variable | Value |
|---|---|
| `DATABASE_URL` | Neon connection string (`postgresql://…?sslmode=require`). The app converts it to the psycopg driver form |
| `CORS_ALLOWED_ORIGINS` | The frontend URL, e.g. `https://review-harness-web.onrender.com` (no trailing slash) |
| `APP_ENV`, `PLANNER`, `RATE_LIMIT_PER_MINUTE`, `PYTHON_VERSION` | Set by `render.yaml` |
| `ANTHROPIC_API_KEY` | **Not set.** The public demo uses the mock planner |

Frontend (Render → review-harness-web → Environment):

| Variable | Value |
|---|---|
| `VITE_API_BASE_URL` | The API URL, e.g. `https://review-harness-api.onrender.com`. Public by design: Vite embeds it in the bundle |

## 3. Steps that need your accounts

1. **Neon**: sign up at neon.tech (GitHub login works) → create a project named
   `review-harness`, choosing an EU region (e.g. Frankfurt) if offered → copy the
   connection string from *Connect*.
2. **Render**: sign up at render.com with GitHub → *New → Blueprint* → select the
   `ai-agent-review-harness` repository. Render reads `render.yaml` and creates both
   services. When prompted:
   - `DATABASE_URL`: the Neon string.
   - `CORS_ALLOWED_ORIGINS`: `https://review-harness-web.onrender.com`
   - `VITE_API_BASE_URL`: `https://review-harness-api.onrender.com`

   If Render assigns different hostnames (the names may be taken), update both values
   to the real URLs and redeploy both services.
3. Wait for both deploys to finish. The API log should show
   `Running upgrade -> 0001, initial schema` on the first start.

## 4. Release procedure (after the first deploy)

1. Push to `main`. CI runs backend, frontend, and e2e checks.
2. Render auto-deploys `main`. Only rely on a deploy whose commit passed CI. To make
   this strict, set *Auto-Deploy* to "After CI checks pass" in the Render service
   settings.
3. Migrations run at API start (`alembic upgrade head`). Every migration must be
   backward-compatible with the previous release, because the old instance keeps
   serving until the new one is healthy.
4. Run the smoke test (§5).

**Rollback:** in Render, *Rollback* to the previous deploy. A migration that must be
undone needs `alembic downgrade -1` run against the database from a trusted machine,
after a Neon branch or backup has been taken.

## 5. Smoke test (run against the real URLs)

```bash
API=https://review-harness-api.onrender.com
WEB=https://review-harness-web.onrender.com
curl -s $API/health                      # {"status":"ok",...}  (first call may take ~1 min)
curl -s $API/health/ready                # {"database":"ok"}
curl -s -X OPTIONS $API/api/v1/tasks -H "Origin: $WEB" \
     -H "Access-Control-Request-Method: POST" -D - -o /dev/null | grep -i access-control-allow-origin
```

Then, in the browser at `$WEB`:

1. Create the "Risky irreversible proposal" example → the plan shows *High risk*.
2. Request a revision → attempt 2 proposes archiving → approve → *Run approved actions*
   → the task is *Completed* and the archive action shows *Executed* and *Verified*.
3. Create the "Prompt injection" example → the shell action shows *Blocked by policy*
   and *Skipped*.
4. **Persistence:** in Render, *Manual Deploy → Restart service* for the API, then
   reload the task page. The task and its audit trail must still be there.

Record the date, commit, and results in `docs/progress.md`, then add the URLs to the
README.

## 6. Monitoring and recovery

- **Health:** Render probes `/health` (liveness). `/health/ready` reports database
  reachability for manual checks or an external uptime monitor.
- **Logs:** Render service logs (request lines and exception traces; no request
  bodies or secrets).
- **Database:** Neon's console shows usage. The free plan keeps a 6-hour restore
  window. For anything that matters, take a Neon branch before risky migrations.
- **Demo data growth:** the API is public and unauthenticated. If storage nears the
  limit, truncate the tables from a trusted machine (with the database name guard
  temporarily adjusted) or create a fresh Neon branch.
