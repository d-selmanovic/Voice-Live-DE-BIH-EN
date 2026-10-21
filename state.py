import json
import sqlite3
import uuid
from pathlib import Path


def validate_ticket(args):
    if not isinstance(args, dict) or set(args) != {"customer_ref", "issue", "priority"}:
        raise ValueError("Ungültige Ticketfelder")
    if not isinstance(args['customer_ref'], str) or not 1 <= len(args['customer_ref'].strip()) <= 100:
        raise ValueError("Kundenreferenz fehlt oder ist zu lang")
    if not isinstance(args['issue'], str) or not 10 <= len(args['issue'].strip()) <= 2000:
        raise ValueError("Problembeschreibung muss 10 bis 2000 Zeichen enthalten")
    if args['priority'] not in ['low', 'normal', 'high']:
        raise ValueError("Ungültige Priorität")
    return {k: v.strip() for k, v in args.items()}


class Store:
    def __init__(self, path):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path)
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.executescript('''
        CREATE TABLE IF NOT EXISTS tickets(operation_id TEXT PRIMARY KEY, id TEXT, payload TEXT);
        CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY, ts TEXT DEFAULT CURRENT_TIMESTAMP,
          session_id TEXT, event TEXT, details TEXT);
        ''')

    def audit(self, sid, event, details):
        # Persist technical metadata only. Transcripts, tool arguments, retrieved
        # memories and document contents must never enter the audit store.
        allowed = {'operation_id', 'revision', 'delegation_id', 'http_status', 'status', 'response_id'}
        safe = {k: v for k, v in details.items() if k in allowed and isinstance(v, (str, int, bool, type(None)))}
        usage = details.get('usage')
        if isinstance(usage, dict):
            safe['usage'] = {k: v for k, v in usage.items() if isinstance(v, (int, float))}
        from integrations import trace
        trace(event, status=safe.get('status'), operation_id=safe.get('operation_id'), http_status=safe.get('http_status'))
        with self.db:
            self.db.execute('INSERT INTO audit(session_id,event,details) VALUES(?,?,?)',
                (sid, event, json.dumps(safe, ensure_ascii=False)))

    def create_ticket(self, operation_id, args):
        args = validate_ticket(args)
        with self.db:
            self.db.execute('INSERT OR IGNORE INTO tickets VALUES(?,?,?)',
                (operation_id, 'demo_' + uuid.uuid4().hex[:12], json.dumps(args)))
        row = self.db.execute('SELECT id FROM tickets WHERE operation_id=?', (operation_id,)).fetchone()
        return {"status": "created", "ticket_id": row[0], "demo": True}

