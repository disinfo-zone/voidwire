# Release Runbook

## Pipeline
1. Open GitHub Actions `Release` workflow.
2. Select target environment (`staging` or `production`).
3. Provide release/image tag.
4. For production, set `confirm_production=YES`.

## Automated Gates
- Dependency install + smoke test pass
- Alembic migrations apply cleanly
- Basic auth/public endpoint smoke checks

## Post-Deploy Checks
1. `GET /health` returns `ok`.
2. Admin login succeeds.
3. Public reading endpoint returns expected payload.
4. User login + profile read succeeds.
5. User personal reading async job enqueue/list works (`/v1/user/readings/personal/jobs`).
6. Billing checkout path responds without server errors.
7. If SMTP is enabled, send a test email from Admin > Site Settings.
8. Admin > Accounts shows personal reading job status/error rows.
9. Admin > Site Settings OAuth toggle changes `/v1/user/auth/oauth/providers` visibility.
10. Admin > Pipeline Settings updates `synthesis.banned_phrases` and personal readings reflect the change.
11. Admin > Templates includes starter personal-reading templates (`starter_personal_reading_free`, `starter_personal_reading_pro`).
12. `GET /admin/analytics/kpis` returns user/subscription/personal-reading metrics.

## Rollback
1. Redeploy previous stable image tag.
2. Re-run smoke checks.
3. If schema migration caused breakage, restore from latest known-good backup and redeploy stable tag.
