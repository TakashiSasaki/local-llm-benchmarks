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
        changed=m.compact(msgs,limit=17000,keep=2);self.assertEqual(len(changed),2);self.assertEqual(msgs[0]['tool_call_id'],'0');self.assertIn('reread',msgs[0]['content']);self.assertEqual(len(msgs[-1]['content']),8000)
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
        probe.local_api=lambda route,data=None,timeout=0:{'choices':[{'message':seq.pop(0),'finish_reason':'stop'}]}
        probe.public_url=lambda url:None;probe.fetch_snapshot=lambda client,url:('# Fact\nthe answer is 42',{'document_id':'snapshot'})
        try:
            with tempfile.TemporaryDirectory() as d:
                p=pathlib.Path(d);(p/'raw').mkdir();answer=probe.run_case(p,'example','fact?',Search(),object());self.assertIn('42',answer)
                result=json.loads((p/'raw/example/result.json').read_text(encoding='utf8'));self.assertEqual(result['counts'],{'search':1,'open_page':1,'read_page':1,'find_in_page':1})
        finally:probe.local_api,probe.public_url,probe.fetch_snapshot=old

if __name__=='__main__':unittest.main()
