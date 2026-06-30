"""Todoist integration (API v1).

Docs: https://developer.todoist.com/api/v1/
Needs: TODOIST_API_TOKEN

The old REST v2 endpoint (rest/v2/tasks) was retired and now returns 410.
Filtered queries live at /api/v1/tasks/filter, take a `query` param, and
return a cursor-paginated object: {"results": [...], "next_cursor": ...}.
"""
import requests

from .base import Integration

API_URL = "https://api.todoist.com/api/v1/tasks/filter"
CLOSE_URL = "https://api.todoist.com/api/v1/tasks/{task_id}/close"


class TodoistIntegration(Integration):
    name = "todoist"

    def __init__(self, env, cache_ttl=300):
        super().__init__(env, cache_ttl)
        self.token = env.get("TODOIST_API_TOKEN", "").strip()
        self.filter = env.get("TODOIST_FILTER", "today | overdue").strip()

    def is_configured(self):
        return bool(self.token)

    def fetch_real(self):
        headers = {"Authorization": f"Bearer {self.token}"}
        tasks = []
        cursor = None
        # Cursor-paginated; loop until the API stops handing back a cursor.
        while True:
            params = {"query": self.filter, "limit": 200}
            if cursor:
                params["cursor"] = cursor
            resp = requests.get(API_URL, headers=headers, params=params, timeout=10)
            resp.raise_for_status()
            payload = resp.json()
            tasks.extend(payload.get("results", []))
            cursor = payload.get("next_cursor")
            if not cursor:
                break

        # Sort: higher priority first (Todoist p1 == priority 4), then due date.
        def sort_key(t):
            due = t.get("due") or {}
            # Empty string sorts last only if we invert; use a high sentinel.
            return (-t.get("priority", 1), due.get("date") or "9999-12-31")

        tasks.sort(key=sort_key)

        items = []
        for t in tasks:
            due = t.get("due") or {}
            items.append(
                {
                    "id": t.get("id"),
                    "content": t.get("content", ""),
                    "priority": t.get("priority", 1),  # 1..4, 4 = urgent
                    "due": due.get("string", ""),
                }
            )
        return {"tasks": items, "count": len(items)}

    def complete_task(self, task_id: str):
        """Mark a task done in Todoist. Recurring tasks roll to their next
        occurrence automatically (the API's close behavior). No-op when not
        configured. Returns (ok, message)."""
        if not self.is_configured():
            return False, "Todoist not configured"
        if not task_id:
            return False, "No task id"
        try:
            resp = requests.post(
                CLOSE_URL.format(task_id=task_id),
                headers={"Authorization": f"Bearer {self.token}"},
                timeout=10,
            )
            resp.raise_for_status()
        except Exception as exc:
            return False, str(exc)
        # Bust the cache so the completed task disappears on the next render.
        self._cache = None
        return True, "ok"

    def mock(self):
        return {
            "tasks": [
                {"id": "1", "content": "Set up Todoist API token", "priority": 4, "due": "today"},
                {"id": "2", "content": "Wire the Kindle to local WiFi", "priority": 3, "due": "today"},
                {"id": "3", "content": "Read on the new dashboard", "priority": 1, "due": "today"},
            ],
            "count": 3,
        }
