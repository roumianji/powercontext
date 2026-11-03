from copy import deepcopy


VALID_STATUSES = ("todo", "doing", "done")


class TaskBoard:
    def __init__(self, tasks=()):
        self._tasks = {task["id"]: deepcopy(task) for task in tasks}

    def list_tasks(self, query=None):
        """List tasks in insertion order; the original version supports q."""
        query = query or {}
        tasks = deepcopy(list(self._tasks.values()))
        keyword = query.get("q", "").strip().casefold()
        if keyword:
            tasks = [task for task in tasks if keyword in task["title"].casefold()]
        if "status" in query:
            status = query["status"]
            if status not in VALID_STATUSES:
                raise ValueError("invalid status")
            tasks = [task for task in tasks if task["status"] == status]
        return tasks

    def create_task(self, title):
        title = title.strip()
        if not title:
            raise ValueError("title must not be blank")
        task_id = max(self._tasks, default=0) + 1
        task = {"id": task_id, "title": title, "status": "todo"}
        self._tasks[task_id] = task
        return deepcopy(task)

    def set_status(self, task_id, status):
        if status not in VALID_STATUSES:
            raise ValueError("invalid status")
        self._tasks[task_id]["status"] = status
        return deepcopy(self._tasks[task_id])

    def delete_task(self, task_id):
        del self._tasks[task_id]
