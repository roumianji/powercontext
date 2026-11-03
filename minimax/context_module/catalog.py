import ast
import hashlib
import json
import re
from pathlib import Path


SOURCES = (("specs", "*.md", "spec"), ("demo_app", "*.py", "code"),
           ("tests", "test_*.py", "test"), ("data", "*.json", "data"))


def digest(value):
    return hashlib.sha256(value).hexdigest()


def read_symbols(content):
    result = []

    def walk(node, prefix=""):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                name = prefix + child.name
                result.append({"name": name, "line_start": child.lineno, "line_end": child.end_lineno})
                walk(child, name + ".")

    walk(ast.parse(content))
    return result


def collect_documents(root):
    root = Path(root).resolve()
    documents = []
    for directory, pattern, kind in SOURCES:
        for path in sorted((root / directory).rglob(pattern)):
            if path.name == "__init__.py":
                continue
            if not path.resolve().is_relative_to(root):
                raise ValueError(f"Source points outside project: {path}")
            raw = path.read_bytes()
            if len(raw) > 256 * 1024:
                raise ValueError(f"Source exceeds this demo's 256 KiB per-file limit: {path}")
            content = raw.decode("utf-8")
            source_path = path.relative_to(root).as_posix()
            source_kind = kind
            if kind == "test":
                source_kind = {"test_target.py": "target_test", "test_regression.py": "regression_test"}.get(path.name, "test")
            requirements = []
            if kind == "spec":
                for number, line in enumerate(content.splitlines(), 1):
                    match = re.match(r"\s*-\s+([A-Z][A-Z0-9_-]*-\d+)\s*[：:]\s*(.*)", line)
                    if match:
                        requirements.append({"id": match.group(1), "line": number, "text": match.group(2)})
            metadata = {
                "line_start": 1, "line_end": len(content.splitlines()),
                "symbols": read_symbols(content) if path.suffix == ".py" else [],
                "requirements": requirements,
            }
            documents.append({"source_path": source_path, "kind": source_kind, "content": content,
                              "sha256": digest(raw), "metadata": metadata})
    if not documents:
        raise ValueError("No engineering sources found; run from the minimax directory containing specs/, demo_app/ and tests/.")
    return sorted(documents, key=lambda item: item["source_path"])


def revision(documents):
    manifest = {item["source_path"]: item["sha256"] for item in documents}
    return digest(json.dumps(manifest, sort_keys=True).encode("utf-8"))


def task_terms(task):
    stop = {"the", "a", "an", "and", "or", "to", "for", "of", "add", "task", "tasks"}
    terms = [word.casefold() for word in re.findall(r"[A-Za-z_][A-Za-z0-9_]{1,63}", task)]
    aliases = {"状态": "status", "筛选": "filter", "标题": "title", "创建": "create",
               "删除": "delete", "更新": "update", "关键词": "keyword", "关键字": "keyword"}
    terms.extend(english for chinese, english in aliases.items() if chinese in task)
    terms = list(dict.fromkeys(term for term in terms if term not in stop))[:12]
    if not terms:
        raise ValueError("No searchable task terms found; include a symbol or a field such as status, title or list_tasks.")
    return terms
