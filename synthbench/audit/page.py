"""The audit page (P5a design §4): one still at a time, keyboard answers, an append-only log.

`AuditApp.handle(method, path, body)` is the whole application and is tested without a socket;
`serve()` puts it behind `http.server` on 127.0.0.1 only.
"""

from __future__ import annotations

import json
import threading
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from html import escape
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from synthbench.audit.sample import Question
from synthbench.export.vss import ExportedSet

ANSWERS = ("y", "n", "u")


@dataclass(frozen=True)
class AuditItem:
    exported: ExportedSet
    questions: tuple[Question, ...]

    @property
    def event_id(self) -> str:
        return str(self.exported.facts["event_id"])


@dataclass(frozen=True)
class Response:
    status: int
    content_type: str
    body: bytes


def load_answers(log: Path) -> dict[tuple[str, str], str]:
    """The latest answer per (event id, question key)."""
    answers: dict[tuple[str, str], str] = {}
    if log.exists():
        for line in log.read_text(encoding="utf-8").splitlines():
            if line.strip():
                row = json.loads(line)
                answers[(row["event_id"], row["question"])] = row["answer"]
    return answers


class AuditApp:
    """The page's routes over a fixed list of items and one answer log."""

    def __init__(self, items: Sequence[AuditItem], log: Path, now: Callable[[], str]) -> None:
        self.items = list(items)
        self.log = log
        self.now = now
        self.answers = load_answers(log)
        self._lock = threading.Lock()

    def answered(self, item: AuditItem) -> bool:
        return all((item.event_id, q.key) in self.answers for q in item.questions)

    def next_open(self) -> int:
        """The first item with an unanswered question, or -1 when every item is answered."""
        return next((i for i, item in enumerate(self.items) if not self.answered(item)), -1)

    def handle(self, method: str, path: str, body: bytes) -> Response:
        if method == "GET" and path in ("", "/"):
            return self._page(self.next_open())
        if method == "GET" and path.startswith("/item/"):
            index = self._index(path.removeprefix("/item/"))
            return self._page(index) if index is not None else _not_found()
        if method == "GET" and path.startswith("/still/"):
            index = self._index(path.removeprefix("/still/"))
            if index is None:
                return _not_found()
            data = self.items[index].exported.still.read_bytes()
            return Response(200, "image/jpeg", data)
        if method == "POST" and path == "/answer":
            return self._answer(body)
        return _not_found()

    def _index(self, text: str) -> int | None:
        return int(text) if text.isdigit() and int(text) < len(self.items) else None

    def _answer(self, body: bytes) -> Response:
        try:
            request = json.loads(body)
            item = self.items[int(request["index"])]
            key, answer = str(request["question"]), str(request["answer"])
        except ValueError, KeyError, IndexError, TypeError:
            return Response(400, "text/plain", b"expected {index, question, answer}")
        if answer not in ANSWERS or key not in {q.key for q in item.questions}:
            return Response(400, "text/plain", b"unknown question or answer")
        row = {
            "event_id": item.event_id,
            "question": key,
            "answer": answer,
            "time": self.now(),
        }
        with self._lock:
            self.log.parent.mkdir(parents=True, exist_ok=True)
            with self.log.open("a", encoding="utf-8") as out:
                out.write(json.dumps(row, sort_keys=True) + "\n")
            self.answers[(item.event_id, key)] = answer
        body_out = json.dumps({"next": self.next_open()}).encode()
        return Response(200, "application/json", body_out)

    def _page(self, index: int) -> Response:
        done = sum(1 for item in self.items if self.answered(item))
        head = f"<p>{done}/{len(self.items)} stills fully answered.</p>"
        if index < 0:
            return _html(head + "<h1>Every still is answered.</h1>")
        item = self.items[index]
        rows = "".join(
            f'<li data-key="{q.key}">{escape(q.text)} '
            f"<b>{escape(self.answers.get((item.event_id, q.key), '·'))}</b></li>"
            for q in item.questions
        )
        body = (
            f"{head}<h1>{index + 1}. {escape(item.event_id)}</h1>"
            f'<img src="/still/{index}" alt="still"><ol>{rows}</ol>'
            "<p>Keys: <b>y</b> yes, <b>n</b> no, <b>u</b> unclear answer the selected question "
            "(the first unanswered); <b>1-4</b> select a question to change it; <b>[</b> and "
            "<b>]</b> move between stills.</p>"
            f"<script>{_SCRIPT % {'index': index, 'last': len(self.items) - 1}}</script>"
        )
        return _html(body)


_SCRIPT = """
const items = [...document.querySelectorAll('li')];
let selected = items.findIndex(li => li.querySelector('b').textContent === '·');
if (selected < 0) selected = 0;
items[selected].style.outline = '2px solid #36c';
document.addEventListener('keydown', async (e) => {
  if (e.key === '[' && %(index)d > 0) location.href = '/item/' + (%(index)d - 1);
  if (e.key === ']' && %(index)d < %(last)d) location.href = '/item/' + (%(index)d + 1);
  if ('1234'.includes(e.key) && items[+e.key - 1]) {
    items[selected].style.outline = ''; selected = +e.key - 1;
    items[selected].style.outline = '2px solid #36c';
  }
  if (!'ynu'.includes(e.key) || e.key === '') return;
  const r = await fetch('/answer', {method: 'POST', body: JSON.stringify(
    {index: %(index)d, question: items[selected].dataset.key, answer: e.key})});
  const next = (await r.json()).next;
  const open = items.some((li, i) => i !== selected && li.querySelector('b').textContent === '·');
  location.href = open ? '/item/%(index)d' : (next < 0 ? '/' : '/item/' + next);
});
"""


def _html(body: str) -> Response:
    page = (
        "<!doctype html><meta charset=utf-8><title>synthbench audit</title>"
        "<style>body{font-family:sans-serif;margin:16px} img{max-width:100%;max-height:70vh}"
        " li{margin:6px 0;font-size:18px}</style>" + body
    )
    return Response(200, "text/html; charset=utf-8", page.encode())


def _not_found() -> Response:
    return Response(404, "text/plain", b"not found")


def serve(app: AuditApp, port: int) -> None:
    """Serve `app` on 127.0.0.1:`port` until interrupted."""

    class Handler(BaseHTTPRequestHandler):
        def _respond(self, response: Response) -> None:
            self.send_response(response.status)
            self.send_header("Content-Type", response.content_type)
            self.send_header("Content-Length", str(len(response.body)))
            self.end_headers()
            self.wfile.write(response.body)

        def do_GET(self) -> None:
            self._respond(app.handle("GET", self.path, b""))

        def do_POST(self) -> None:
            length = int(self.headers.get("Content-Length", "0"))
            self._respond(app.handle("POST", self.path, self.rfile.read(length)))

        def log_message(self, format: str, *args: object) -> None:
            del format, args  # quiet: the command prints its own progress

    with ThreadingHTTPServer(("127.0.0.1", port), Handler) as server:
        server.serve_forever()
