"""Caller checks with simulated MiniMax responses, NOT actual MiniMax usage evidence.

All flow fixtures live in temporary directories. The production caller contains
no preset solution or simulated-provider fallback.
"""
import io
import json
import shutil
import tempfile
import unittest
import urllib.error
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

from coding_assistant import api, flow
from coding_assistant.change import TARGET, parse_change
from coding_assistant.config import Config


class FakeResponse(io.BytesIO):
    def __init__(self, payload):
        super().__init__(json.dumps(payload).encode())
        self.headers = {"x-request-id": "unit-fixture-request"}


class CallerChecks(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="minimax-caller-check-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        project = Path(__file__).resolve().parents[1]
        for folder in ("demo_app", "tests", "data", "snapshots", "tools", "specs"):
            shutil.copytree(project / folder, self.root / folder, ignore=shutil.ignore_patterns("__pycache__", "evidence"))
        self.original = (self.root / TARGET).read_text(encoding="utf-8")
        # Explicit, temporary unit-test fixture; never used by production generation.
        replacement = '''        if "status" in query:
            status = query["status"]
            if status not in VALID_STATUSES:
                raise ValueError("invalid status")
            tasks = [task for task in tasks if task["status"] == status]
'''
        anchor = '        keyword = query.get("q", "").strip().casefold()\n'
        self.candidate = self.original.replace(anchor, replacement + anchor)
        self.config = Config(api_key="unit-fixture-key-not-real")
        self.context = {"task": "unit fixture task", "task_progress": {"reference": {"artifact_id": "unit-fixture-reference"}}}

    def response(self, content=None, path=TARGET):
        return json.dumps({"summary": "unit fixture", "files": [{"path": path, "content": content or self.candidate}]})

    def test_only_target_function_body_is_accepted(self):
        content, _ = parse_change(self.response(), self.original)
        self.assertEqual(content, self.candidate)

    def test_test_file_modification_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "不能修改测试"):
            parse_change(self.response(path="tests/test_target.py"), self.original)

    def test_changes_to_other_business_behavior_are_rejected(self):
        changed = self.candidate.replace('("todo", "doing", "done")', '("todo", "done")')
        with self.assertRaisesRegex(ValueError, "超出了"):
            parse_change(self.response(changed), self.original)

    def test_no_op_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "没有修改"):
            parse_change(self.response(self.original), self.original)

    def test_private_thinking_is_not_retained_in_public_result(self):
        payload = {"content": [{"type": "thinking", "thinking": "PRIVATE_FIXTURE"},
                               {"type": "text", "text": "<think>PRIVATE_TAG_FIXTURE</think>public answer"}]}
        self.assertEqual(api.public_text(payload), "public answer")

    def test_http_body_and_metadata_omit_authentication_and_thinking(self):
        config = self.config
        test = self
        class Opener:
            def open(self, request, timeout):
                test.assertEqual(request.full_url, config.base_url + "/v1/messages")
                test.assertEqual(request.get_header("Authorization"), "Bearer " + config.api_key)
                sent = json.loads(request.data)
                test.assertEqual(sent["model"], config.model)
                test.assertNotIn(config.api_key, request.data.decode())
                return FakeResponse({"id": "unit-fixture-response", "model": config.model,
                    "stop_reason": "end_turn", "usage": {"input_tokens": 10, "output_tokens": 20},
                    "content": [{"type": "thinking", "thinking": "PRIVATE_FIXTURE"},
                                {"type": "text", "text": "public answer"}]})
        text, metadata = api.call(config, api.request_body(self.context, config), opener=Opener())
        self.assertEqual(text, "public answer")
        self.assertNotIn(config.api_key, json.dumps(metadata))
        self.assertNotIn("PRIVATE_FIXTURE", json.dumps(metadata))
        self.assertEqual(metadata["request_id"], "unit-fixture-request")

    def test_http_error_is_redacted_and_not_retried(self):
        config = self.config
        class Opener:
            count = 0
            def open(self, request, timeout):
                self.count += 1
                raise urllib.error.HTTPError(request.full_url, 401, "fixture", {},
                    io.BytesIO(("bad key " + config.api_key).encode()))
        opener = Opener()
        with self.assertRaises(RuntimeError) as caught:
            api.call(config, {}, opener=opener)
        self.assertEqual(opener.count, 1)
        self.assertNotIn(config.api_key, str(caught.exception))

    def run_fixture(self, text, finalize_side_effect=None):
        metadata = {"stop_reason": "end_turn", "response_id": "unit-fixture-response", "usage": {}}
        with (patch.object(flow, "prepare_context", return_value=(self.context, b'{"synthetic_unit_fixture":true}')),
              patch.object(flow.api, "call", return_value=(text, metadata)),
              patch.object(flow, "finalize_steps", side_effect=finalize_side_effect),
              redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO())):
            code = flow.run(self.root, self.config, "unit-fixture-task")
        path = next((self.root / "evidence/minimax").glob("*/record.json"))
        return code, json.loads(path.read_text(encoding="utf-8")), path.parent

    def test_simulated_success_runs_fixed_tests_and_saves_matching_snapshots(self):
        initial_tests = {path.name: path.read_bytes() for path in (self.root / "tests").glob("*.py")}
        code, record, directory = self.run_fixture(self.response())
        self.assertEqual(code, 0)
        self.assertTrue(record["code_validated"])
        self.assertEqual(record["test_exit_codes"], {"target": 0, "regression": 0})
        self.assertEqual((directory / "before" / TARGET).read_text(encoding="utf-8"), self.original)
        self.assertEqual((directory / "after" / TARGET).read_text(encoding="utf-8"), self.candidate)
        self.assertEqual((self.root / TARGET).read_text(encoding="utf-8"), self.candidate)
        self.assertEqual(initial_tests, {path.name: path.read_bytes() for path in (self.root / "tests").glob("*.py")})

    def test_failing_candidate_is_preserved_but_live_source_is_rolled_back(self):
        changed = self.original.replace('        query = query or {}\n', '        query = query or {}\n        unused_status = query.get("status")\n')
        code, record, directory = self.run_fixture(self.response(changed))
        self.assertEqual(code, 1)
        self.assertTrue(record["rolled_back"])
        self.assertFalse(record["code_validated"])
        self.assertEqual((self.root / TARGET).read_text(encoding="utf-8"), self.original)
        self.assertEqual((directory / "after" / TARGET).read_text(encoding="utf-8"), changed)

    def test_finalization_failure_preserves_validated_code(self):
        code, record, _ = self.run_fixture(self.response(), finalize_side_effect=RuntimeError("unit fixture finalize failure"))
        self.assertEqual(code, 1)
        self.assertTrue(record["code_validated"])
        self.assertFalse(record["rolled_back"])
        self.assertEqual(record["status"], "finalize_failed")
        self.assertEqual((self.root / TARGET).read_text(encoding="utf-8"), self.candidate)


if __name__ == "__main__":
    unittest.main()
