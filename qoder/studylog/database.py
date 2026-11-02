"""seekdb 数据库层：连接管理、建表、增删查改。"""

import json
from contextlib import closing, contextmanager
from datetime import date, datetime
from pathlib import Path

DB_PATH = Path(__file__).parent / "data" / "studylog.seekdb"


@contextmanager
def open_store(path=None):
    """打开 seekdb 连接，自动初始化和关闭。"""
    try:
        import pylibseekdb
        import pymysql
    except ImportError as error:
        raise RuntimeError(
            "请先安装依赖: pip install -r requirements.txt"
        ) from error

    path = Path(path or DB_PATH).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)

    with closing(pylibseekdb.open(str(path))) as runtime:
        with pymysql.connect(
            database="test",
            autocommit=True,
            charset="utf8mb4",
            cursorclass=pymysql.cursors.DictCursor,
            **runtime.connection_options(),
        ) as connection:
            store = Store(connection)
            store.initialize()
            yield store


class Store:
    """封装所有 SQL 操作。"""

    def __init__(self, connection):
        self.connection = connection

    def execute(self, sql, parameters=()):
        with closing(self.connection.cursor()) as cursor:
            count = cursor.execute(sql, tuple(parameters))
            rows = [dict(row) for row in cursor.fetchall()] if cursor.description else []
        return rows

    def initialize(self):
        self.execute("""CREATE TABLE IF NOT EXISTS study_logs (
            id INT AUTO_INCREMENT PRIMARY KEY,
            log_date DATE NOT NULL,
            project VARCHAR(128) NOT NULL,
            completed TEXT NOT NULL,
            problems TEXT,
            next_plan TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )""")

    def add_log(self, log_date: str, project: str, completed: str,
                problems: str = "", next_plan: str = "") -> int:
        """新增一条研习记录，返回新记录 ID。"""
        self.execute(
            "INSERT INTO study_logs (log_date, project, completed, problems, next_plan) "
            "VALUES (%s, %s, %s, %s, %s)",
            (log_date, project, completed, problems, next_plan),
        )
        rows = self.execute("SELECT LAST_INSERT_ID() AS new_id")
        return rows[0]["new_id"]

    def query_logs(self, date_from: str = None, date_to: str = None,
                   project: str = None, keyword: str = None) -> list:
        """按条件筛选研习记录。"""
        conditions = []
        params = []

        if date_from:
            conditions.append("log_date >= %s")
            params.append(date_from)
        if date_to:
            conditions.append("log_date <= %s")
            params.append(date_to)
        if project:
            conditions.append("project = %s")
            params.append(project)
        if keyword:
            conditions.append(
                "(completed LIKE %s OR problems LIKE %s OR next_plan LIKE %s)"
            )
            like = f"%{keyword}%"
            params.extend([like, like, like])

        sql = "SELECT * FROM study_logs"
        if conditions:
            sql += " WHERE " + " AND ".join(conditions)
        sql += " ORDER BY log_date DESC, id DESC"

        return self.execute(sql, params)

    def list_projects(self) -> list:
        """返回所有已出现的项目名（去重）。"""
        rows = self.execute(
            "SELECT DISTINCT project FROM study_logs ORDER BY project"
        )
        return [r["project"] for r in rows]

    def get_log_by_id(self, log_id: int) -> dict | None:
        rows = self.execute("SELECT * FROM study_logs WHERE id = %s", (log_id,))
        return rows[0] if rows else None

    def get_db_info(self) -> dict:
        rows = self.execute("SELECT VERSION() AS ver")
        return {"engine": "seekdb", "version": rows[0]["ver"]} if rows else {}
