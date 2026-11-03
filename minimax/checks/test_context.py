"""Portable logic checks using a SQLite SQL adapter, NOT seekdb acceptance evidence.

Native seekdb startup/read/write must additionally be exercised by the CLI on the
target machine. These checks cover source selection, updates and transactions.
"""
import json
import shutil
import sqlite3
import tempfile
import unittest
from pathlib import Path

from context_module.__main__ import make_context
from context_module.catalog import collect_documents, revision, task_terms
from context_module.database import Store


class CursorAdapter:
    def __init__(self, cursor):
        self.cursor = cursor

    @property
    def description(self):
        return self.cursor.description

    def execute(self, sql, parameters):
        self.cursor.execute(sql.replace("%s", "?"), parameters)
        return self.cursor.rowcount

    def fetchall(self):
        return self.cursor.fetchall()

    def close(self):
        self.cursor.close()


class ConnectionAdapter:
    def __init__(self, connection):
        self.connection = connection

    def cursor(self):
        return CursorAdapter(self.connection.cursor())

    def begin(self):
        self.connection.execute("BEGIN")

    def commit(self):
        self.connection.commit()

    def rollback(self):
        self.connection.rollback()


class ContextLogicChecks(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="minimax-context-check-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        project = Path(__file__).resolve().parents[1]
        for directory in ("specs", "demo_app", "tests", "data"):
            shutil.copytree(project / directory, self.root / directory,
                            ignore=shutil.ignore_patterns("__pycache__"))
        self.connection = sqlite3.connect(":memory:", isolation_level=None)
        self.addCleanup(self.connection.close)
        self.connection.row_factory = sqlite3.Row
        self.connection.create_function("LOCATE", 2, lambda needle, text: text.find(needle) + 1)
        self.store = Store(ConnectionAdapter(self.connection))
        self.store.database_info = {"engine": "sqlite-validation-adapter"}
        self.store.initialize()
        self.documents = collect_documents(self.root)
        self.store.import_documents(self.documents)

    def test_context_contains_required_real_sources(self):
        context = make_context(self.store, self.root, "给任务列表增加 status 筛选，保持原有功能")
        paths = {item["source_path"] for item in context["documents"]}
        self.assertTrue({"specs/task_list.md", "demo_app/service.py", "demo_app/__main__.py",
                         "tests/test_target.py", "tests/test_regression.py", "data/tasks.json"}.issubset(paths))
        specifications = [item for item in context["documents"] if item["kind"] == "spec"]
        ids = {rule["id"] for item in specifications for rule in item["metadata"]["requirements"]}
        self.assertTrue({f"KEEP-{number:03}" for number in range(1, 6)}.issubset(ids))
        self.assertTrue({f"STATUS-{number:03}" for number in range(1, 5)}.issubset(ids))
        service = next(item for item in context["documents"] if item["source_path"] == "demo_app/service.py")
        symbols = {item["name"] for item in service["metadata"]["symbols"]}
        self.assertIn("TaskBoard.list_tasks", symbols)
        self.assertEqual(service["content"], (self.root / service["source_path"]).read_text(encoding="utf-8"))

    def test_chinese_status_query_selects_sources(self):
        context = make_context(self.store, self.root, "增加状态筛选")
        self.assertIn("status", context["terms"])
        self.assertTrue(any(item["kind"] == "target_test" for item in context["documents"]))

    def test_unrelated_query_does_not_return_fixed_sources(self):
        with self.assertRaisesRegex(ValueError, "No matching database documents"):
            make_context(self.store, self.root, "unrelated_symbol_xyz")

    def test_changed_spec_requires_reimport_and_new_content_is_used(self):
        original_revision = self.store.metadata()["project_revision"]
        path = self.root / "specs/task_list.md"
        addition = "\n- STATUS-005：status 参数使用小写，DONE 视为无效状态。\n"
        path.write_text(path.read_text(encoding="utf-8") + addition, encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "re-import"):
            make_context(self.store, self.root, "status 筛选")
        updated_documents = collect_documents(self.root)
        self.store.import_documents(updated_documents)
        context = make_context(self.store, self.root, "status 筛选")
        self.assertNotEqual(original_revision, context["project_revision"])
        specification = next(item for item in context["documents"] if item["kind"] == "spec")
        self.assertIn(addition.strip(), specification["content"])
        self.assertIn("STATUS-005", [rule["id"] for rule in specification["metadata"]["requirements"]])

    def test_reimport_removes_deleted_source(self):
        path = self.root / "specs/temporary_rule.md"
        path.write_text("temporary status rule", encoding="utf-8")
        self.store.import_documents(collect_documents(self.root))
        self.assertTrue(any(item["source_path"] == "specs/temporary_rule.md" for item in self.store.search(["status"])))
        path.unlink()
        self.store.import_documents(collect_documents(self.root))
        self.assertFalse(any(item["source_path"] == "specs/temporary_rule.md" for item in self.store.search(["status"])))

    def test_failed_import_rolls_back_previous_snapshot(self):
        bad_documents = [self.documents[0], self.documents[0]]
        with self.assertRaises(sqlite3.IntegrityError):
            self.store.import_documents(bad_documents)
        self.assertEqual(self.store.metadata()["project_revision"], revision(self.documents))
        context = make_context(self.store, self.root, "status 筛选")
        self.assertTrue(any(item["source_path"] == "specs/task_list.md" for item in context["documents"]))

    def test_query_trace_contains_parameterized_select_and_returned_paths(self):
        make_context(self.store, self.root, "status 筛选")
        selected = next(item for item in reversed(self.store.trace) if "WHERE" in item["sql"])
        self.assertIn("%s", selected["sql"])
        self.assertIn("status", selected["parameters"])
        self.assertIn("demo_app/service.py", selected["returned_sources"])
        json.dumps(self.store.trace, ensure_ascii=False)


if __name__ == "__main__":
    unittest.main()
