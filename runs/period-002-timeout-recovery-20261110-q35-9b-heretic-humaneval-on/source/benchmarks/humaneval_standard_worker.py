"""Single-use official HumanEval execution body; parent owns Windows timeout/job."""
import contextlib,importlib.util,json,pathlib,sys

def main():
    # Wait for the parent to assign the resource-limited job before executing input.
    payload=json.load(sys.stdin)
    file=pathlib.Path(__file__).resolve().parents[1]/'vendor/humaneval/b9453e8/execution.py'
    spec=importlib.util.spec_from_file_location('pinned_humaneval_execution',file)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    # Windows has no setitimer/SIGALRM. Parent kills this entire job on timeout.
    module.time_limit=lambda seconds:contextlib.nullcontext()
    problem=dict(payload['problem'],prompt='');result=[]
    try:
        module.unsafe_execute(problem,payload['code'],6,result)
        value=result[0]
        print(json.dumps({'passed':value=='passed','status':'passed' if value=='passed' else 'test_failed','detail':value}))
    except BaseException as error:
        print(json.dumps({'passed':False,'status':'adapter_error','detail':repr(error)}))

if __name__=='__main__':main()
