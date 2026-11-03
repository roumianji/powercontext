import json
import unittest
from pathlib import Path

from demo_app.service import TaskBoard


class ExistingBehaviorTests(unittest.TestCase):
    def setUp(self):
        path = Path(__file__).resolve().parents[1] / "data/tasks.json"
        self.board = TaskBoard(json.loads(path.read_text(encoding="utf-8")))

    def test_default_list_keeps_order(self):
        self.assertEqual([task["id"] for task in self.board.list_tasks()], [1, 2, 3, 4])

    def test_title_keyword(self):
        tasks = self.board.list_tasks({"q": "论文"})
        self.assertEqual([task["id"] for task in tasks], [1, 4])

    def test_blank_keyword(self):
        self.assertEqual(len(self.board.list_tasks({"q": "  "})), 4)

    def test_keyword_is_case_insensitive(self):
        board = TaskBoard([{"id": 1, "title": "Read Python", "status": "todo"}])
        self.assertEqual(len(board.list_tasks({"q": "PYTHON"})), 1)

    def test_create(self):
        task = self.board.create_task("  新任务  ")
        self.assertEqual(task, {"id": 5, "title": "新任务", "status": "todo"})
        self.assertEqual(len(self.board.list_tasks()), 5)

    def test_blank_title_rejected(self):
        with self.assertRaises(ValueError):
            self.board.create_task("  ")

    def test_change_status(self):
        self.assertEqual(self.board.set_status(1, "done")["status"], "done")
        self.assertEqual(self.board.list_tasks()[0]["status"], "done")

    def test_invalid_status_update_rejected(self):
        with self.assertRaises(ValueError):
            self.board.set_status(1, "unknown")

    def test_delete(self):
        self.board.delete_task(2)
        self.assertEqual([task["id"] for task in self.board.list_tasks()], [1, 3, 4])

    def test_results_do_not_expose_internal_state(self):
        self.board.list_tasks()[0]["title"] = "changed outside"
        self.assertEqual(self.board.list_tasks()[0]["title"], "阅读论文")
