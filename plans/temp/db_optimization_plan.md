# Implementation plan: blob storage, then Postgres

| Item | Decision |
| --- | --- |
| Goal | No SQLite and no local run/media files. Postgres holds state; an S3-compatible bucket holds files. |
| Order | Blob storage (phases 1-4) first; Postgres (phases 5-9) second; cleanup last. |
| New deps | `psycopg[pool]` and `boto3`. Neither is installed. |
| Host | GCP (Cloud SQL + GCS) or Cloudflare (R2 + external Postgres). Only `.env` differs. |
| Out of scope | Desktop app. `tools/taktik-bot` keeps its own SQLite (separate tool). |

## Verified inventory

| # | Fact | Where |
| --- | --- | --- |
| 1 | 6 DBs: `jobs`, `video_jobs`, `credits`, `media`, `profiles`, `traffic_pools` | `local/app-runs` |
| 2 | `traffic_pools.db` code lives outside the backend, in the analyzer | `tools/loop/viral_analyzer/cache.py` |
| 3 | The analyzer passes `db_path` through `config.py`, `glasser.py` and `pipeline.py` | same package |
| 4 | 42 run dirs but only 18 job rows: ~24 orphan dirs | `ls` vs `jobs.db` |
| 5 | Export route reads the job snapshot from the DB, not from `result.json` | `server.py` L251 |
| 6 | `harness.lock` is an `fcntl.flock` on a local file | `research.py` L505 |
| 7 | Job subprocesses are forked with `multiprocessing` and call the store | `handler.py` |
| 8 | Money columns are `INTEGER` (micro-USD); Postgres `INTEGER` is 32-bit | `credits.py`, `video_jobs.py` |
| 9 | Non-portable SQL: `INSERT OR IGNORE` (`profiles.py` L303-358), `sqlite_master`/`PRAGMA table_info` (`profiles.py` L238-267), `rowcount` | grep |
| 10 | Claim logic relies on `BEGIN IMMEDIATE` to serialize | `store.py` `claim`, `video_jobs.py` `claim_next_pending` |

## Phase order

```text
0 infra -> 1 blobs -> 2 media -> 3 videos -> 4 runs
-> 5 db.py -> 6 stores -> 7 analyzer -> 8 server -> 9 purge -> 10 migrate
```

## Environment

| Variable | Purpose |
| --- | --- |
| `DATABASE_URL` | Postgres DSN |
| `DB_POOL_MAX` | Pool size per process; default 10 |
| `BLOB_ENDPOINT`, `BLOB_BUCKET`, `BLOB_ACCESS_KEY`, `BLOB_SECRET_KEY`, `BLOB_REGION` | S3 API (RustFS in dev, R2 uses `auto`, GCS uses HMAC keys) |
| `RETENTION_DAYS` | Run and video retention; default 30 |
| `API_THREADS` | Request pool size; default 64 |

All blank in `.env.example`. Confirm `.env` is gitignored before filling values.

## Phases

| Phase | Steps | Exit check |
| --- | --- | --- |
| 0 Infra | Update Docker for local dev and tests; see the Docker table below. | `docker compose up` healthy; `psql` and an S3 `ls` connect from the host |
| 1 `blobs.py` | Functions: `put(key, data, content_type)`, `get(key)`, `download(key, path)`, `upload_file(key, path)`, `delete_prefix(prefix)`, `url(key, ttl, filename)`. `delete_prefix` lists then deletes one key at a time, since GCS interop has no batch delete. Lazy singleton client. | Round-trip test passes on RustFS, including a presigned URL with a Range header |
| 2 Media | `save_media`: validate, `put` to `media/<user>/<id>.<ext>`, then insert. Store the key in the existing `path` column for now. `delete_media`: delete row, then blob. `GET /api/media/<id>`: check ownership, then 302 to `url`. `video_jobs._run_job` (L320-328) uses `blobs.get`. Remove `media_dir`. | Upload, list, fetch and delete work |
| 3 Videos | `video_engine` writes to a temp file; `_run_job` calls `upload_file("videos/<user>/<job>/output.mp4")`, then `mark_completed(key)`. `GET /api/videos/<id>/file`: 302 to `url`; `?download` sets the filename. Delete the Range code (`server.py` L330-372). `delete_job`: `delete_prefix`, no `rmtree`. | Player seeks; download works |
| 4 Run dirs | `research.py` submit: `put("runs/<id>/input.xlsx")`; drop `run_dir` from the job dict and from `mkdir`. `run_job`: use `tempfile.TemporaryDirectory`, `download` the input, run sheets there; `shared_cache` becomes a subdir of the temp dir. After each sheet, `put` `result.json`; do not upload `viral_reels_48h.json`. `server.py` L482: `delete_prefix("runs/<id>/")`. Worker start sweeps `job-*` temp dirs older than 1 day, since SIGKILL skips cleanup. | A job completes with `RUNS_ROOT` unused |
| 5 `db.py` | `ConnectionPool` created lazily per PID, because forked job processes must not reuse the parent pool. `tx()` yields a connection and commits or rolls back. `init_schema()` runs `schema.sql` once at import. Use `conn.execute` so store code keeps the same call shape. | Schema applies twice cleanly |
| 6 Stores | Port `store.py`, `credits.py`, `media.py`, `video_jobs.py` and `profiles.py` (rules below). Delete every `_tx`, `_ro`, PRAGMA and `OperationalError` retry loop. Constructors lose `db_path`. | Backend tests pass on Postgres |
| 7 Analyzer | `connect_db` ignores `db_path` and uses `db.py`. `SCHEMA_SQL` moves into `schema.sql`. Delete `migrate_fragmented_storage` and `resolve_db_path`. Remove `db_path` from `config.py`, `glasser.py`, `pipeline.py`, `research.py` L631, then the tests. | Pipeline test passes; `grep db_path tools/loop` is empty |
| 8 Server and locks | Bounded pool: subclass `ThreadingHTTPServer`, override `process_request` to submit to a `ThreadPoolExecutor(API_THREADS)`; set `request_queue_size = 256`. Replace the `fcntl` harness lock with `pg_advisory_lock`. | 200 parallel requests do not exceed `API_THREADS` threads |
| 9 Purge | `purge_expired()`: select jobs and video jobs older than `RETENTION_DAYS` in a final state, delete the row, then `delete_prefix`. Run hourly from the worker loop. Optional bucket lifecycle rule as a backstop. | Expired fixtures are removed from DB and bucket |
| 10 Migrate and remove | Run `migrate_legacy.py` (rules below). Then delete it, the `.db`, `-wal` and `-shm` files, and `local/app-runs` data. | `grep -r sqlite3 tools/app tools/loop` is empty |
| 11 Verify | Load test with locust or k6 at 100, 500 and 1000 users: list jobs, snapshot, credit reserve, media fetch. Record p95 and errors. | Targets met |

## Docker and local testing

| File | Change |
| --- | --- |
| `docker-compose.yml` | Add `postgres` (`postgres:16`, `POSTGRES_PASSWORD` from `.env`, named volume, `pg_isready` healthcheck, port 5432 published to localhost). Add `rustfs` (`rustfs/rustfs`, pinned tag; S3 on 9000, console on 9001, both published to localhost; env `RUSTFS_VOLUMES`, `RUSTFS_ADDRESS`, `RUSTFS_CONSOLE_ADDRESS`, `RUSTFS_ACCESS_KEY`, `RUSTFS_SECRET_KEY` from `.env`; `curl` healthcheck on `:9000/health`; named volume; runs as UID 10001, so use a named volume, not a bind mount). Add `rustfs-init` (`amazon/aws-cli`, runs once, `s3 mb` for `BLOB_BUCKET`, depends on `rustfs` healthy). |
| `docker-compose.yml` `backend` | Add `depends_on` with `condition: service_healthy` for `postgres`, and `service_completed_successfully` for `rustfs-init`. Pass `DATABASE_URL` and `BLOB_*` using the in-network hosts `postgres` and `rustfs`. Drop `VIRAL_APP_RUNS=/data/runs` and the `aibrand-data` volume once phase 10 passes; keep the HF cache volume. |
| `Dockerfile` | Add `psycopg[binary,pool] boto3` to the existing `pip install` line (there is no requirements file). Remove `/data` and `VOLUME /data` after phase 10. Container temp dirs replace run dirs. |
| `Dockerfile.dockerignore` | No change; `tools/app/backend/.env` stays excluded so secrets are not baked in. |
| `.env.example` | Add `DATABASE_URL`, `POSTGRES_PASSWORD`, `BLOB_*`, `RETENTION_DAYS`, `API_THREADS`, `DB_POOL_MAX`. Local-dev values point at `localhost`; blank secrets. Rewrite the stale comment about the SQLite `jobs.db` and `VIRAL_APP_RUNS`. |
| Host-run tests | Start only the deps with `docker compose up -d postgres rustfs rustfs-init`. Run the backend tests from the host with `DATABASE_URL` and `BLOB_ENDPOINT` set to `localhost`. No test image is needed. |
| Separate test DB | Create `aibrand_test` in Postgres and a `test-` bucket prefix, so tests never touch dev data. The truncate fixture refuses to run unless the DB name ends in `_test`. |
| Full-stack check | `docker compose up --build backend` then call `/api/health`, upload media, and run one job end to end. |
| Reset | `docker compose down -v` wipes Postgres and RustFS, giving a clean slate for migration rehearsal. |

## Store port rules

| SQLite | Postgres |
| --- | --- |
| `?` placeholder | `%s`; a literal `%` in `LIKE` becomes `%%` |
| `INTEGER` for balance, delta, cost, bytes, sizes | `BIGINT` |
| `INTEGER PRIMARY KEY AUTOINCREMENT` | `BIGSERIAL` |
| `INSERT OR IGNORE` | `INSERT ... ON CONFLICT DO NOTHING` |
| `cursor.lastrowid` | `RETURNING id` |
| `REAL` | `DOUBLE PRECISION` |
| ISO-string timestamps | Keep as `TEXT` (smallest diff). Ceiling: no SQL date math. |
| `jobs.data` JSON text | `JSONB`; keep the whole-document update inside `SELECT ... FOR UPDATE`, so locks are per row, not per DB |
| `ALTER TABLE ADD COLUMN` migrations, `sqlite_master` | Delete; `schema.sql` is the only source |
| `path` / `video_path` columns | Rename to `blob_key` in `schema.sql` |
| `BEGIN IMMEDIATE` claim | `pg_advisory_xact_lock` at the start of `claim` and `claim_next_pending`; `FOR UPDATE SKIP LOCKED` for the row pick. Per-client caps stay correct. |
| Credit reserve | One `UPDATE ... WHERE balance >= %s RETURNING balance`, plus the ledger insert in the same transaction |

## Schema and indexes

| Table | Indexes and constraints |
| --- | --- |
| `jobs` | `(status, client_id)`, `(user_id, created_at DESC)` |
| `job_logs` | PK `seq`; `(job_id, seq)`; `ON DELETE CASCADE` to `jobs` |
| `video_jobs` | `(status, created_at)`, `(user_id, status)` |
| `user_credits`, `credit_ledger` | PK `user_id`; `(user_id, id DESC)` |
| `user_media` | `(user_id, kind)` |
| `topics`, `profiles` | Same PKs and unique keys as now; `(user_id, topic_slug)` |
| `profile_cache`, `videos`, `metric_snapshots` | Copy from `cache.py`; keep `(author_handle)` and `(video_id, timestamp)` |

## Migration rules

| Step | Action |
| --- | --- |
| 1 | Copy `local/app-runs` to a backup outside the repo. |
| 2 | Read each `.db` with `sqlite3`; this is the only remaining use. |
| 3 | Media and videos: upload the file first, then insert the row with its key. |
| 4 | Jobs: upload `input.xlsx` for the 18 job rows only. Skip the ~24 orphan dirs and report them. |
| 5 | Use `ON CONFLICT DO NOTHING`, so a rerun is safe. |
| 6 | Reset each `BIGSERIAL` sequence with `setval` to `max(id)`. |
| 7 | Compare row counts per table; fail loudly on mismatch. |

## Tests

| Area | Change |
| --- | --- |
| Fixtures | Tests need `DATABASE_URL` and RustFS. Replace `Path(tmp) / "x.db"` with a fixture that truncates tables per test. |
| Files | `test_backend.py`, `test_credits.py`, `test_media.py`, `test_video_jobs.py`, `test_server_video_routes.py`, `test_video_engine.py` |
| New | `test_blobs.py` round-trip; a concurrency test with 20 threads that checks no double claim and no negative balance |

## Risks

| Risk | Mitigation |
| --- | --- |
| Connection exhaustion (API procs x pool + workers) | Job subprocess pool max 2; add pgbouncer if near `max_connections` |
| Presigned URLs blocked by browser CORS | Set a bucket CORS rule for the app origin |
| Row exists but blob missing | Purge deletes row first; the file route returns 404 on a missing key |
| Temp disk fills on workers | Size scratch disk for video downloads; the startup sweep removes stale dirs |
| Rollback | Revert the commit and restore the backup; the legacy `.db` files stay until phase 10 passes |

**Next step:** approve and I start at phase 0.
