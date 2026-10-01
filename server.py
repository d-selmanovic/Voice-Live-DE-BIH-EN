import asyncio
import hashlib
import hmac
import json
import os
import secrets
import time
import uuid
from pathlib import Path

from aiohttp import web, ClientSession, ClientTimeout, WSMsgType
from prompts import LIVE, BACKEND, TOOLS
from state import Store, validate_ticket

ROOT = Path(__file__).resolve().parent
for path in [ROOT / '.env.local', ROOT.parent / '.env.local']:
    if path.exists():
        for line in path.read_text().splitlines():
            if '=' in line and not line.lstrip().startswith('#'):
                key, value = line.split('=', 1)
                os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))
ON_RENDER = os.getenv('RENDER') == 'true'
ORIGIN = (os.getenv('APP_ORIGIN') or os.getenv('RENDER_EXTERNAL_URL') or 'http://localhost:3000').rstrip('/')
PASSWORD = os.getenv('APP_PASSWORD', '')
KEY = os.getenv('OPENAI_API_KEY', '').strip()
HOST = os.getenv('HOST', '0.0.0.0' if ON_RENDER else '127.0.0.1')
if HOST not in ['127.0.0.1', 'localhost', '::1'] and (not PASSWORD or not ORIGIN.startswith('https://')):
    raise RuntimeError('Remote-Betrieb benötigt APP_PASSWORD und eine HTTPS APP_ORIGIN')
if ON_RENDER and len(PASSWORD) < 12:
    raise RuntimeError('Render-Testbetrieb benötigt ein APP_PASSWORD mit mindestens 12 Zeichen')
store = Store(Path(os.getenv('DATA_DIR', str(ROOT / 'data'))) / 'agent.sqlite')
auth = {}
sessions = {}
login_attempts = {}
limits = {}


@web.middleware
async def security(request, handler):
    if request.path == '/healthz' and request.method == 'GET':
        return await handler(request)
    if request.host != ORIGIN.split('://', 1)[1]:
        raise web.HTTPForbidden(text='Host nicht erlaubt')
    if request.method != 'GET' and request.headers.get('Origin') != ORIGIN:
        raise web.HTTPForbidden(text='Origin nicht erlaubt')
    if request.path.startswith('/api/') and request.path not in ['/api/login', '/api/config']:
        token = request.cookies.get('voice_auth', '')
        if token not in auth or auth[token] < time.time():
            raise web.HTTPUnauthorized(text='Bitte erneut anmelden')
        request['owner'] = token
    try:
        response = await handler(request)
    except web.HTTPException:
        raise
    except Exception:
        return web.json_response({'error': 'Interner Fehler. Vorgang wurde nicht bestätigt.'}, status=500)
    if not isinstance(response, web.WebSocketResponse):
        response.headers.update({'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff',
            'Referrer-Policy': 'no-referrer', 'Permissions-Policy': 'microphone=(self)',
            'Content-Security-Policy': "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; media-src 'self' blob:; object-src 'none'; frame-ancestors 'none'"})
    return response


def owned(request):
    s = sessions.get(request.match_info['sid'])
    if not s or s['owner'] != request['owner']:
        raise web.HTTPNotFound()
    return s


async def login(request):
    existing = request.cookies.get('voice_auth', '')
    if existing in auth and auth[existing] > time.time():
        return web.json_response({'ok': True})
    ip = request.remote
    now = time.time()
    attempts = [x for x in login_attempts.get(ip, []) if now - x < 60]
    if len(attempts) >= 5:
        raise web.HTTPTooManyRequests(text='Bitte eine Minute warten')
    login_attempts[ip] = attempts + [now]
    body = await request.json()
    if PASSWORD and not hmac.compare_digest(str(body.get('password', '')), PASSWORD):
        raise web.HTTPUnauthorized(text='Passwort stimmt nicht')
    token = secrets.token_urlsafe(32)
    auth[token] = now + 3600
    response = web.json_response({'ok': True})
    response.set_cookie('voice_auth', token, httponly=True, samesite='Strict', secure=ORIGIN.startswith('https://'), max_age=3600)
    return response


async def emit(s, event):
    for listener in list(s['listeners']):
        try:
            await listener.send_json(event)
        except Exception:
            s['listeners'].discard(listener)


async def send(s, event):
    if s.get('ws') and not s['ws'].closed:
        await s['ws'].send_json(event)
    else:
        raise RuntimeError('Sideband getrennt')


async def run_call(s, envelope):
    call = envelope['event']['item']
    cid = call['call_id']
    if cid in s['calls']:
        return
    revision = envelope.get('_revision', s['revision'])
    s['calls'].add(cid)
    did = envelope.get('delegation_id')
    op = f"{s['id']}:{revision}:{cid}"
    result = {'status': 'error'}
    try:
        if revision != s['revision'] or s['closing']:
            raise ValueError('Veralteter Tool-Aufruf')
        if call['name'] != 'prepare_demo_ticket':
            raise ValueError('Unbekanntes Tool')
        args = validate_ticket(json.loads(call['arguments']))
        future = asyncio.get_running_loop().create_future()
        approval = uuid.uuid4().hex
        s['pending'][approval] = {'future': future, 'args': args, 'revision': revision}
        await emit(s, {'type': 'approval', 'id': approval, 'args': args})
        store.audit(s['id'], 'approval_requested', {'operation_id': op, 'revision': revision, 'args': args})
        try:
            approved = await asyncio.wait_for(future, 90)
            if s['closing'] or revision != s['revision']:
                result = {'status': 'stale'}
            elif not approved:
                result = {'status': 'declined'}
            else:
                result = store.create_ticket(op, args)
        except asyncio.TimeoutError:
            result = {'status': 'timeout'}
        finally:
            s['pending'].pop(approval, None)
            await emit(s, {'type': 'approval_closed', 'id': approval})
    except (ValueError, TypeError, KeyError):
        result = {'status': 'invalid_arguments'}
    store.audit(s['id'], 'tool_result', {'operation_id': op, 'delegation_id': did, 'result': result})
    await send(s, {'type': 'response.item.create', 'event_id': 'tool_' + cid,
        'item': {'type': 'function_call_output', 'call_id': cid, 'output': json.dumps(result)}})
    await emit(s, {'type': 'tool_result', 'result': result})


async def finish_response(s, response_id):
    calls = s['batches'].pop(response_id, [])
    if not calls:
        return
    # All results for this response must be returned before continuing it.
    for envelope in calls:
        await run_call(s, envelope)
    if not s['closing']:
        await send(s, {'type': 'response.create', 'event_id': 'continue_' + uuid.uuid4().hex})


async def sideband(s):
    try:
        async for msg in s['ws']:
            if msg.type != WSMsgType.TEXT:
                continue
            event = json.loads(msg.data)
            kind = event.get('type', '')
            if kind in ['session.input_audio.append', 'session.output_audio.delta']:
                continue  # Do not retain audio payloads.
            if kind == 'response.event':
                inner = event.get('event', {})
                if inner.get('type') == 'response.created':
                    s['response_id'] = inner['response']['id']
                if inner.get('type') == 'response.output_item.done' and inner.get('item', {}).get('type') == 'function_call':
                    event['_revision'] = s['revision']
                    rid = inner.get('response_id', s.get('response_id'))
                    s['batches'].setdefault(rid, []).append(event)
                if inner.get('type') == 'response.completed':
                    response = inner.get('response', {})
                    store.audit(s['id'], 'backend_usage', {'response_id': response.get('id'), 'usage': response.get('usage')})
                    task = asyncio.create_task(finish_response(s, response.get('id', s.get('response_id'))))
                    s['jobs'].add(task)
                    task.add_done_callback(lambda t: (s['jobs'].discard(t), t.exception() if not t.cancelled() else None))
            elif kind == 'session.delegation.created':
                s['delegation_id'] = event.get('delegation_id')
                store.audit(s['id'], kind, event)
            elif kind in ['session.input_transcript.delta', 'session.output_transcript.delta']:
                store.audit(s['id'], kind, event)
            elif kind == 'session.closed':
                s['closed'].set()
                store.audit(s['id'], kind, event)
            if kind in ['error', 'session.closed']:
                await emit(s, event)
    except Exception:
        await emit(s, {'type': 'backend_disconnected'})
    finally:
        if not s['closed'].is_set():
            store.audit(s['id'], 'finalization_incomplete', {})


async def create_session(request):
    owner = request['owner']
    now = time.time()
    recent = [x for x in limits.get(owner, []) if now - x < 60]
    if len(recent) >= 3 or any(s['owner'] == owner and not s['closing'] for s in sessions.values()):
        raise web.HTTPTooManyRequests(text='Nur ein Gespräch gleichzeitig; maximal drei Starts pro Minute')
    limits[owner] = recent + [now]
    body = await request.json()
    sdp = body.get('sdp')
    if not isinstance(sdp, str) or not sdp.startswith('v=0') or len(sdp) > 60000:
        raise web.HTTPBadRequest(text='Ungültiges SDP-Angebot')
    if not KEY:
        raise web.HTTPServiceUnavailable(text='OpenAI-Key fehlt im Backend')
    headers = {'Authorization': 'Bearer ' + KEY, 'OpenAI-Safety-Identifier': hashlib.sha256(owner.encode()).hexdigest()}
    payload = {'session': {'model': os.getenv('LIVE_MODEL', 'gpt-live-1'), 'instructions': LIVE,
        'delegation': {'type': 'responses', 'responses': {'model': os.getenv('BACKEND_MODEL', 'gpt-6-luna'),
            'instructions': BACKEND, 'tools': TOOLS, 'tool_choice': 'auto', 'parallel_tool_calls': False}}},
        'transport': {'type': 'webrtc', 'sdp': sdp}}
    client = request.app['http']
    try:
        async with client.post('https://api.openai.com/v1/live/sessions', headers=headers, json=payload) as response:
            if response.status >= 400:
                # Do not expose full upstream request/error data or credentials.
                store.audit('startup', 'upstream_error', {'http_status': response.status})
                messages = {
                    401: 'OpenAI lehnt die Authentifizierung ab (HTTP 401). Den aktiven API-Key in voice-agent/.env.local und OPENAI_API_KEY in der Prozessumgebung prüfen; anschließend den Python-Server neu starten. Auch Key-Berechtigungen und IP-Freigaben prüfen.',
                    403: 'OpenAI verweigert den Zugriff (HTTP 403). Projektberechtigungen und regionale Verfügbarkeit prüfen.',
                    404: 'OpenAI-Endpunkt oder Modell nicht gefunden (HTTP 404). Modellnamen und Modellzugriff prüfen.',
                    429: 'OpenAI-Limit erreicht (HTTP 429). Guthaben, Ausgabenlimits und Anfragerate prüfen.'}
                return web.json_response({'error': messages.get(response.status, f'OpenAI-Verbindung fehlgeschlagen (HTTP {response.status}). API-Konfiguration prüfen.')}, status=502)
            data = await response.json()
        sid = data['session']['id']
        s = {'id': sid, 'owner': owner, 'revision': 0, 'calls': set(), 'pending': {}, 'listeners': set(),
            'closed': asyncio.Event(), 'closing': False, 'jobs': set(), 'batches': {}}
        sessions[sid] = s
        s['ws'] = await client.ws_connect(f'wss://api.openai.com/v1/live/sessions/{sid}/attach', headers=headers, max_msg_size=4*1024*1024)
        s['reader'] = asyncio.create_task(sideband(s))
        s['expiry'] = asyncio.create_task(expire_session(s))
        return web.json_response({'session_id': sid, 'sdp': data['transport']['sdp']}, status=201)
    except Exception:
        if 'sid' in locals() and sid in sessions:
            sessions[sid]['closing'] = True
        return web.json_response({'error': 'Verbindung zum Voice-Dienst konnte nicht aufgebaut werden.'}, status=502)


async def expire_session(s):
    await asyncio.sleep(600)
    await close_session(s)


async def close_session(s):
    if s['closing']:
        return
    s['closing'] = True
    for p in s['pending'].values():
        if not p['future'].done():
            p['future'].set_result(False)
    try:
        if s['jobs']:
            await asyncio.wait_for(asyncio.gather(*list(s['jobs']), return_exceptions=True), 3)
        await send(s, {'type': 'session.close', 'event_id': 'close_' + uuid.uuid4().hex})
        await asyncio.wait_for(s['closed'].wait(), 8)
    except Exception:
        store.audit(s['id'], 'finalization_incomplete', {})
    finally:
        if s.get('ws'):
            await s['ws'].close()
        await emit(s, {'type': 'app_closed', 'usage_complete': s['closed'].is_set()})
        for listener in list(s['listeners']):
            await listener.close()
        sessions.pop(s['id'], None)


async def action(request):
    s = owned(request)
    body = await request.json()
    if body.get('action') == 'close':
        await close_session(s)
    elif body.get('action') == 'revise':
        s['revision'] += 1
        for p in s['pending'].values():
            if not p['future'].done():
                p['future'].set_result(False)
        await send(s, {'type': 'session.instructions.append', 'delegation_id': None,
            'content': 'Der Nutzer hat die Aufgabe zurückgesetzt. Alte Ticketentwürfe sind ungültig. Frage nach seinem neuen Anliegen.'})
        store.audit(s['id'], 'task_revised', {'revision': s['revision']})
    elif body.get('action') == 'approve':
        p = s['pending'].get(body.get('id'))
        if not p or p['revision'] != s['revision'] or p['future'].done() or s['closing']:
            raise web.HTTPConflict(text='Dieser Entwurf ist nicht mehr gültig')
        p['future'].set_result(body.get('approved') is True)
    else:
        raise web.HTTPBadRequest()
    return web.json_response({'ok': True})


async def events(request):
    if request.headers.get('Origin') != ORIGIN:
        raise web.HTTPForbidden()
    s = owned(request)
    ws = web.WebSocketResponse(heartbeat=20)
    await ws.prepare(request)
    s['listeners'].add(ws)
    for pid, p in s['pending'].items():
        await ws.send_json({'type': 'approval', 'id': pid, 'args': p['args']})
    try:
        async for _ in ws:
            pass
    finally:
        s['listeners'].discard(ws)
    return ws


async def static(request):
    filename = request.match_info.get('file', 'index.html')
    if filename not in ['index.html', 'app.js', 'style.css']:
        raise web.HTTPNotFound()
    return web.FileResponse(ROOT / 'public' / filename)


async def lifecycle(app):
    async with ClientSession(timeout=ClientTimeout(total=25)) as client:
        app['http'] = client
        yield
        await asyncio.gather(*(close_session(s) for s in list(sessions.values())), return_exceptions=True)


async def config(request):
    return web.json_response({'password_required': bool(PASSWORD)})

async def health(request):
    return web.json_response({'status': 'ok'}, headers={'Cache-Control':'no-store'})

def create_app():
    app = web.Application(middlewares=[security], client_max_size=65536)
    app.cleanup_ctx.append(lifecycle)
    app.router.add_get('/api/config', config)
    app.router.add_get('/healthz', health)
    app.router.add_post('/api/login', login)
    app.router.add_post('/api/session', create_session)
    app.router.add_post('/api/session/{sid}/action', action)
    app.router.add_get('/api/session/{sid}/events', events)
    app.router.add_get('/', static)
    app.router.add_get('/{file}', static)
    return app

if __name__ == '__main__':
    web.run_app(create_app(), host=HOST, port=int(os.getenv('PORT', '3000')), access_log=None)
