import ast
import difflib
import hashlib
import json
import os
import tempfile
from pathlib import Path


TARGET = "demo_app/service.py"


def sha256(raw):
    return hashlib.sha256(raw).hexdigest()


def masked(source):
    tree = ast.parse(source)
    targets = [node for cls in tree.body if isinstance(cls, ast.ClassDef) and cls.name == "TaskBoard"
               for node in cls.body if isinstance(node, ast.FunctionDef) and node.name == "list_tasks"]
    if len(targets) != 1:
        raise ValueError("需要且只能有一个 TaskBoard.list_tasks 函数。")
    method = targets[0]
    body = ast.dump(ast.Module(body=method.body, type_ignores=[]), include_attributes=False)
    for node in ast.walk(method):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            raise ValueError("本次函数修改不需要新增 import。")
        if isinstance(node, ast.Attribute) and node.attr.startswith("__"):
            raise ValueError("本次函数修改不需要访问双下划线属性。")
        if isinstance(node, ast.Name) and node.id in {"eval", "exec", "open", "__import__", "compile", "globals", "locals", "breakpoint"}:
            raise ValueError("候选代码包含与本次数据筛选无关的执行或文件操作。")
    method.body = [ast.Pass()]
    return ast.dump(tree, include_attributes=False), body


def parse_change(text, original):
    text = text.strip()
    if text.startswith("```") and text.endswith("```"):
        lines = text.splitlines()
        text = "\n".join(lines[1:-1])
    result = json.loads(text)
    if not isinstance(result, dict) or not set(result).issubset({"summary", "files"}):
        raise ValueError("模型输出应为约定的 summary/files JSON 对象。")
    files = result.get("files")
    if not isinstance(files, list) or len(files) != 1 or files[0].get("path") != TARGET:
        raise ValueError("本次只能修改 demo_app/service.py，不能修改测试或其他文件。")
    content = files[0].get("content")
    if not isinstance(content, str) or not content.strip() or len(content.encode("utf-8")) > 256 * 1024:
        raise ValueError("候选源码内容为空或超出本样例上限。")
    if not content.endswith("\n"):
        content += "\n"
    before_tree, before_body = masked(original)
    after_tree, after_body = masked(content)
    if before_tree != after_tree:
        raise ValueError("候选修改超出了 TaskBoard.list_tasks 函数体。")
    if before_body == after_body:
        raise ValueError("模型没有修改目标函数的逻辑。")
    compile(content, TARGET, "exec")
    return content, str(result.get("summary", ""))


def atomic_write(path, raw):
    path = Path(path)
    mode = path.stat().st_mode & 0o777 if path.exists() else 0o644
    descriptor, temporary = tempfile.mkstemp(prefix=".minimax-change-", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, mode)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def diff(before, after):
    return "".join(difflib.unified_diff(before.splitlines(keepends=True), after.splitlines(keepends=True),
                                       fromfile="before/" + TARGET, tofile="after/" + TARGET))
