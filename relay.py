"""Durable at-most-once candidate intake. Ambiguous writes require human review."""
import asyncio
import hashlib
import time
from feedback import FeedbackStore
from integrations import IntegrationError, candidate_reply, trace


class RelayStore(FeedbackStore):
    def __init__(self, url='', path=None):
        super().__init__(url, path)
        with self.connection() as db:
            db.execute('''CREATE TABLE IF NOT EXISTS lena_deliveries (
                id TEXT PRIMARY KEY, state TEXT NOT NULL, created_at BIGINT NOT NULL)''')
            db.execute('''CREATE TABLE IF NOT EXISTS lena_handoffs (
                id TEXT PRIMARY KEY, paused INTEGER NOT NULL, updated_at BIGINT NOT NULL)''')
            db.execute('''CREATE TABLE IF NOT EXISTS lena_webhook_queue (
                id TEXT PRIMARY KEY, account_id TEXT NOT NULL, inbox_id TEXT NOT NULL,
                conversation_id BIGINT NOT NULL, message_id BIGINT NOT NULL,
                state TEXT NOT NULL, created_at BIGINT NOT NULL)''')

    def enqueue(self, event, cfg):
        cid, mid = identity(event, cfg)
        key = hashlib.sha256(f'{cfg.account}:{cid}:{mid}'.encode()).hexdigest()
        with self.connection() as db:
            cursor = db.execute(self.sql('''INSERT INTO lena_webhook_queue VALUES (?, ?, ?, ?, ?, 'queued', ?)
                ON CONFLICT (id) DO NOTHING'''), (key, cfg.account, cfg.inbox, cid, mid, int(time.time())))
            return cursor.rowcount == 1

    def take(self):
        with self.connection() as db:
            row = db.execute(self.sql('''UPDATE lena_webhook_queue SET state='processing', created_at=?
                WHERE id=(SELECT id FROM lena_webhook_queue WHERE state='queued' ORDER BY created_at LIMIT 1)
                AND state='queued' RETURNING id, account_id, inbox_id, conversation_id, message_id'''), (int(time.time()),)).fetchone()
            if not row:
                return None
            key, account, inbox, cid, mid = row
            return key, {'event': 'message_created', 'id': mid, 'account': {'id': int(account)},
                         'inbox': {'id': int(inbox)}, 'conversation': {'id': cid},
                         'message_type': 'incoming', 'private': False}

    def finish_queue(self, key, state):
        with self.connection() as db:
            db.execute(self.sql('UPDATE lena_webhook_queue SET state=? WHERE id=?'), (state, key))

    def unresolved(self, cid, current):
        with self.connection() as db:
            return bool(db.execute(self.sql("SELECT 1 FROM lena_webhook_queue WHERE conversation_id=? AND id<>? AND state IN ('processing','needs_review') LIMIT 1"), (cid, current)).fetchone())

    def recover(self):
        # A processing row may already have sent a message before process death.
        # Surface it for humans; never replay that message automatically.
        with self.connection() as db:
            return db.execute(self.sql("UPDATE lena_webhook_queue SET state='needs_review' WHERE state='processing' AND created_at < ? RETURNING id, conversation_id"), (int(time.time()) - 300,)).fetchall()

    def claim(self, key):
        with self.connection() as db:
            cursor = db.execute(self.sql('''INSERT INTO lena_deliveries VALUES (?, 'claimed', ?)
                ON CONFLICT (id) DO NOTHING'''), (key, int(time.time())))
            return cursor.rowcount == 1

    def finish(self, key, state):
        with self.connection() as db:
            db.execute(self.sql('UPDATE lena_deliveries SET state=? WHERE id=?'), (state, key))

    def paused(self, key):
        with self.connection() as db:
            row = db.execute(self.sql('SELECT paused FROM lena_handoffs WHERE id=?'), (key,)).fetchone()
            return bool(row and row[0])

    def pause(self, key, paused=True):
        with self.connection() as db:
            db.execute(self.sql('''INSERT INTO lena_handoffs VALUES (?, ?, ?)
                ON CONFLICT (id) DO UPDATE SET paused=excluded.paused, updated_at=excluded.updated_at'''),
                (key, int(paused), int(time.time())))

    def summary(self):
        with self.connection() as db:
            return dict(db.execute('SELECT state, COUNT(*) FROM lena_deliveries GROUP BY state').fetchall())

    def resume(self, cid, conv_key):
        with self.connection() as db:
            if db.execute(self.sql("SELECT 1 FROM lena_webhook_queue WHERE conversation_id=? AND state='processing' LIMIT 1"), (cid,)).fetchone():
                raise ValueError('Vorgang wird noch verarbeitet; bitte später prüfen')
            db.execute(self.sql("UPDATE lena_webhook_queue SET state='reviewed' WHERE conversation_id=? AND state='needs_review'"), (cid,))
            db.execute(self.sql('UPDATE lena_handoffs SET paused=0, updated_at=? WHERE id=?'), (int(time.time()), conv_key))


def identity(event, cfg):
    if not isinstance(event, dict):
        return None
    try:
        if str(event['account']['id']) != cfg.account or str(event['inbox']['id']) != cfg.inbox:
            return None
        cid, mid = event['conversation']['id'], event['id']
        if type(cid) is not int or type(mid) is not int or cid < 1 or mid < 1:
            return None
        if event.get('event') != 'message_created' or event.get('private') is not False or event.get('message_type') not in ('incoming', 0):
            return None
        return cid, mid
    except (KeyError, TypeError):
        return None


async def process_message(api, store, event):
    ids = identity(event, api.cfg)
    if ids is None:
        return 'ignored'
    cid, mid = ids
    conv_key = f'{api.cfg.account}:{cid}'
    key = hashlib.sha256(f'{conv_key}:{mid}'.encode()).hexdigest()
    if not await asyncio.to_thread(store.claim, key):
        return 'duplicate'
    state = 'needs_review'
    start = time.monotonic()
    try:
        conversation = await api.conversation(cid)
        if await asyncio.to_thread(store.unresolved, cid, key):
            await asyncio.to_thread(store.pause, conv_key)
            await api.chat('POST', f'/conversations/{cid}/toggle_status', {'status': 'open'})
            state = 'human_active'
            return state
        if conversation.get('status') != 'pending' or await asyncio.to_thread(store.paused, conv_key):
            state = 'human_active'
            return state
        messages = await api.chat('GET', f'/conversations/{cid}/messages')
        canonical = next((m for m in messages.get('payload', []) if m.get('id') == mid), None)
        if not canonical or canonical.get('message_type') not in ('incoming', 0) or canonical.get('private') is not False:
            state = 'unverified_message'
            return state
        # Stale webhook deliveries must not reply after newer incoming messages.
        if any(m.get('message_type') in ('incoming', 0) and m.get('id', 0) > mid for m in messages.get('payload', [])):
            state = 'superseded'
            return state
        text = canonical.get('content') or ''
        if not isinstance(text, str) or len(text) > 16000:
            raise IntegrationError('message_too_large')
        reply = candidate_reply(text, bool(canonical.get('attachments')))
        if (await api.conversation(cid)).get('status') != 'pending':
            state = 'human_active'
            return state
        if reply['handoff']:
            # Persist silence BEFORE any remote write. If the status update fails,
            # subsequent deliveries still cannot resume the bot automatically.
            await asyncio.to_thread(store.pause, conv_key)
            await api.chat('POST', f'/conversations/{cid}/toggle_status', {'status': 'open'})
        await api.chat('POST', f'/conversations/{cid}/messages',
                       {'content': reply['content'], 'message_type': 'outgoing', 'private': False})
        if reply['handoff']:
            state = 'handed_off'
        else:
            state = 'replied'
        return state
    except asyncio.CancelledError:
        # Shutdown while a request is in flight is also an ambiguous write.
        await asyncio.shield(asyncio.to_thread(store.pause, conv_key))
        raise
    except Exception:
        # A POST might have succeeded despite a timeout. Do not retry it.
        await asyncio.to_thread(store.pause, conv_key)
        try:
            # Independently surface the case to humans even when a message POST
            # timed out. Setting a known status is safe; sending again is not.
            await api.conversation(cid)
            await api.chat('POST', f'/conversations/{cid}/toggle_status', {'status': 'open'})
        except Exception:
            trace('handoff_unconfirmed', status='needs_review', operation_id=key)
        return state
    finally:
        await asyncio.to_thread(store.finish, key, state)
        trace('chatwoot_delivery', status=state, operation_id=key,
              duration_ms=round((time.monotonic()-start)*1000))
