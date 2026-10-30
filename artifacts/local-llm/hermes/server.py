"""Reuse the verified lifecycle helper with isolated Hermes state and profiles."""
import argparse
import importlib.util
import pathlib

WORK = pathlib.Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("local_llm_server", WORK.parent / "scripts/server.py")
server = importlib.util.module_from_spec(spec)
spec.loader.exec_module(server)
server.ROOT = WORK

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["start", "stop"])
    parser.add_argument("profile", choices=["daily", "large"], nargs="?", default="daily")
    args = parser.parse_args()
    server.start(args.profile) if args.action == "start" else server.stop()
