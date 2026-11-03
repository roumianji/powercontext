import json
from contextlib import closing, contextmanager
from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path

from .catalog import revision


class Store:
    """The SQL boundary. Context content comes from SELECT results, not local reads."""

    def __init__(self, connection):
        self.connection = connection
        self.trace = []

    def execute(self, sql, parameters=()):
        with closing(self.connection.cursor()) as cursor:
            count = cursor.execute(sql, tuple(parameters))
            rows = [dict(row) for row in cursor.fetchall()] if cursor.description else []
        self.trace.append({"sql": sql, "parameters": list(parameters), "affected_or_returned_rows": count,
                           "returned_sources": [row["source_path"] for row in rows if "source_path" in row]})
        return rows

    def initialize(self):
        self.execute("""CREATE TABLE IF NOT EXISTS minimax_docs (
            source_path VARCHAR(512) NOT NULL PRIMARY KEY,
            kind VARCHAR(32) NOT NULL,
            content LONGTEXT NOT NULL,
            sha256 CHAR(64) NOT NULL,
            metadata_json LONGTEXT NOT NULL
        )""")
        self.execute("""CREATE TABLE IF NOT EXISTS minimax_meta (
            meta_key VARCHAR(64) NOT NULL PRIMARY KEY,
            meta_value LONGTEXT NOT NULL
        )""")

    def import_documents(self, documents):
        project_revision = revision(documents)
        # Only these two application-owned tables are replaced, in one transaction.
        try:
            self.connection.begin()
            self.execute("DELETE FROM minimax_docs")
            for item in documents:
                self.execute(
                    "INSERT INTO minimax_docs (source_path, kind, content, sha256, metadata_json) VALUES (%s,%s,%s,%s,%s)",
                    (item["source_path"], item["kind"], item["content"], item["sha256"],
                     json.dumps(item["metadata"], ensure_ascii=False)),
                )
            self.execute("DELETE FROM minimax_meta")
            for key, value in (("project_revision", project_revision),
                               ("imported_at_utc", datetime.now(timezone.utc).isoformat())):
                self.execute("INSERT INTO minimax_meta (meta_key, meta_value) VALUES (%s,%s)", (key, value))
            self.connection.commit()
        except Exception:
            self.connection.rollback()
            raise
        return project_revision

    def metadata(self):
        return {row["meta_key"]: row["meta_value"] for row in self.execute("SELECT meta_key, meta_value FROM minimax_meta")}

    def search(self, terms):
        clauses = []
        parameters = []
        for term in terms:
            clauses.append("(LOCATE(%s, LOWER(content)) > 0 OR LOCATE(%s, LOWER(source_path)) > 0)")
            parameters.extend((term, term))
        sql = "SELECT source_path, kind, content, sha256, metadata_json FROM minimax_docs WHERE "
        sql += " OR ".join(clauses) + " ORDER BY source_path"
        rows = self.execute(sql, parameters)
        for row in rows:
            row["metadata"] = json.loads(row.pop("metadata_json"))
        order = {"spec": 0, "code": 1, "target_test": 2, "regression_test": 3, "test": 4, "data": 5}
        return sorted(rows, key=lambda row: (order.get(row["kind"], 9), row["source_path"]))


@contextmanager
def open_store(path):
    try:
        import pylibseekdb
        import pymysql
    except ImportError as error:
        raise RuntimeError("Install requirements first: python -m pip install -r requirements-seekdb.txt") from error
    path = Path(path).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    with closing(pylibseekdb.open(str(path))) as runtime:
        with pymysql.connect(database="test", autocommit=True, charset="utf8mb4",
                             cursorclass=pymysql.cursors.DictCursor, **runtime.connection_options()) as connection:
            store = Store(connection)
            store.initialize()
            server_version = store.execute("SELECT VERSION() AS server_version")[0]["server_version"]
            store.database_info = {"engine": "seekdb", "server_version": server_version,
                                   "pylibseekdb": version("pylibseekdb"), "PyMySQL": version("PyMySQL")}
            yield store
