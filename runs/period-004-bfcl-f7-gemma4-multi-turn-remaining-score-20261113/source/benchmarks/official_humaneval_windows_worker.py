"""Run pinned upstream unsafe_execute in a JobObject-owned worker on Windows."""
import contextlib,importlib.util,json,pathlib,sys

def main():
    payload=json.load(sys.stdin)
    root=pathlib.Path(__file__).resolve().parents[1]
    source=root/'.local/official-humaneval-b9453e8/human_eval/execution.py'
    spec=importlib.util.spec_from_file_location('official_humaneval_execution',source)
    upstream=importlib.util.module_from_spec(spec);spec.loader.exec_module(upstream)
    # Windows lacks setitimer/SIGALRM; the parent enforces a wall deadline.
    upstream.time_limit=lambda seconds:contextlib.nullcontext()
    result=[]
    upstream.unsafe_execute(payload['problem'],payload['completion'],3.0,result)
    print(json.dumps({'result':result[0]}))

if __name__=='__main__':main()
