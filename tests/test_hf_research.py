import importlib.util
import json
import pathlib
import unittest
import urllib.error
from unittest.mock import patch

ROOT=pathlib.Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('hf_research',ROOT/'scripts/collect_hf_research.py')
collector=importlib.util.module_from_spec(spec);spec.loader.exec_module(collector)


class HubResearch(unittest.TestCase):
    def test_metadata_only_and_templates_are_hashed(self):
        visited=[]
        def fetch(url):
            visited.append(url)
            if '/api/models/' in url:
                return json.dumps({'sha':'a'*40,'gguf':{'architecture':'qwen35','chat_template':'private template body'},'config':{'tokenizer_config':{'chat_template':'nested private template body'}},'cardData':{'license':'apache-2.0'},'siblings':[{'rfilename':'test.Q4_K_M.gguf','size':123,'lfs':{'sha256':'b'*64}},{'rfilename':'huge.F16.gguf','size':999}]}).encode()
            if url.endswith('config.json'):return b'{"model_type":"qwen3_5"}'
            if url.endswith('README.md'):return b'Author card; not published verbatim'
            raise AssertionError('Unexpected file retrieval '+url)
        with patch.object(collector,'fetch',side_effect=fetch):result=collector.collect('example/test')
        self.assertEqual(len(visited),3)
        self.assertEqual(result['selected_files'][0]['sha256'],'b'*64)
        self.assertEqual(len(result['selected_files']),1)
        self.assertNotIn('chat_template',result['gguf'])
        self.assertEqual(len(result['gguf']['chat_template_sha256']),64)
        self.assertNotIn('private template body',json.dumps(result))
        self.assertEqual(len(result['config']['tokenizer_config']['chat_template_sha256']),64)
        self.assertFalse(any(url.endswith('.gguf') for url in visited))

    def test_inaccessible_repo_stays_an_error_not_a_candidate(self):
        with patch.object(collector,'fetch',side_effect=urllib.error.HTTPError('url',401,'Unauthorized',None,None)):
            result=collector.collect('example/unknown')
        self.assertEqual(result['http_status'],401)
        self.assertNotIn('revision',result)
