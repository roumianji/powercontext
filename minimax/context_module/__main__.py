import argparse
import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

from . import __version__
from .catalog import collect_documents, digest, revision, task_terms
from .database import open_store


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def make_context(store, root, task):
    metadata = store.metadata()
    if "project_revision" not in metadata:
        raise ValueError("No project imported; run: python -m context_module ingest")
    current = collect_documents(root)
    if revision(current) != metadata["project_revision"]:
        raise ValueError("Engineering sources changed; re-import them with: python -m context_module ingest")
    terms = task_terms(task)
    documents = store.search(terms)
    if not documents:
        raise ValueError("No matching database documents; use a more specific task or symbol.")
    # Verify provenance; do not use disk content to construct the returned context.
    for item in documents:
        path = (root / item["source_path"]).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            raise ValueError(f"Database source no longer exists inside the project: {item['source_path']}")
        if digest(item["content"].encode("utf-8")) != item["sha256"] or digest(path.read_bytes()) != item["sha256"]:
            raise ValueError(f"Stale or inconsistent source; re-import: {item['source_path']}")
    return {"schema": "minimax-sdd-context-v1", "module_version": __version__, "task": task,
            "created_at_utc": datetime.now(timezone.utc).isoformat(), "terms": terms,
            "project_revision": metadata["project_revision"], "imported_at_utc": metadata["imported_at_utc"],
            "database": store.database_info, "selection": "parameterized SQL keyword search over current imported engineering sources",
            "documents": documents}


def main():
    parser = argparse.ArgumentParser(description="导入工程资料，并通过 seekdb 查询开发上下文")
    parser.add_argument("--root", type=Path, default=Path.cwd(), help="包含 demo_app、specs、tests 的 minimax 目录")
    parser.add_argument("--db", type=Path, default=Path(".runtime/engineering.seekdb"))
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("ingest", help="导入或重新导入当前有效资料")
    context_parser = subparsers.add_parser("context", help="按任务查询并生成上下文")
    context_parser.add_argument("--task", required=True)
    args = parser.parse_args()
    root = args.root.resolve()
    db_path = args.db.resolve() if args.db.is_absolute() else (root / args.db).resolve()
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ") + "_" + uuid.uuid4().hex[:8]
    record_path = root / "evidence/database" / f"{run_id}_{args.command}.json"
    record = {"started_at_utc": datetime.now(timezone.utc).isoformat(), "command": [sys.executable, "-m", "context_module", *sys.argv[1:]],
              "working_directory": str(Path.cwd()), "project_root": str(root), "database_path": str(db_path),
              "module_version": __version__, "exit_code": None}
    exit_code = 0
    store = None
    try:
        with open_store(db_path) as store:
            record["database"] = store.database_info
            if args.command == "ingest":
                documents = collect_documents(root)
                project_revision = store.import_documents(documents)
                record.update({"project_revision": project_revision, "documents": [
                    {"source_path": item["source_path"], "kind": item["kind"], "sha256": item["sha256"]} for item in documents]})
                print(f"已导入 {len(documents)} 份工程资料。", flush=True)
                print(f"资料版本：{project_revision}", flush=True)
                for item in documents:
                    print(f"  [{item['kind']}] {item['source_path']}", flush=True)
            else:
                context = make_context(store, root, args.task)
                context_path = root / ".runtime/context.json"
                evidence_path = root / "evidence/context" / f"{run_id}.json"
                write_json(context_path, context)
                write_json(evidence_path, context)
                record.update({"project_revision": context["project_revision"], "context_evidence": evidence_path.relative_to(root).as_posix(),
                               "selected_sources": [item["source_path"] for item in context["documents"]]})
                print(f"已从 seekdb 查询得到 {len(context['documents'])} 份上下文资料。", flush=True)
                print("检索词：" + ", ".join(context["terms"]), flush=True)
                for item in context["documents"]:
                    print(f"  [{item['kind']}] {item['source_path']}", flush=True)
                    for requirement in item["metadata"]["requirements"]:
                        print(f"    {requirement['id']} @ line {requirement['line']}", flush=True)
                print(f"完整上下文：{context_path.relative_to(root)}", flush=True)
                print(f"上下文证据：{evidence_path.relative_to(root)}", flush=True)
    except Exception as error:
        exit_code = 1
        record["error"] = {"type": type(error).__name__, "message": str(error)}
        print(f"失败：{type(error).__name__}: {error}", file=sys.stderr, flush=True)
    finally:
        if store is not None:
            record["queries"] = store.trace
        record["exit_code"] = exit_code
        record["finished_at_utc"] = datetime.now(timezone.utc).isoformat()
        write_json(record_path, record)
        print(f"数据库操作记录：{record_path.relative_to(root)}", flush=True)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
