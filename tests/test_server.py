import asyncio
import sys
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path
from aiohttp.test_utils import TestClient, TestServer
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import server
from state import Store
from feedback import FeedbackStore
from types import SimpleNamespace


class ServerTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        server.store = Store(Path(self.tmp.name) / 'test.sqlite')
        self.old_feedback = server.feedback
        server.feedback = FeedbackStore(path=Path(self.tmp.name) / 'feedback.sqlite')
        server.sessions.clear()
        server.auth.clear()
        server.login_attempts.clear()
        self.client = TestClient(TestServer(server.create_app()))
        await self.client.start_server()
        self.headers = {'Host': 'localhost:3000', 'Origin': server.ORIGIN}

    async def asyncTearDown(self):
        await self.client.close()
        server.feedback = self.old_feedback
        self.tmp.cleanup()

    async def test_security_and_invalid_session(self):
        r = await self.client.get('/api/config', headers={'Host':'localhost:3000'})
        self.assertEqual(r.status, 200)
        r = await self.client.post('/api/session', json={'sdp':'invalid'}, headers=self.headers)
        self.assertEqual(r.status, 401)
        r = await self.client.post('/api/login', json={}, headers=self.headers)
        cookie = r.cookies['voice_auth'].value
        headers = {**self.headers, 'Cookie': 'voice_auth=' + cookie}
        r = await self.client.post('/api/session', json={'sdp':'invalid'}, headers=headers)
        self.assertEqual(r.status, 400)
        r = await self.client.post('/api/session', json={}, headers={**headers,'Origin':'https://evil.example'})
        self.assertEqual(r.status, 403)
        r = await self.client.get('/.env.local', headers={'Host':'localhost:3000'})
        self.assertEqual(r.status, 404)

    async def test_healthcheck_without_public_host(self):
        r = await self.client.get('/healthz')
        self.assertEqual(r.status, 200)
        self.assertEqual(await r.json(), {'status':'ok'})

    async def test_password_and_existing_session(self):
        with patch.object(server, 'PASSWORD', 'StrongTestPassword123'):
            r = await self.client.post('/api/login', json={'password':'wrong'}, headers=self.headers)
            self.assertEqual(r.status, 401)
            r = await self.client.post('/api/login', json={'password':'StrongTestPassword123'}, headers=self.headers)
            self.assertEqual(r.status, 200)
            cookie = r.cookies['voice_auth'].value
            count = len(server.auth)
            r = await self.client.post('/api/login', json={}, headers={**self.headers,'Cookie':'voice_auth='+cookie})
            self.assertEqual(r.status, 200)
            self.assertEqual(len(server.auth), count)

    async def test_approval_and_duplicate_call(self):
        sent = []
        class Socket:
            closed = False
            async def send_json(self, event): sent.append(event)
        s = {'id':'test', 'revision':0,'calls':set(),'pending':{},'listeners':set(),'closing':False,'ws':Socket()}
        envelope = {'delegation_id':'d','event':{'item':{'call_id':'c','name':'prepare_demo_ticket',
            'arguments':'{"customer_ref":"test","issue":"Mikrofon funktioniert nicht","priority":"normal"}'}}}
        task = asyncio.create_task(server.run_call(s,envelope))
        await asyncio.sleep(0)
        self.assertEqual(server.store.db.execute('SELECT COUNT(*) FROM tickets').fetchone()[0],0)
        next(iter(s['pending'].values()))['future'].set_result(True)
        await task
        await server.run_call(s,envelope)
        self.assertEqual(server.store.db.execute('SELECT COUNT(*) FROM tickets').fetchone()[0],1)
        self.assertEqual(len(sent),1)

    async def test_revision_blocks_write(self):
        class Socket:
            closed = False
            async def send_json(self,event): pass
        s = {'id':'test','revision':0,'calls':set(),'pending':{},'listeners':set(),'closing':False,'ws':Socket()}
        envelope = {'event':{'item':{'call_id':'c','name':'prepare_demo_ticket',
            'arguments':'{"customer_ref":"test","issue":"Mikrofon funktioniert nicht","priority":"normal"}'}}}
        task = asyncio.create_task(server.run_call(s,envelope))
        await asyncio.sleep(0)
        s['revision'] += 1
        next(iter(s['pending'].values()))['future'].set_result(True)
        await task
        self.assertEqual(server.store.db.execute('SELECT COUNT(*) FROM tickets').fetchone()[0],0)

    async def test_rating_requires_login_and_successful_voice_test(self):
        r = await self.client.get('/api/ratings', headers=self.headers)
        self.assertEqual(r.status,401)
        r = await self.client.post('/api/login',json={},headers=self.headers)
        headers = {**self.headers,'Cookie':'voice_auth='+r.cookies['voice_auth'].value}
        received = []
        class Response:
            status = 201
            async def __aenter__(self): return self
            async def __aexit__(self,*args): pass
            async def json(self): return {'session':{'id':'mock-session'},'transport':{'sdp':'answer'}}
        class Socket:
            closed = False
            def __aiter__(self):
                async def events():
                    import json
                    for e in [{'type':'session.output_transcript.delta','delta':'Zdravo!'}, {'type':'session.closed'}]:
                        yield SimpleNamespace(type=server.WSMsgType.TEXT,data=json.dumps(e))
                return events()
            async def close(self): self.closed=True
            async def send_json(self,e): pass
        class Upstream:
            def post(self,url,headers,json): received.append(json);return Response()
            async def ws_connect(self,*a,**k): return Socket()
        with patch.object(server,'KEY','test-key'):
            self.client.server.app['http'] = Upstream()
            r = await self.client.post('/api/session',headers=headers,json={'sdp':'v=0\r\n','voice':'cedar','language':'bs','tester_code':'tester-1'})
            self.assertEqual(r.status,201)
            result=await r.json()
            await server.sessions['mock-session']['reader']
        self.assertEqual(received[0]['session']['audio']['output']['voice'],'cedar')
        self.assertIn('Započni',received[0]['session']['instructions'])
        body={'test_id':result['test_id'],'test_token':result['test_token'],'pronunciation':4,'clarity':5,'naturalness':3}
        r=await self.client.post('/api/ratings',headers=headers,json=body)
        self.assertEqual(r.status,200)
        r=await self.client.get('/api/ratings',headers=headers)
        stats=await r.json()
        self.assertEqual(stats['testers'],1)
        self.assertEqual(stats['rows'][0]['voice'],'cedar')
        self.assertEqual(stats['rows'][0]['language'],'bs')
        self.assertEqual(stats['rows'][0]['overall'],4)

if __name__ == '__main__': unittest.main()
