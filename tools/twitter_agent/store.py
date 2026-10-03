"""Transactional draft queue, attempt quotas, audit trail, and submission lock."""

from contextlib import contextmanager
from dataclasses import asdict
import fcntl
import json
import os
from pathlib import Path
import sqlite3
import time
from typing import Callable
import uuid

from .models import AgentError, Limits, Target, draft_digest, normalize_target, validate_text


class Store:
    def __init__(self, root: Path, clock: Callable[[], float] = time.time):
        self.root = Path(root)
        self.clock = clock
        self.db_path = self.root / 'state.sqlite3'
        self.artifact_dir = self.root / 'artifacts'
        # Keep the legacy lock filename so older running clients cannot overlap.
        self.lock_path = self.root / 'supervisor.lock'
        self._lock_fd = None
        self._lock_pid = None
        self._session = None
        for directory in (self.root, self.artifact_dir):
            directory.mkdir(mode=0o700, parents=True, exist_ok=True)
            directory.chmod(0o700)
        for path in (self.db_path, self.lock_path):
            fd = self._open_private(path)
            os.close(fd)
        with self._transaction() as db:
            db.execute('''CREATE TABLE IF NOT EXISTS drafts (
                id TEXT PRIMARY KEY, target_id TEXT NOT NULL, target_url TEXT NOT NULL,
                text TEXT NOT NULL, digest TEXT NOT NULL UNIQUE,
                state TEXT NOT NULL CHECK (state IN ('pending', 'reviewing', 'submitting',
                    'submitted', 'rejected', 'cancelled', 'failed', 'uncertain')),
                created_at REAL NOT NULL, updated_at REAL NOT NULL, detail TEXT NOT NULL
            )''')
            db.execute('''CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT, kind TEXT NOT NULL,
                draft_id TEXT REFERENCES drafts(id), created_at REAL NOT NULL,
                detail TEXT NOT NULL
            )''')
            db.execute('CREATE INDEX IF NOT EXISTS attempt_windows ON events(kind, created_at)')
            db.execute('CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL)')
            for key, value in [('paused', False), ('limits', asdict(Limits())),
                               ('submission', {'pid': None, 'session': None, 'heartbeat': None})]:
                db.execute('INSERT OR IGNORE INTO settings VALUES (?, ?)', (key, json.dumps(value)))
            db.execute('''CREATE TABLE IF NOT EXISTS watchlist (
                handle TEXT PRIMARY KEY, notes TEXT NOT NULL, created_at REAL NOT NULL
            )''')

    @staticmethod
    def _open_private(path):
        fd = os.open(path, os.O_CREAT | os.O_RDWR, 0o600)
        try:
            os.fchmod(fd, 0o600)
        except BaseException:
            os.close(fd)
            raise
        return fd

    @contextmanager
    def _connection(self):
        db = sqlite3.connect(self.db_path, timeout=10, isolation_level=None)
        db.row_factory = sqlite3.Row
        try:
            db.execute('PRAGMA foreign_keys = ON')
            yield db
        finally:
            db.close()

    @contextmanager
    def _transaction(self):
        with self._connection() as db:
            db.execute('BEGIN IMMEDIATE')
            try:
                yield db
                db.commit()
            except BaseException:
                db.rollback()
                raise

    @staticmethod
    def _draft(row):
        result = dict(row)
        result['detail'] = json.loads(result['detail'])
        return result

    def _get(self, db, draft_id):
        row = db.execute('SELECT * FROM drafts WHERE id = ?', (draft_id,)).fetchone()
        if row is None:
            raise AgentError('draft_not_found', f'No draft with ID {draft_id}.')
        return self._draft(row)

    @staticmethod
    def _setting(db, key):
        return json.loads(db.execute('SELECT value FROM settings WHERE key = ?', (key,)).fetchone()[0])

    @staticmethod
    def _set_setting(db, key, value):
        db.execute('UPDATE settings SET value = ? WHERE key = ?', (json.dumps(value), key))

    @staticmethod
    def _event(db, kind, draft_id, detail, now):
        db.execute('INSERT INTO events(kind, draft_id, created_at, detail) VALUES (?, ?, ?, ?)',
                   (kind, draft_id, now, json.dumps(detail, ensure_ascii=False)))

    @staticmethod
    def _require_state(draft, allowed):
        if draft['state'] not in allowed:
            raise AgentError('invalid_state', f"Draft {draft['id']} is {draft['state']}.")

    def _transition(self, db, draft_id, state, detail, now, kind=None):
        db.execute('UPDATE drafts SET state = ?, detail = ?, updated_at = ? WHERE id = ?',
                   (state, json.dumps(detail, ensure_ascii=False), now, draft_id))
        self._event(db, kind or state, draft_id, detail, now)

    def enqueue(self, target: Target, text: str) -> dict:
        return self.enqueue_many([(target, text)])[0]

    def enqueue_many(self, items: list[tuple[Target, str]]) -> list[dict]:
        validated = []
        for target, text in items:
            if not isinstance(target, Target) or normalize_target(target.id) != target:
                raise AgentError('invalid_target', 'Queue targets must be canonical Target values.')
            validate_text(text)
            validated.append((target, text, draft_digest(target.id, text)))
        result = []
        with self._transaction() as db:
            now = self.clock()
            for target, text, digest in validated:
                existing = db.execute('SELECT * FROM drafts WHERE digest = ?', (digest,)).fetchone()
                if existing is not None:
                    result.append(self._draft(existing))
                    continue
                draft_id = str(uuid.uuid4())
                db.execute('INSERT INTO drafts VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)',
                           (draft_id, target.id, target.url, text, digest, 'pending', now, now, '{}'))
                self._event(db, 'enqueued', draft_id, {}, now)
                result.append(self._get(db, draft_id))
        return result

    def get(self, draft_id: str) -> dict:
        with self._connection() as db:
            return self._get(db, draft_id)

    def _submission_running(self):
        fd = self._open_private(self.lock_path)
        try:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                return True
            fcntl.flock(fd, fcntl.LOCK_UN)
            return False
        finally:
            os.close(fd)

    def status(self) -> dict:
        with self._connection() as db:
            db.execute('BEGIN')
            drafts = [self._draft(row) for row in db.execute('SELECT * FROM drafts ORDER BY rowid')]
            events = [dict(row) for row in db.execute('SELECT * FROM events ORDER BY id DESC LIMIT 20')]
            for ev in events:
                ev['detail'] = json.loads(ev['detail'])
            submission = self._setting(db, 'submission')
            submission['running'] = self._submission_running()
            return {
                'paused': self._setting(db, 'paused'),
                'limits': self._setting(db, 'limits'),
                'submission': submission,
                'active_draft': next((draft for draft in drafts
                                      if draft['state'] in ('reviewing', 'submitting')), None),
                'pending_drafts': [d for d in drafts if d['state'] == 'pending'],
                'queue': drafts,
                'recent_events': events,
            }

    def set_paused(self, paused: bool) -> None:
        if type(paused) is not bool:
            raise AgentError('invalid_pause', 'Pause must be a boolean.')
        with self._transaction() as db:
            self._set_setting(db, 'paused', paused)
            self._event(db, 'paused' if paused else 'resumed', None, {}, self.clock())

    def cancel(self, draft_id: str) -> dict:
        with self._transaction() as db:
            self._require_state(self._get(db, draft_id), ('pending', 'reviewing'))
            self._transition(db, draft_id, 'cancelled', {}, self.clock())
            return self._get(db, draft_id)

    def configure_limits(self, limits: Limits) -> None:
        if not isinstance(limits, Limits):
            raise AgentError('invalid_limits', 'Expected Limits.')
        with self._transaction() as db:
            self._set_setting(db, 'limits', asdict(limits))
            self._event(db, 'limits_configured', None, asdict(limits), self.clock())

    @contextmanager
    def submission_lock(self):
        if self._lock_fd is not None:
            raise AgentError('submission_running', 'This store already holds a submission lock.')
        fd = self._open_private(self.lock_path)
        acquired = False
        try:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as error:
                raise AgentError('submission_running', 'Another submission process is running.') from error
            acquired = True
            self._lock_fd = fd
            self._lock_pid = os.getpid()
            self._session = str(uuid.uuid4())
            self.heartbeat()
            yield
        finally:
            if acquired:
                self._lock_fd = self._lock_pid = self._session = None
                fcntl.flock(fd, fcntl.LOCK_UN)
            os.close(fd)

    def _require_lock(self):
        if self._lock_fd is None or self._lock_pid != os.getpid():
            raise AgentError('submission_lock_required', 'Hold the submission lock for this operation.')

    def heartbeat(self) -> None:
        self._require_lock()
        with self._transaction() as db:
            self._set_setting(db, 'submission', {
                'pid': os.getpid(), 'session': self._session, 'heartbeat': self.clock(),
            })

    def recover(self) -> None:
        self._require_lock()
        with self._transaction() as db:
            now = self.clock()
            rows = db.execute("SELECT * FROM drafts WHERE state IN ('reviewing', 'submitting')").fetchall()
            for row in rows:
                state = 'pending' if row['state'] == 'reviewing' else 'uncertain'
                detail = json.loads(row['detail'])
                detail.update(reason='interrupted submission', previous_state=row['state'])
                self._transition(db, row['id'], state, detail, now, kind='recovered')

    def claim_next(self) -> dict | None:
        with self._transaction() as db:
            if self._setting(db, 'paused'):
                return None
            if db.execute("SELECT 1 FROM drafts WHERE state IN ('reviewing', 'submitting') LIMIT 1").fetchone():
                return None
            row = db.execute("SELECT id FROM drafts WHERE state = 'pending' ORDER BY rowid LIMIT 1").fetchone()
            if row is None:
                return None
            self._transition(db, row['id'], 'reviewing', {}, self.clock())
            return self._get(db, row['id'])

    def claim(self, draft_id: str) -> dict:
        """Claim only the caller-selected pending draft, never an unrelated queue entry."""
        self._require_lock()
        with self._transaction() as db:
            if self._setting(db, 'paused'):
                raise AgentError('paused', 'Submissions are paused.')
            draft = self._get(db, draft_id)
            self._require_state(draft, ('pending',))
            if db.execute("SELECT 1 FROM drafts WHERE state IN ('reviewing', 'submitting') LIMIT 1").fetchone():
                raise AgentError('submission_running', 'Another draft is active.')
            self._transition(db, draft_id, 'reviewing', {}, self.clock())
            return self._get(db, draft_id)

    def defer(self, draft_id: str, reason: str) -> None:
        with self._transaction() as db:
            self._require_state(self._get(db, draft_id), ('reviewing',))
            self._transition(db, draft_id, 'pending', {'reason': reason}, self.clock(), kind='deferred')

    def reject(self, draft_id: str) -> None:
        with self._transaction() as db:
            self._require_state(self._get(db, draft_id), ('reviewing',))
            self._transition(db, draft_id, 'rejected', {}, self.clock())

    def begin_submission(self, draft_id: str, digest: str) -> None:
        """Persist the caller's submission authorization and attempt before clicking."""
        with self._transaction() as db:
            draft = self._get(db, draft_id)
            self._require_state(draft, ('reviewing',))
            if digest != draft['digest'] or digest != draft_digest(draft['target_id'], draft['text']):
                raise AgentError('digest_mismatch', 'Reviewed target/text no longer matches the draft.', True)
            if self._setting(db, 'paused'):
                raise AgentError('paused', 'Submissions are paused.')
            now = self.clock()
            limits = Limits(**self._setting(db, 'limits'))
            attempts = db.execute('''SELECT
                COUNT(CASE WHEN created_at > ? THEN 1 END) AS burst,
                COUNT(CASE WHEN created_at > ? THEN 1 END) AS hourly,
                COUNT(CASE WHEN created_at > ? THEN 1 END) AS daily,
                MAX(created_at) AS latest
                FROM events WHERE kind = 'submission_started' ''',
                                   (now - 1800, now - 3600, now - 86400)).fetchone()
            if (attempts['hourly'] >= limits.hourly or attempts['daily'] >= limits.daily
                    or (attempts['latest'] is not None and now - attempts['latest'] < limits.spacing)):
                raise AgentError('rate_limited', 'Submission attempt quota or minimum spacing reached.')
            if attempts['burst'] >= limits.burst_max:
                raise AgentError('rate_limited', f'Burst limit reached (max {limits.burst_max} replies per 30 minutes).')
            detail = {'digest': digest, 'target_id': draft['target_id'], 'target_url': draft['target_url']}
            self._event(db, 'approval', draft_id, detail, now)
            self._transition(db, draft_id, 'submitting', detail, now, kind='submission_started')

    def finish(self, draft_id: str, state: str, detail: dict) -> None:
        with self._transaction() as db:
            draft = self._get(db, draft_id)
            allowed = ('reviewing', 'submitting') if state == 'failed' else ('submitting',)
            if state not in ('submitted', 'uncertain', 'failed'):
                raise AgentError('invalid_state', 'Finish requires submitted, uncertain, or failed.')
            self._require_state(draft, allowed)
            self._transition(db, draft_id, state, detail, self.clock())

    def event(self, kind: str, draft_id: str | None, detail: dict) -> None:
        with self._transaction() as db:
            if draft_id is not None:
                self._get(db, draft_id)
            self._event(db, kind, draft_id, detail, self.clock())

    def add_watchlist(self, handle: str, notes: str = '') -> dict:
        clean = handle.strip().lstrip('@').lower()
        if not clean or not clean.isalnum() and '_' not in clean:
            raise AgentError('invalid_handle', f'Invalid X handle: {handle}')
        with self._transaction() as db:
            now = self.clock()
            db.execute('INSERT OR REPLACE INTO watchlist (handle, notes, created_at) VALUES (?, ?, ?)',
                       (clean, str(notes).strip(), now))
            row = db.execute('SELECT * FROM watchlist WHERE handle = ?', (clean,)).fetchone()
            return dict(row)

    def remove_watchlist(self, handle: str) -> bool:
        clean = handle.strip().lstrip('@').lower()
        with self._transaction() as db:
            cursor = db.execute('DELETE FROM watchlist WHERE handle = ?', (clean,))
            return cursor.rowcount > 0

    def get_watchlist(self) -> list[dict]:
        with self._connection() as db:
            rows = db.execute('SELECT * FROM watchlist ORDER BY handle ASC').fetchall()
            return [dict(r) for r in rows]
