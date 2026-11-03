import argparse
import asyncio
import json
import os
import sys
import uuid
from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path

from context_module.__main__ import make_context, write_json
from context_module.database import open_store
from . import __version__
from .evidence import assemble_state, attach_state, verify_saved_receipts
from .powercontext_store import load_state, save_state


def main():
    parser = argparse.ArgumentParser(description="用 PowerContext 保存和恢复课程作业进度")
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--task-id", default="status-filter-v1")
    parser.add_argument("--state-db", type=Path, default=Path(".runtime/powercontext.sqlite3"))
    parser.add_argument("--engineering-db", type=Path, default=Path(".runtime/engineering.seekdb"))
    subparsers = parser.add_subparsers(dest="command", required=True)
    checkpoint = subparsers.add_parser("checkpoint", help="核对实际验证结果并保存状态")
    checkpoint.add_argument("--phase", choices=("before", "after"), default="before")
    subparsers.add_parser("resume", help="从 PowerContext 恢复状态，并用于构造后续上下文")
    args = parser.parse_args()
    root = args.root.resolve()
    state_db = args.state_db.resolve() if args.state_db.is_absolute() else (root / args.state_db).resolve()
    engineering_db = args.engineering_db.resolve() if args.engineering_db.is_absolute() else (root / args.engineering_db).resolve()
    instance_id = uuid.uuid4().hex
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ") + "_" + instance_id[:8]
    evidence_path = root / "evidence/powercontext" / f"{stamp}_{args.command}.json"
    record = {"started_at_utc": datetime.now(timezone.utc).isoformat(),
              "command": [sys.executable, "-m", "task_state", *sys.argv[1:]],
              "process_id": os.getpid(), "process_instance_id": instance_id,
              "working_directory": str(Path.cwd()), "state_database": str(state_db),
              "task_id": args.task_id, "module_version": __version__, "exit_code": None}
    exit_code = 0
    try:
        record["powercontext_version"] = version("powercontext")
        if args.command == "checkpoint":
            state = assemble_state(root, args.task_id, args.phase, instance_id)
            metadata = asyncio.run(save_state(state_db, state))
            record.update({"operation": "AtomicMemory.create", "state": state, "powercontext": metadata})
            print("任务状态已保存到 PowerContext。", flush=True)
            print(f"此前同任务状态数量：{metadata['previous_matching_states']}", flush=True)
        else:
            state, metadata = asyncio.run(load_state(state_db, args.task_id))
            verify_saved_receipts(root, state)
            with open_store(engineering_db) as store:
                context = make_context(store, root, state["task"])
                record["engineering_database_queries"] = store.trace
                record["engineering_database"] = store.database_info
            merged = attach_state(context, state, metadata)
            current = root / ".runtime/context_with_state.json"
            archived = root / "evidence/context" / f"{stamp}_with_state.json"
            write_json(current, merged)
            write_json(archived, merged)
            record.update({"operation": "AtomicMemory.list/get", "state": state, "powercontext": metadata,
                           "saved_process_id": state["saved_process_id"],
                           "different_process": state["saved_process_id"] != os.getpid(),
                           "different_process_instance": state["saved_process_instance_id"] != instance_id,
                           "used_for_context": archived.relative_to(root).as_posix(),
                           "next_action": merged["next_action"]})
            print("已从 PowerContext 恢复任务状态，并用于后续开发上下文。", flush=True)
            print(f"保存进程 PID：{state['saved_process_id']}；当前进程 PID：{os.getpid()}", flush=True)
            print(f"包含进度的上下文：{current.relative_to(root)}", flush=True)
            print(f"下一步：{merged['next_action']}", flush=True)
        print(f"任务：{state['task']}", flush=True)
        print("已完成：", flush=True)
        for item in state["completed"]:
            print(f"  - {item}", flush=True)
        print("已有验证：", flush=True)
        for item in state["validation_results"]:
            print(f"  - {item['phase']}/{item['suite']}: exit_code={item['exit_code']}; {'; '.join(item['summary'])}", flush=True)
        print("待办：", flush=True)
        for item in state["pending"]:
            print(f"  - {item}", flush=True)
        ref = metadata["reference"]
        print(f"PowerContext 引用：{ref['family']}/{ref['artifact_id']}@{ref['revision']}", flush=True)
    except Exception as error:
        exit_code = 1
        record["error"] = {"type": type(error).__name__, "message": str(error)}
        print(f"失败：{type(error).__name__}: {error}", file=sys.stderr, flush=True)
    finally:
        record["exit_code"] = exit_code
        record["finished_at_utc"] = datetime.now(timezone.utc).isoformat()
        write_json(evidence_path, record)
        print(f"PowerContext 操作记录：{evidence_path.relative_to(root)}", flush=True)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
