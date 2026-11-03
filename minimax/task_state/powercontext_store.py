import json
from contextlib import asynccontextmanager
from pathlib import Path


KIND = "minimax-task-state"
SCOPE_TITLE = "MiniMax SDD 课程作业"
SCOPE_SUMMARY = "Validated task progress for the MiniMax SDD coursework."
SCOPE_KEY = "minimax-sdd-coursework-v1"
EXTERNAL_KIND = "coursework"
EXTERNAL_VALUE = "minimax-sdd-v1"


@asynccontextmanager
async def runtime_for(path):
    from powercontext.builtin.persistence.sqlite import SQLiteConfig
    from powercontext.builtin.runtime import BuiltinConfig, open_builtin_runtime

    path = Path(path).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    config = BuiltinConfig(database=SQLiteConfig(url="sqlite+aiosqlite:///" + str(path)))
    async with open_builtin_runtime(config, scheduler_path=path.parent / "powercontext.scheduler.sqlite3") as runtime:
        yield runtime


async def scope_for(runtime, *, create):
    from powercontext.builtin.scope.models import ScopeDraft, ScopeExternalReference

    if create:
        descriptor = await runtime.scopes.create(ScopeDraft(
            title=SCOPE_TITLE, summary=SCOPE_SUMMARY, idempotency_key=SCOPE_KEY,
            external_references=(ScopeExternalReference(kind=EXTERNAL_KIND, value=EXTERNAL_VALUE),),
        ))
        return descriptor.scope_id
    scopes = [scope for scope in await runtime.scopes.list()
              if any(item.kind == EXTERNAL_KIND and item.value == EXTERNAL_VALUE for item in scope.external_references)]
    if len(scopes) != 1:
        raise ValueError("No unique saved coursework Scope found; create a checkpoint first.")
    return scopes[0].scope_id


async def task_records(memory, task_id):
    found = []
    cursor = None
    while True:
        page = await memory.list(kind=KIND, limit=50, cursor=cursor)
        for record in page.items:
            content = json.loads(record.artifact.content.text)
            if content.get("schema") == "minimax-task-state-v1" and content.get("task_id") == task_id:
                found.append((record, content))
        if page.next_cursor is None:
            return found
        cursor = page.next_cursor


async def save_state(database_path, state):
    from powercontext.builtin.artifacts.atomic_memory.models import AtomicMemoryContent

    text = json.dumps(state, ensure_ascii=False, separators=(",", ":"))
    if len(text.encode("utf-8")) > 8192:
        raise ValueError("Task summary exceeds PowerContext's 8192-byte Atomic Memory limit.")
    async with runtime_for(database_path) as runtime:
        scope_id = await scope_for(runtime, create=True)
        memory = runtime.atomic_memory.for_scope(scope_id)
        previous = await task_records(memory, state["task_id"])
        result = await memory.create([AtomicMemoryContent(kind=KIND, text=text)])
        return {"scope_id": scope_id, "reference": result.primary.ref.model_dump(mode="json"),
                "previous_matching_states": len(previous), "sdk_response": result.model_dump(mode="json", by_alias=True)}


async def load_state(database_path, task_id):
    async with runtime_for(database_path) as runtime:
        scope_id = await scope_for(runtime, create=False)
        memory = runtime.atomic_memory.for_scope(scope_id)
        records = await task_records(memory, task_id)
        if not records:
            raise ValueError(f"No saved task state in PowerContext: {task_id}")
        record, _ = max(records, key=lambda item: (item[1]["saved_at_utc"], item[0].ref.artifact_id))
        # Resolve the exact immutable revision after discovery.
        loaded = await memory.get(record.ref.artifact_id, revision=record.ref.revision)
        state = json.loads(loaded.artifact.content.text)
        return state, {"scope_id": scope_id, "reference": loaded.ref.model_dump(mode="json"),
                       "sdk_response": loaded.model_dump(mode="json", by_alias=True)}
