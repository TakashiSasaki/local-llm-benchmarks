"""Pinned checker/converter definitions, loaded as in the original measurement adapter."""
import ast,copy,hashlib,json,re,sys,types
from .study import ROOT,load
def components():
    vendor=ROOT/'vendor/bfcl';sys.path.insert(0,str(vendor))
    for base in [vendor,ROOT/'datasets/bfcl/6ea5797']:
        for rel,expected in load(base/'manifest.json')['files'].items():assert hashlib.sha256((base/rel).read_bytes()).hexdigest()==expected,rel
    registry=types.ModuleType('bfcl_eval.constants.model_config');registry.MODEL_CONFIG_MAPPING={'local':types.SimpleNamespace(underscore_to_dot=True)};sys.modules[registry.__name__]=registry
    from bfcl_eval.constants.enums import Language,ModelStyle
    from bfcl_eval.constants.type_mappings import GORILLA_TO_OPENAPI
    from bfcl_eval.eval_checker.ast_eval.ast_checker import ast_checker
    archive=vendor
    ns={'copy':copy,'json':json,'re':re,'Language':Language,'ModelStyle':ModelStyle,'GORILLA_TO_OPENAPI':GORILLA_TO_OPENAPI,'ast_checker':ast_checker}
    for path,names in [(archive/'handler_utils.py',{'_cast_to_openai_type','convert_to_tool'}),(archive/'study_adapter_snapshot.py',{'check','golden'})]:
        tree=ast.parse(path.read_text(encoding='utf-8'));nodes=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in names];assert len(nodes)==len(names)
        exec(compile(ast.Module(body=nodes,type_ignores=[]),str(path),'exec'),ns)
    cases=load(ROOT/'datasets/bfcl/6ea5797/selected-80.json')
    for c in cases:
        assert ns['check'](c,ns['golden'](c))['valid']
        assert not ns['check'](c,[{'not_a_valid_function':{}}] if c['category']=='irrelevance' else [])['valid']
    def tools(c):return ns['convert_to_tool'](c['problem']['function'],GORILLA_TO_OPENAPI,ModelStyle.OPENAI_COMPLETIONS)
    def grade(c,response):
        decoded=[];error=None
        try:
            for call in response['choices'][0]['message'].get('tool_calls') or []:
                args=json.loads(call['function']['arguments'])
                if not isinstance(args,dict):raise ValueError('Non-object arguments')
                decoded.append({call['function']['name']:args})
            outcome=ns['check'](c,decoded)
        except (ValueError,KeyError,TypeError) as exc:error=str(exc);outcome={'valid':False,'error':[error]}
        return {'passed':outcome['valid'],'grade':outcome,'decoded':decoded,'decode_error':error}
    return cases,tools,grade
