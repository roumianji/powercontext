import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from .service import TaskBoard


def main():
    parser = argparse.ArgumentParser(description="Task list HTTP demo")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8088)
    parser.add_argument("--data", type=Path, default=Path(__file__).resolve().parents[1] / "data/tasks.json")
    args = parser.parse_args()
    board = TaskBoard(json.loads(args.data.read_text(encoding="utf-8")))

    class Handler(BaseHTTPRequestHandler):
        def respond(self, status, payload):
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            parsed = urlsplit(self.path)
            if parsed.path == "/health":
                self.respond(200, {"status": "ok"})
                return
            if parsed.path != "/tasks":
                self.respond(404, {"error": "not found"})
                return
            query = {key: values[-1] for key, values in parse_qs(parsed.query, keep_blank_values=True).items()}
            try:
                self.respond(200, board.list_tasks(query))
            except ValueError as error:
                self.respond(400, {"error": str(error)})

    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"Task demo running at http://{args.host}:{server.server_port}/tasks", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
