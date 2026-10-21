import unittest
from integrations import Settings, Integrations, IntegrationError, candidate_reply, verify_webhook, trace
from unittest.mock import patch, AsyncMock
import hashlib, hmac, json

class Rules(unittest.TestCase):
    def test_webhook_auth(self):
        body=b'{"event":"message_created"}'
        signature='sha256='+hmac.new(b'secret',b'1000.'+body,hashlib.sha256).hexdigest()
        self.assertTrue(verify_webhook(body,{'X-Chatwoot-Timestamp':'1000','X-Chatwoot-Signature':signature},'secret',now=1001))
        self.assertFalse(verify_webhook(body,{'X-Chatwoot-Timestamp':'1000','X-Chatwoot-Signature':signature},'secret',now=2000))
        self.assertFalse(verify_webhook(body,{},'secret',now=1001))
    def test_safe_candidate_intake_and_handoff(self):
        for text,lang in [('Tražim posao','bs'),('Ich suche Arbeit','de'),('Looking for a job','en')]:
            result=candidate_reply(text,False)
            self.assertFalse(result['handoff']);self.assertEqual(result['language'],lang);self.assertIn('CV',result['content'])
        for text in ['Koja je plata?','Was kostet die Unterkunft?','Ist das Visum sicher?','salary','visa']:
            self.assertTrue(candidate_reply(text,False)['handoff'])
        self.assertTrue(candidate_reply('',True)['handoff'])
    def test_trace_never_copies_payload(self):
        with patch('integrations.logger.info') as out:
            trace('tool',status='ok',duration_ms=2,content='secret',token='secret',email='test@example.com')
        encoded=out.call_args.args[-1]
        self.assertNotIn('secret',encoded);self.assertNotIn('example.com',encoded)
    def test_endpoints_fixed(self):
        with self.assertRaises(ValueError): Settings({'CHATWOOT_BASE_URL':'https://evil.example'})
        with self.assertRaises(ValueError): Settings({'SUPERMEMORY_BASE_URL':'https://evil.example'})

class ConnectorTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.cfg=Settings({'CHATWOOT_BASE_URL':'https://chat.activi.io','CHATWOOT_ACCOUNT_ID':'2','CHATWOOT_TEST_INBOX_ID':'12','CHATWOOT_API_TOKEN':'test','SUPERMEMORY_API_KEY':'test'})
        self.api=Integrations(None,self.cfg)
    async def test_segmented_json_is_read_completely(self):
        from integrations import bounded_json
        class Stream:
            async def iter_chunked(self,size):
                for chunk in [b'{"res',b'ults":',b'[]}']:
                    yield chunk
        response=type('Response',(),{'content':Stream()})()
        self.assertEqual(await bounded_json(response),{'results':[]})

    async def test_memory_accepts_any_existing_context_without_fixed_filter(self):
        self.api.namespaces=AsyncMock(return_value=['existing_a','existing_b'])
        self.api.request=AsyncMock(return_value={'results':[]})
        result=await self.api.execute('memory_search',{'query':'FAQ','namespace':'existing_b'},{})
        args=self.api.request.call_args
        self.assertEqual(args.args[1],'https://api.supermemory.ai/ns/existing_b/search')
        self.assertNotIn('containerTags',args.kwargs['payload'])
        self.assertFalse(result['all_namespaces_searched'])
        self.assertEqual(result['status'],'ok')
    async def test_write_guard_runs_after_async_preflight(self):
        from integrations import IntegrationError
        self.api.request=AsyncMock(return_value={'inbox_id':12})
        def cancelled():raise IntegrationError('stale')
        with self.assertRaises(IntegrationError):
            await self.api.execute('chatwoot_add_note',{'conversation_id':4,'content':'Note'},{'before_write':cancelled})
        self.assertEqual(self.api.request.await_count,1)

    async def test_wrong_inbox_blocks_note_before_write(self):
        self.api.request=AsyncMock(return_value={'inbox_id':9})
        with self.assertRaises(IntegrationError):
            await self.api.execute('chatwoot_add_note',{'conversation_id':4,'content':'Note'},{})
        self.assertEqual(self.api.request.await_count,1)
    async def test_linear_missing_config_fails_closed(self):
        with self.assertRaises(IntegrationError):
            await self.api.execute('linear_create_issue',{'title':'Test','description':'Test'},{})
    async def test_arguments_reject_project_and_url(self):
        with self.assertRaises(ValueError):self.api.validate('linear_create_issue',{'title':'Test','description':'Test','project':'other'})
        with self.assertRaises(ValueError):self.api.validate('memory_search',{'query':'x','url':'https://evil'})
    async def test_namespace_discovery_fails_instead_of_partial_search(self):
        self.api.request=AsyncMock(return_value={'namespaces':[{'namespace':'a'}],'pagination':{'totalItems':2,'totalPages':1}})
        with self.assertRaises(IntegrationError):await self.api.namespaces()

    async def test_mcp_only_advertised_tools(self):
        self.api.cfg.linear_token='test';self.api.cfg.linear_project='p';self.api.cfg.linear_team='t'
        self.api.mcp=AsyncMock(return_value={'tools':[{'name':'delete_issue'}]})
        with self.assertRaises(IntegrationError):await self.api.linear('linear_create_issue',{'title':'T','description':'D'})

if __name__=='__main__':unittest.main()
