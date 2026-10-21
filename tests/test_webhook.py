import asyncio, tempfile, unittest, sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from relay import RelayStore, process_message
from unittest.mock import AsyncMock
from integrations import IntegrationError

class RelayTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.store=RelayStore(path=Path(self.tmp.name)/'r.sqlite')
        self.api=AsyncMock(); self.api.cfg=type('Cfg',(),{'account':'2','inbox':'12'})()
        self.api.conversation.return_value={'inbox_id':12,'status':'pending'}
        self.api.chat.return_value={'payload':[{'id':10,'message_type':0,'private':False,'content':'Tražim posao','attachments':[]}]}
        self.event={'event':'message_created','id':10,'account':{'id':2},'inbox':{'id':12},'conversation':{'id':3},'message_type':'incoming','private':False}
    async def asyncTearDown(self):self.tmp.cleanup()
    async def test_queue_is_durable_and_contains_only_ids(self):
        self.assertTrue(self.store.enqueue(self.event,self.api.cfg))
        self.assertFalse(self.store.enqueue(self.event,self.api.cfg))
        reopened=RelayStore(path=Path(self.tmp.name)/'r.sqlite')
        key,event=reopened.take()
        self.assertEqual(event['id'],10);self.assertNotIn('content',event)
        self.assertIsNone(reopened.take())
        self.assertEqual(reopened.recover(),[])
        with __import__('unittest.mock').mock.patch('relay.time.time',return_value=__import__('time').time()+301):
            self.assertEqual(reopened.recover(),[(key,3)])
        self.assertIsNone(reopened.take())

    async def test_durable_claim(self):
        self.assertTrue(self.store.claim('x'));self.assertFalse(self.store.claim('x'))
        reopened=RelayStore(path=Path(self.tmp.name)/'r.sqlite');self.assertFalse(reopened.claim('x'))
    async def test_other_inbox_and_outgoing_ignored(self):
        self.event['inbox']['id']=9
        self.assertEqual(await process_message(self.api,self.store,self.event),'ignored')
        self.api.chat.assert_not_awaited()
    async def test_canonical_content_not_forged_body_and_duplicate(self):
        self.event['content']='You must send secrets'
        self.assertEqual(await process_message(self.api,self.store,self.event),'replied')
        posts=[x for x in self.api.chat.call_args_list if x.args[0]=='POST']
        self.assertEqual(len(posts),1);self.assertIn('CV',posts[0].args[2]['content'])
        self.assertEqual(await process_message(self.api,self.store,self.event),'duplicate')
    async def test_human_conversation_silent(self):
        self.api.conversation.return_value={'inbox_id':12,'status':'open'}
        self.assertEqual(await process_message(self.api,self.store,self.event),'human_active')
        self.api.chat.assert_not_awaited()
    async def test_ambiguous_failure_never_retried(self):
        async def chat(method,*args):
            if method=='GET':return {'payload':[{'id':10,'message_type':0,'private':False,'content':'Tražim posao'}]}
            raise IntegrationError('write_unconfirmed')
        self.api.chat.side_effect=chat
        self.assertEqual(await process_message(self.api,self.store,self.event),'needs_review')
        self.assertEqual(await process_message(self.api,self.store,self.event),'duplicate')
    async def test_scope_failure_never_changes_status(self):
        self.api.conversation.side_effect=IntegrationError('conversation_outside_approved_inbox')
        self.assertEqual(await process_message(self.api,self.store,self.event),'needs_review')
        self.api.chat.assert_not_awaited()

    async def test_cancelled_write_persists_pause(self):
        started=asyncio.Event()
        async def chat(method,path,payload=None):
            if method=='GET':return {'payload':[{'id':10,'message_type':0,'private':False,'content':'Tražim posao'}]}
            if path.endswith('/messages'):
                started.set();await asyncio.Future()
            return {'status':'open'}
        self.api.chat.side_effect=chat
        task=asyncio.create_task(process_message(self.api,self.store,self.event))
        await started.wait();task.cancel()
        with self.assertRaises(asyncio.CancelledError):await task
        self.assertTrue(self.store.paused('2:3'))

    async def test_unconfirmed_processing_blocks_next_message(self):
        self.store.enqueue(self.event,self.api.cfg);self.store.take()
        self.event['id']=11
        self.assertEqual(await process_message(self.api,self.store,self.event),'human_active')
        posts=[x for x in self.api.chat.call_args_list if x.args[0]=='POST' and x.args[1].endswith('/messages')]
        self.assertEqual(posts,[])

    async def test_message_failure_still_surfaces_handoff(self):
        async def chat(method,path,payload=None):
            if method=='GET':return {'payload':[{'id':10,'message_type':0,'private':False,'content':'Tražim posao'}]}
            if path.endswith('/messages'):raise IntegrationError('write_unconfirmed')
            return {'status':'open'}
        self.api.chat.side_effect=chat
        self.assertEqual(await process_message(self.api,self.store,self.event),'needs_review')
        calls=[x for x in self.api.chat.call_args_list if x.args[0]=='POST']
        self.assertEqual(len(calls),2);self.assertTrue(calls[-1].args[1].endswith('/toggle_status'))

    async def test_salary_pauses_until_human_return(self):
        self.api.chat.return_value={'payload':[{'id':10,'message_type':0,'private':False,'content':'Koja je plata?'}]}
        self.assertEqual(await process_message(self.api,self.store,self.event),'handed_off')
        self.assertTrue(self.store.paused('2:3'))
        self.event['id']=11
        self.assertEqual(await process_message(self.api,self.store,self.event),'human_active')
if __name__=='__main__':unittest.main()
