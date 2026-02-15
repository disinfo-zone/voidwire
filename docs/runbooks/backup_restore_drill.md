# Backup/Restore Drill Runbook

## Goal
Validate that backup storage is writable/readable and that restore workflows remain usable.

## Frequency
- Daily lightweight drill (`POST /admin/backup/drill`)
- Monthly full restore drill in staging

## Lightweight Drill (No DB Restore)
1. Open Admin UI: `Backups`.
2. Run `Run Drill`.
3. Confirm response status is `ok` and note duration.
4. If failed:
   - Check backup storage credentials in `Site Settings`.
   - Check API logs for `Backup drill failed`.

## Full Restore Drill (Staging)
1. Trigger `Create Backup`.
2. Verify backup appears in listing.
3. Restore backup into staging DB.
4. Run smoke checks:
   - `GET /health`
   - Admin login
   - Public reading fetch
5. Record result timestamp and operator in ops notes.

## Rollback Guidance
- Keep latest known-good backup from prior day before any production restore.
- If post-restore smoke checks fail, restore previous known-good backup immediately.

