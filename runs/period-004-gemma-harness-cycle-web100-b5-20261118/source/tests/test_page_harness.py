import importlib.util, json, pathlib, tempfile, unittest, sys
P=pathlib.Path(__file__).resolve().parents[1]/'integrations/page_harness/page_harness.py'
spec=importlib.util.spec_from_file_location('page_harness',P);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

class HarnessTest(unittest.TestCase):
    def test_page_reread_and_source(self):
        with tempfile.TemporaryDirectory() as d:
            store=m.PageStore(d); text='# Introduction\n'+'x'*3000+'\n## Pricing\nPrice is 42 yen.\n';page=store.add('https://example.org/a',text)
            self.assertEqual([x['heading'] for x in page['headings']],['Introduction','Pricing'])
            match=store.find(page['page_id'],'42 yen')['matches'][0];part=store.read(page['page_id'],match['read_offset'])
            self.assertIn('42 yen',part['content']);self.assertEqual(part['url'],'https://example.org/a')
            self.assertEqual(json.loads((pathlib.Path(d)/'page_1.json').read_text(encoding='utf8'))['text'],text)
            with self.assertRaises(ValueError):store.read('page_1',-1)
    def test_compaction_keeps_last_and_can_reread(self):
        msgs=[{'role':'tool','tool_call_id':str(i),'content':'x'*8000,'_page_read':{'page_id':'page_1','offset':i*2400}} for i in range(4)]
        changed=m.compact(msgs,limit=17000,keep=2);self.assertEqual(len(changed),2);self.assertEqual(msgs[0]['tool_call_id'],'0');self.assertIn('retrieve it again',msgs[0]['content']);self.assertEqual(len(msgs[-1]['content']),8000)
    def test_keyword_fallback_preserves_source_and_offset(self):
        with tempfile.TemporaryDirectory() as d:
            store=m.PageStore(d);text='# Intro\nNothing relevant.\n'+'filler '*400+'\n## Usage\njson.dumps(obj, ensure_ascii=True) serializes data.';info=store.add('https://example.org/json',text)
            found=store.find(info['page_id'],'json.dumps ensure_ascii default');self.assertEqual(found['mode'],'ranked_terms');self.assertTrue(found['matches']);best=found['matches'][0]
            self.assertIn('json.dumps',best['matched_terms']);self.assertIn('ensure_ascii',best['matched_terms']);self.assertEqual(best['section']['heading'],'Usage')
            self.assertIn('ensure_ascii=True',store.read(info['page_id'],best['read_offset'])['content'])
            self.assertEqual(store.find(info['page_id'],'quantum banana')['matches'],[])
    def test_japanese_approximate_find(self):
        with tempfile.TemporaryDirectory() as d:
            store=m.PageStore(d);x=store.add('https://example.org','# 説明\n価格は100円。発売日は月曜日。')
            found=store.find(x['page_id'],'価格 発売日');self.assertEqual(found['mode'],'ranked_terms');self.assertEqual(set(found['matches'][0]['matched_terms']),{'価格','発売日'})
    def test_outline_paginates(self):
        with tempfile.TemporaryDirectory() as d:
            store=m.PageStore(d);x=store.add('https://example.org','\n'.join(f'# Section {i}\nBody' for i in range(40)))
            self.assertEqual(len(x['headings']),30);self.assertEqual(store.outline(x['page_id'],30)['headings'][0]['heading'],'Section 30')
            with self.assertRaises(ValueError):store.outline(x['page_id'],-1)
    def test_citations_distinguish_read_from_search_only(self):
        pages={'page_1':{'url':'https://example.org/read'},'page_2':{'url':'https://en.wikipedia.org/wiki/Example_(sample)'}}
        answer='Claim one (https://example.org/read#part). Claim two https://notread.org/item. See page_2.'
        report=m.audit_citations(answer,pages,{'page_1'},{'https://notread.org/item'})
        self.assertEqual([x['state'] for x in report['urls']],['read_page','search_only']);self.assertTrue(report['warnings']);self.assertEqual(report['page_id_references'][0]['page_id'],'page_2');self.assertFalse(report['page_id_references'][0]['read'])
        s=m.audit_citations('See https://en.wikipedia.org/wiki/Example_(sample).',pages,{'page_2'},set());self.assertEqual(s['urls'][0]['state'],'read_page')
        md=m.audit_citations('[https://example.org/read](https://example.org/read)',pages,{'page_1'},set());self.assertEqual([x['state'] for x in md['urls']],['read_page','read_page']);self.assertFalse(md['warnings'])
    def test_pagination_and_inconsistency(self):
        class C:
            def call(self,name,args):
                if name=='md':return {'document_id':'id','total_chars':7,'offset':0,'content':'abcd','has_more':True,'next_offset':4,'source_url':'https://example.org'}
                return {'document_id':'id','total_chars':7,'offset':4,'content':'efg','has_more':False}
        self.assertEqual(m.fetch_snapshot(C(),'https://example.org')[0],'abcdefg')
        class Bad(C):
            def call(self,name,args):
                r=super().call(name,args)
                if name=='read_document':r['document_id']='other'
                return r
        with self.assertRaises(ValueError):m.fetch_snapshot(Bad(),'https://example.org')
    def test_agent_loop_uses_saved_page(self):
        sys.path.insert(0,str(P.parent));import run_probe as probe
        def msg(name,args,id):return {'role':'assistant','content':None,'tool_calls':[{'id':id,'type':'function','function':{'name':name,'arguments':json.dumps(args)}}]}
        seq=[msg('search',{'query':'fact'},'1'),msg('open_page',{'url':'https://example.org/fact'},'2'),msg('find_in_page',{'page_id':'page_1','query':'answer'},'3'),msg('read_page',{'page_id':'page_1','offset':0},'4'),{'role':'assistant','content':'42 https://example.org/fact'}]
        class Search:
            def call(self,name,args):return {'result':[{'title':'fact','url':'https://example.org/fact','content':'hint'}]}
        old=(probe.local_api,probe.public_url,probe.fetch_snapshot)
        def api(route,data=None,timeout=0):
            if route=='/apply-template':return {'prompt':'fixture'}
            if route=='/tokenize':return {'tokens':[1,2,3]}
            return {'choices':[{'message':seq.pop(0),'finish_reason':'stop'}]}
        probe.local_api=api
        probe.public_url=lambda url:None;probe.fetch_snapshot=lambda client,url:('# Fact\nthe answer is 42',{'document_id':'snapshot'})
        try:
            with tempfile.TemporaryDirectory() as d:
                p=pathlib.Path(d);(p/'raw').mkdir();answer=probe.run_case(p,'example','fact?',Search(),object());self.assertIn('42',answer)
                result=json.loads((p/'raw/example/result.json').read_text(encoding='utf8'));self.assertEqual({k:result['counts'][k] for k in ('search','open_page','read_page','find_in_page','page_outline')},{'search':1,'open_page':1,'read_page':1,'find_in_page':1,'page_outline':0});self.assertIsNone(result['citation_warning'])
                self.assertTrue(result['source_ledger']);self.assertEqual(result['source_ledger'][-1]['url'],'https://example.org/fact')
        finally:probe.local_api,probe.public_url,probe.fetch_snapshot=old
    def test_mcp_rate_limit_stops(self):
        class Reply:
            status_code=429
        class Session:
            headers={}
            def post(self,*a,**kw):return Reply()
        with self.assertRaises(m.BackendStop):m.MCP('https://example.org/mcp',Session(),lambda x:None).rpc('tools/list')
    def test_context_budget_stops_before_generation(self):
        sys.path.insert(0,str(P.parent));import run_probe as probe
        old=probe.local_api;routes=[]
        def api(route,data=None,timeout=0):
            routes.append(route)
            return {'prompt':'fixture'} if route=='/apply-template' else {'tokens':[1]*65536}
        probe.local_api=api
        try:
            with tempfile.TemporaryDirectory() as d:
                p=pathlib.Path(d);(p/'raw').mkdir();self.assertEqual(probe.run_case(p,'example','fact?',object(),object()),'')
                result=json.loads((p/'raw/example/result.json').read_text(encoding='utf8'));self.assertEqual(result['status'],'context_budget_exhausted');self.assertNotIn('/v1/chat/completions',routes)
        finally:probe.local_api=old
    def test_no_snippet_and_compacted_page_is_reread(self):
        sys.path.insert(0,str(P.parent));import run_probe as probe
        def call(name,args,id):return {'role':'assistant','content':None,'tool_calls':[{'id':id,'type':'function','function':{'name':name,'arguments':json.dumps(args)}}]}
        seq=[call('search',{'query':'fact'},'1'),call('open_page',{'url':'https://example.org/fact'},'2'),call('read_page',{'page_id':'page_1','offset':0},'3'),call('read_page',{'page_id':'page_1','offset':2400},'4'),call('read_page',{'page_id':'page_1','offset':0},'5'),{'role':'assistant','content':'42 https://example.org/fact'}]
        class Search:
            def call(self,name,args):return {'result':[{'title':'fact','url':'https://example.org/fact','content':'secret snippet'}]}
        captured=[]
        def api(route,data=None,timeout=0):
            if route=='/apply-template':return {'prompt':'fixture'}
            if route=='/tokenize':return {'tokens':[1,2,3]}
            captured.append(data);return {'choices':[{'message':seq.pop(0),'finish_reason':'stop'}]}
        old=(probe.local_api,probe.public_url,probe.fetch_snapshot);probe.local_api=api;probe.public_url=lambda url:None;probe.fetch_snapshot=lambda client,url:('# Fact\nanswer 42\n'+'x'*6000,{'document_id':'snapshot'})
        try:
            with tempfile.TemporaryDirectory() as d:
                p=pathlib.Path(d);(p/'raw').mkdir();probe.run_case(p,'example','fact?',Search(),object(),{'show_snippets':False,'compaction_mode':'legacy','compact_chars':1000,'compact_keep':1})
                events=json.loads((p/'raw/example/events.json').read_text(encoding='utf8'));self.assertTrue(any(e['type']=='compaction' for e in events))
                reads=[e['arguments']['offset'] for e in events if e.get('name')=='read_page' and e['type']=='tool'];self.assertEqual(reads,[0,2400,0])
                search_results=[e['result'] for e in events if e.get('name')=='search' and e['type']=='tool'];self.assertNotIn('secret snippet',json.dumps(search_results))
                self.assertTrue(any(e['type']=='search_backend' and 'secret snippet' in json.dumps(e) for e in events))
                self.assertTrue(any('Earlier page excerpt compacted' in json.dumps(req) for req in captured))
        finally:probe.local_api,probe.public_url,probe.fetch_snapshot=old
    def test_parallel_new_excerpts_are_shown_before_compaction(self):
        sys.path.insert(0,str(P.parent));import run_probe as probe
        def fn(name,args,id):return {'id':id,'type':'function','function':{'name':name,'arguments':json.dumps(args)}}
        seq=[{'role':'assistant','content':None,'tool_calls':[fn('search',{'query':'fact'},'1')]},{'role':'assistant','content':None,'tool_calls':[fn('open_page',{'url':'https://example.org/fact'},'2')]},{'role':'assistant','content':None,'tool_calls':[fn('read_page',{'page_id':'page_1','offset':0},'3'),fn('read_page',{'page_id':'page_1','offset':2400},'4')]},{'role':'assistant','content':'done https://example.org/fact'}]
        class Search:
            def call(self,name,args):return {'result':[{'title':'fact','url':'https://example.org/fact','content':'hint'}]}
        captured=[]
        def api(route,data=None,timeout=0):
            if route=='/apply-template':return {'prompt':'fixture'}
            if route=='/tokenize':return {'tokens':[1,2,3]}
            captured.append(data);return {'choices':[{'message':seq.pop(0),'finish_reason':'stop'}]}
        old=(probe.local_api,probe.public_url,probe.fetch_snapshot);probe.local_api=api;probe.public_url=lambda url:None;probe.fetch_snapshot=lambda client,url:('ZERO'+('a'*2396)+'SECOND'+('b'*3000),{'document_id':'snapshot'})
        try:
            with tempfile.TemporaryDirectory() as d:
                p=pathlib.Path(d);(p/'raw').mkdir();probe.run_case(p,'example','fact?',Search(),object(),{'compaction_mode':'legacy','compact_chars':1000,'compact_keep':1})
                seen={x.get('tool_call_id'):x.get('content','') for x in captured[-1]['messages'] if x.get('role')=='tool'}
                self.assertIn('ZERO',seen['3']);self.assertIn('SECOND',seen['4']);self.assertNotIn('compacted',seen['3'])
        finally:probe.local_api,probe.public_url,probe.fetch_snapshot=old

if __name__=='__main__':unittest.main()
