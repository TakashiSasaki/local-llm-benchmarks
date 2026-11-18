"""Classify saved BFCL response ASTs without executing model-generated code."""
import ast,collections,json,pathlib
ROOT=pathlib.Path(__file__).resolve().parents[1]
RUNS=('period-004-bfcl-f7-gemma4-multi-turn-20261113',
      'period-004-bfcl-f7-gemma4-multi-turn-remaining-20261113',
      'period-004-bfcl-f7-gemma4-multi-turn-pending-20261113',
      'period-004-bfcl-f7-gemma4-multi-turn-pending-v2-20261113',
      'period-004-bfcl-f7-gemma4-multi-turn-pending-v3-20261113',
      'period-004-bfcl-f7-gemma4-multi-turn-pending-v4-20261113')

def main():
    counts=collections.Counter();ops=collections.Counter();references=collections.defaultdict(list)
    for name in RUNS:
        for path in sorted((ROOT/'runs'/name/'raw/http').glob('*.json')):
            row=json.loads(path.read_text(encoding='utf8'));case=row['case_id']
            text=(row['response']['choices'][0]['message']['content'] or '').strip('`\n ')
            if not text.startswith('['):text='['+text
            if not text.endswith(']'):text+=']'
            counts['responses']+=1
            try:tree=ast.parse(text,mode='eval')
            except SyntaxError:counts['syntax_error']+=1;continue
            counts['parsed']+=1
            flags=set()
            for node in ast.walk(tree):
                if isinstance(node,ast.BinOp):
                    key=type(node.op).__name__;ops[key]+=1;flags.add('binary_'+key)
                elif isinstance(node,ast.Lambda):flags.add('lambda')
                elif isinstance(node,ast.Subscript):flags.add('subscript')
                elif isinstance(node,ast.Attribute):flags.add('attribute')
                elif isinstance(node,ast.Call) and isinstance(node.func,ast.Call):flags.add('nested_callee')
                elif isinstance(node,ast.Call) and isinstance(node.func,ast.Attribute):flags.add('attribute_callee')
                elif isinstance(node,ast.Call) and any(k.arg is None for k in node.keywords):flags.add('keyword_unpack')
            for flag in flags:
                counts['response_'+flag]+=1
                if len(references[flag])<20:references[flag].append({'run':name,'file':path.name,'case':case})
    assert counts['responses']==1012,counts['responses']
    print(json.dumps({'counts':dict(counts),'binary_operators':dict(ops),'examples':dict(references)},indent=2))

if __name__=='__main__':main()
