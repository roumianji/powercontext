import json
import unittest
from pathlib import Path

from demo_app.service import TaskBoard


class StatusFilterTests(unittest.TestCase):
    def setUp(self):
        path = Path(__file__).resolve().parents[1] / "data/tasks.json"
        self.board = TaskBoard(json.loads(path.read_text(encoding="utf-8")))

    def test_todo(self):
        tasks = self.board.list_tasks({"status": "todo"})
        self.assertEqual([task["id"] for task in tasks], [1, 4])

    def test_doing(self):
        tasks = self.board.list_tasks({"status": "doing"})
        self.assertEqual([task["id"] for task in tasks], [2])

    def test_done(self):
        tasks = self.board.list_tasks({"status": "done"})
        self.assertEqual([task["id"] for task in tasks], [3])

    def test_invalid_status(self):
        with self.assertRaises(ValueError):
            self.board.list_tasks({"status": "unknown"})

    def test_keyword_and_status_are_combined(self):
        tasks = self.board.list_tasks({"q": "论文", "status": "done"})
        self.assertEqual(tasks, [])

    def test_no_matching_status(self):
        board = TaskBoard([{"id": 1, "title": "单个任务", "status": "todo"}])
        self.assertEqual(board.list_tasks({"status": "done"}), [])
