"""Persistent, cross-process request reservations. Unknown cost is never zero."""
from __future__ import annotations
import hashlib
import json
import sqlite3
import time
import uuid
from contextlib import contextmanager
from pathlib import Path

class LimitReached(RuntimeError):
    pass

class Busy(RuntimeError):
    pass

class Ledger:
    def __init__(self, path, total_limit=8000, codex_limit=1000, concurrency=4, per_provider=1):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.limits = (total_limit, codex_limit, concurrency, per_provider)
        with self.connection() as db:
            db.executescript("""
            CREATE TABLE IF NOT EXISTS requests (
                id TEXT PRIMARY KEY, task_key TEXT NOT NULL, provider TEXT NOT NULL,
                attempt INTEGER NOT NULL, state TEXT NOT NULL, started REAL NOT NULL,
                ended REAL, estimated_cost REAL, actual_cost REAL, currency TEXT,
                metadata TEXT NOT NULL, result TEXT, error_type TEXT,
                UNIQUE(task_key, attempt));
            CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS queue_tickets (ticket TEXT PRIMARY KEY,provider TEXT NOT NULL,task_key TEXT NOT NULL,created REAL NOT NULL,expires REAL NOT NULL);
            """)
            for key, val in zip(('total_limit','codex_limit','concurrency','per_provider'), self.limits):
                db.execute('INSERT OR IGNORE INTO settings VALUES (?,?)', (key,str(val)))
                saved = int(db.execute('SELECT value FROM settings WHERE key=?',(key,)).fetchone()[0])
                if val > saved:
                    raise ValueError('Increasing persisted request limits is not permitted')

    @contextmanager
    def connection(self):
        db = sqlite3.connect(self.path, timeout=30)
        db.row_factory = sqlite3.Row
        try:
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    @staticmethod
    def key(payload):
        return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()).hexdigest()

    def cached(self, task_key):
        with self.connection() as db:
            row = db.execute("SELECT result FROM requests WHERE task_key=? AND state='succeeded' ORDER BY attempt DESC LIMIT 1",(task_key,)).fetchone()
            return json.loads(row['result']) if row else None

    def enqueue(self,task_key,provider,ttl=610):
        ticket=str(uuid.uuid4());now=time.time()
        with self.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            db.execute('DELETE FROM queue_tickets WHERE expires<=?',(now,))
            db.execute('INSERT INTO queue_tickets VALUES (?,?,?,?,?)',(ticket,provider,task_key,now,now+ttl))
        return ticket

    def cancel_ticket(self,ticket):
        with self.connection() as db:db.execute('DELETE FROM queue_tickets WHERE ticket=?',(ticket,))

    def reserve(self, task_key, provider, metadata, estimated_cost=None, currency=None, max_attempts=3,queue_ticket=None):
        with self.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            if db.execute("SELECT 1 FROM requests WHERE task_key=? AND state='succeeded'",(task_key,)).fetchone():
                raise Busy('Successful task already cached')
            retired = {r['key']: int(r['value']) for r in db.execute("SELECT key,value FROM settings WHERE key IN ('retired_requests','retired_codex_requests')")}
            count = db.execute('SELECT COUNT(*) FROM requests').fetchone()[0] + retired.get('retired_requests',0)
            pc = db.execute("SELECT COUNT(*) FROM requests WHERE provider='codex' OR json_extract(metadata,'$.client')='codex'").fetchone()[0] + retired.get('retired_codex_requests',0)
            if count >= self.limits[0] or ((provider == 'codex' or metadata.get('client')=='codex') and pc >= self.limits[1]):
                raise LimitReached('Persistent model request limit reached')
            head=db.execute('SELECT ticket FROM queue_tickets WHERE provider=? AND expires>? ORDER BY created,ticket LIMIT 1',(provider,time.time())).fetchone()
            if head and head['ticket']!=queue_ticket:raise Busy('An earlier provider request is waiting')
            active = db.execute("SELECT COUNT(*) FROM requests WHERE state='running'").fetchone()[0]
            provider_active = db.execute("SELECT COUNT(*) FROM requests WHERE state='running' AND provider=?",(provider,)).fetchone()[0]
            if active >= self.limits[2] or provider_active >= self.limits[3]:
                raise Busy('Provider or global concurrency reservation is occupied')
            attempt = db.execute('SELECT COUNT(*) FROM requests WHERE task_key=?',(task_key,)).fetchone()[0]
            if attempt >= max_attempts:
                raise LimitReached('Task retry limit reached')
            rid = str(uuid.uuid4())
            db.execute('INSERT INTO requests (id,task_key,provider,attempt,state,started,estimated_cost,currency,metadata) VALUES (?,?,?,?,?,?,?,?,?)',
                       (rid,task_key,provider,attempt,'running',time.time(),estimated_cost,currency,json.dumps(metadata,ensure_ascii=False)))
            if queue_ticket:db.execute('DELETE FROM queue_tickets WHERE ticket=?',(queue_ticket,))
            return rid

    def finish(self, rid, *, result=None, error_type=None, actual_cost=None, estimated_cost=None, currency=None):
        state = 'failed' if error_type else 'succeeded'
        with self.connection() as db:
            changed = db.execute("UPDATE requests SET state=?, ended=?, result=?, error_type=?, actual_cost=?, estimated_cost=COALESCE(?,estimated_cost),currency=COALESCE(?,currency) WHERE id=? AND state='running'",
                (state,time.time(),json.dumps(result,ensure_ascii=False) if result is not None else None,error_type,actual_cost,estimated_cost,currency,rid)).rowcount
            if changed != 1:
                raise ValueError('Request is not an active reservation')

    def interrupt(self, rid):
        # Explicit recovery only after the caller verifies that the worker ended.
        self.finish(rid, error_type='interrupted_outcome_unknown')

    def summary(self):
        with self.connection() as db:
            groups = [dict(r) for r in db.execute('SELECT provider,state,currency,COUNT(*) AS requests,SUM(estimated_cost) AS estimated_cost,SUM(actual_cost) AS actual_cost,SUM(CASE WHEN estimated_cost IS NULL AND actual_cost IS NULL THEN 1 ELSE 0 END) AS unknown_cost_requests FROM requests GROUP BY provider,state,currency')]
            retired = {r['key']: int(r['value']) for r in db.execute("SELECT key,value FROM settings WHERE key IN ('retired_requests','retired_codex_requests')")}
            retained = db.execute('SELECT COUNT(*) FROM requests').fetchone()[0]
            n = retained + retired.get('retired_requests',0)
            c = db.execute("SELECT COUNT(*) FROM requests WHERE provider='codex' OR json_extract(metadata,'$.client')='codex'").fetchone()[0] + retired.get('retired_codex_requests',0)
        return {'requests':n,'codex_requests':c,'remaining_total':self.limits[0]-n,'remaining_codex':self.limits[1]-c,'groups':groups,'amount_limit':None,'retained_requests':retained,'retired_requests':retired.get('retired_requests',0),'retired_codex_requests':retired.get('retired_codex_requests',0),'cost_scope':'retained records only; deleted history has unknown cost'}
