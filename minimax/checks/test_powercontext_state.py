"""Use real PowerContext with temporary fixture states; no model or seekdb mock is claimed as acceptance evidence."""
import asyncio
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from task_state.evidence import attach_state, check_fixed_tests, latest_test
from task_state.powercontext_store import load_state, save_state


def fixture_state(task_id="fixture-task", pending=None):
    return {"schema": "minimax-task-state-v1", "task_id": task_id, "phase": "before",
            "saved_at_utc": datetime.now(timezone.utc).isoformat(), "saved_process_id": os.getpid(),
            "saved_process_instance_id": "synthetic-unit-fixture", "task": "unit test fixture",
            "project_revision": "fixture-revision", "completed": ["fixture step"],
            "pending": ["fixture next action"] if pending is None else pending,
            "validation_results": [], "receipts": {}}


class PowerContextStateChecks(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="minimax-pc-check-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.db = self.root / "state.sqlite3"

    def test_real_powercontext_round_trip_across_processes_and_context_use(self):
        program = '''
import asyncio, json, os, sys
from datetime import datetime, timezone
from task_state.powercontext_store import save_state, load_state
from task_state.evidence import attach_state
async def run():
    if sys.argv[1] == "write":
        state={"schema":"minimax-task-state-v1", "task_id":"cross-process-fixture", "phase":"before",
               "saved_at_utc":datetime.now(timezone.utc).isoformat(), "saved_process_id":os.getpid(),
               "saved_process_instance_id":"fixture-writer", "task":"fixture task",
               "project_revision":"fixture-revision", "completed":["fixture completed"],
               "pending":["unique action read from PowerContext"], "validation_results":[], "receipts":{}}
        metadata=await save_state(sys.argv[2],state)
        print(json.dumps({"pid":os.getpid(),"metadata":metadata}))
    else:
        state,metadata=await load_state(sys.argv[2],"cross-process-fixture")
        context=attach_state({"project_revision":"fixture-revision","documents":[]},state,metadata)
        print(json.dumps({"pid":os.getpid(),"state":state,"metadata":metadata,"context":context}))
asyncio.run(run())
'''
        project = Path(__file__).resolve().parents[1]
        written = subprocess.run([sys.executable, "-c", program, "write", str(self.db)], cwd=project,
                                 capture_output=True, text=True, check=True)
        read = subprocess.run([sys.executable, "-c", program, "read", str(self.db)], cwd=project,
                              capture_output=True, text=True, check=True)
        first, second = json.loads(written.stdout), json.loads(read.stdout)
        self.assertNotEqual(first["pid"], second["pid"])
        self.assertEqual(first["metadata"]["previous_matching_states"], 0)
        self.assertEqual(first["metadata"]["reference"], second["metadata"]["reference"])
        self.assertEqual(second["state"]["saved_process_id"], first["pid"])
        self.assertEqual(second["context"]["next_action"], "unique action read from PowerContext")
        self.assertEqual(second["context"]["task_progress"]["source"], "PowerContext")

    def test_empty_state_is_not_invented(self):
        with self.assertRaisesRegex(ValueError, "checkpoint"):
            asyncio.run(load_state(self.db, "missing-task"))

    def test_latest_task_state_is_selected(self):
        first = fixture_state(pending=["first action"])
        asyncio.run(save_state(self.db, first))
        second = fixture_state(pending=["newer action"])
        saved = asyncio.run(save_state(self.db, second))
        loaded, metadata = asyncio.run(load_state(self.db, "fixture-task"))
        self.assertEqual(saved["previous_matching_states"], 1)
        self.assertEqual(loaded["pending"], ["newer action"])
        self.assertEqual(saved["reference"], metadata["reference"])

    def test_changed_project_is_not_treated_as_same_checkpoint(self):
        with self.assertRaisesRegex(ValueError, "changed"):
            attach_state({"project_revision": "different-revision"}, fixture_state(),
                         {"reference": {}, "scope_id": "fixture"})

    def test_modified_fixed_test_is_rejected(self):
        (self.root / "snapshots").mkdir()
        (self.root / "tests").mkdir()
        original = b"assert expected_behavior\n"
        (self.root / "snapshots/before_manifest.json").write_text(json.dumps({
            "tests/test_target.py": hashlib.sha256(original).hexdigest()}), encoding="utf-8")
        (self.root / "tests/test_target.py").write_bytes(b"assert True\n")
        with self.assertRaisesRegex(ValueError, "Fixed test file changed"):
            check_fixed_tests(self.root)

    def test_environment_error_cannot_be_recorded_as_before_function_failure(self):
        directory = self.root / "evidence/before"
        directory.mkdir(parents=True)
        (directory / "target_fixture.json").write_text(json.dumps({
            "suite": "target", "label": "before", "started_at_utc": "fixture",
            "exit_code": 1, "output": "ERROR: ModuleNotFoundError\nFAILED (errors=1)"}), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "assertion failure"):
            latest_test(self.root, "before", "target")


if __name__ == "__main__":
    unittest.main()
