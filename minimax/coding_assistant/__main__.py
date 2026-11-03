import argparse
import sys
from pathlib import Path

from .config import configure, load
from .flow import finalize, run


def main():
    parser = argparse.ArgumentParser(description="使用 MiniMax 根据真实开发上下文修改业务代码")
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--task-id", default="status-filter-v1")
    parser.add_argument("command", choices=("configure", "run", "finalize"))
    args = parser.parse_args()
    root = args.root.resolve()
    try:
        if args.command == "configure":
            configure(root)
            return 0
        if args.command == "finalize":
            return finalize(root)
        return run(root, load(root), args.task_id)
    except Exception as error:
        # Configuration errors do not include the entered key.
        print(f"失败：{type(error).__name__}: {error}", file=sys.stderr, flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
