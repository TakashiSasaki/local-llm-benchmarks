"""Create one versioned experiment directory; does not start inference."""
import argparse,pathlib,sys
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'src'))
from local_llm_benchmarks.study import create_run,load,EXPERIMENT_TYPES
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--name',required=True);p.add_argument('--benchmark',required=True);p.add_argument('--config',type=pathlib.Path);p.add_argument('--id');p.add_argument('--type',choices=EXPERIMENT_TYPES,default='benchmark');p.add_argument('--harness');p.add_argument('--period');args=p.parse_args()
    path=create_run(args.name,args.benchmark,load(args.config) if args.config else {},args.id,experiment_type=args.type,harness=args.harness,period=args.period);print(path)
