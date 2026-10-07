"""The clip audit page (ISS-038 acceptance, method per OD-15): one clip at a time, blind.

`ClipAuditApp.handle(method, path, body, headers)` is the whole application, tested without a
socket; `serve()` puts it behind `http.server` on 127.0.0.1. What the page prints is the
blindness surface, so it is deliberately narrow: the clip's own bytes, the declared
lighting/weather (draw-row fields, carried there precisely so the page never opens a spec),
the five fixed questions, and the auditor's own answers echoed back. The row's scenario,
group and intended motion are DECLARED facts and never rendered - the scene question is a
pick from the whole taxonomy, so the list every item prints says nothing about that item.
"""

from __future__ import annotations

import json
import threading
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from html import escape
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from synthbench.audit.clip_sample import (
    ClipQuestion,
    conditions_question,
    motion_question,
    prop_question,
    scene_choices,
    scene_question,
    threat_question,
)
from synthbench.contract.clip_audit import ClipAuditAnswerRow, ClipAuditDrawRow
from synthbench.taxonomy.model import Taxonomy, load_taxonomy

MARKS = ("y", "n", "u")
SCENE = "scene"
PROP = "prop"


@dataclass(frozen=True)
class ClipAuditItem:
    """One drawn clip: the manifest row (its conditions are shown; its scenario is not) and
    the mp4's bytes, reached through the ready attempt's provenance."""

    row: ClipAuditDrawRow
    clip_path: Path

    @property
    def event_id(self) -> str:
        return self.row.event_id


@dataclass(frozen=True)
class Response:
    status: int
    content_type: str
    body: bytes


def load_answers(log: Path) -> tuple[dict[tuple[str, str], str], dict[str, str]]:
    """Replay the log in order: the latest answer per (event id, question key), and the
    scene pick each event's LATEST prop answer was written under. The second dict exists
    because a prop question belongs to a pick ("Is the knife visible?" is not "Is the
    angle grinder visible?"), but the contract row pins prop answers to a bare y/n/u -
    so the binding is read from the log's order, not from the row. A row for a never-
    picked scene binds to ""; nothing answered under a pick counts under another."""
    answers: dict[tuple[str, str], str] = {}
    prop_bind: dict[str, str] = {}
    if log.exists():
        for line in log.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            key = row["question"]
            value = row.get("pick")
            answers[(row["event_id"], key)] = str(row["answer"] if value is None else value)
            if key == PROP:
                prop_bind[row["event_id"]] = answers.get((row["event_id"], SCENE), "")
    return answers, prop_bind


class ClipAuditApp:
    """The page's routes over a fixed draw and one answer log. Questions come from
    `synthbench.audit.clip_sample`; the taxonomy only supplies the two lists the questions
    point at (scenario ids, prop terms) - never this clip's declared scenario."""

    def __init__(
        self,
        items: Sequence[ClipAuditItem],
        log: Path,
        now: Callable[[], str],
        *,
        port: int,
        tax: Taxonomy | None = None,
    ) -> None:
        self.items = list(items)
        self.log = log
        self.now = now
        self.port = port
        self.tax = tax if tax is not None else load_taxonomy()
        self.answers, self._prop_bind = load_answers(log)
        self._lock = threading.Lock()

    # -- the state each page renders -------------------------------------------------

    def current_scene(self, item: ClipAuditItem) -> str | None:
        return self.answers.get((item.event_id, SCENE))

    def prop_question_for(self, item: ClipAuditItem) -> ClipQuestion | None:
        """The prop question of the auditor's CURRENT pick, None while no pick names props.
        This is why an answered prop can go stale: the question belongs to the pick, not to
        the clip (leaving the scenario makes the old mark inert; returning revives it)."""
        picked = self.current_scene(item)
        if picked is None:
            return None
        scenario = next((s for s in self.tax.scenarios if s.id == picked), None)
        return None if scenario is None else prop_question(scenario)

    def questions(self, item: ClipAuditItem) -> tuple[ClipQuestion, ...]:
        """The page's question order; the prop row exists only behind a prop-declaring pick.
        The scene question carries the whole taxonomy as its choices here - the static bank
        ships it choiceless precisely because the list belongs to the page, not to a clip."""
        scene = scene_question()
        out = [
            motion_question(),
            ClipQuestion(key=scene.key, text=scene.text, choices=_scene_ids(self.tax)),
        ]
        prop = self.prop_question_for(item)
        if prop is not None:
            out.append(prop)
        return (
            *out,
            conditions_question(item.row.lighting, item.row.weather),
            threat_question(),
        )

    def _prop_is_current(self, item: ClipAuditItem) -> bool:
        """Whether this event's latest prop answer was written under the scene pick that
        still stands (True when no prop answer exists: nothing to be stale). The log's
        replay set the binding, which only a prop answer moves - so leaving the scenario
        makes the old mark inert, and the same pick returning revives it."""
        bind = self._prop_bind.get(item.event_id)
        return bind is None or bind == self.current_scene(item)

    def answered(self, item: ClipAuditItem) -> bool:
        """Once a prop has been ANSWERED of a clip, that answer must be current for the
        clip to be complete - even behind a pick that asks no prop. A move from a
        prop-declaring pick to a propless one is a changed mind about the scene, and the
        log still holds a prop verdict belonging to the scene the auditor no longer
        believes; only a prop question never asked leaves the four always-asked keys in
        charge."""
        if any((item.event_id, q.key) not in self.answers for q in self.questions(item)):
            return False
        return self._prop_is_current(item)

    def next_open(self) -> int:
        """The first item with an unanswered question, or -1 when every clip is answered."""
        return next((i for i, item in enumerate(self.items) if not self.answered(item)), -1)

    # -- routing --------------------------------------------------------------------

    def handle(
        self, method: str, path: str, body: bytes, headers: Mapping[str, str] | None = None
    ) -> Response:
        """One request. `headers` matter only to `POST /answer`, which the page's own origin
        alone may send: without them it is refused."""
        if method == "GET" and path in ("", "/"):
            return self._page(self.next_open())
        if method == "GET" and path.startswith("/item/"):
            index = self._index(path.removeprefix("/item/"))
            return self._page(index) if index is not None else _not_found()
        if method == "GET" and path.startswith("/clip/"):
            return self._clip(path.removeprefix("/clip/"))
        if method == "POST" and path == "/answer":
            return self._answer(body, headers or {})
        return _not_found()

    def _clip(self, text: str) -> Response:
        """The drawn clip's bytes. Checked only for readability by name - `clip check`
        verifies bytes against sha256s - and a vanished file is a broken manifest, not a
        crash, so it is the same 404 an out-of-range index gets."""
        index = self._index(text)
        if index is None:
            return _not_found()
        try:
            return Response(200, "video/mp4", self.items[index].clip_path.read_bytes())
        except OSError:
            return _not_found()

    def _index(self, text: str) -> int | None:
        return int(text) if text.isdigit() and int(text) < len(self.items) else None

    def _same_origin(self, headers: Mapping[str, str]) -> bool:
        named = {key.lower(): value for key, value in headers.items()}
        hosts = {f"127.0.0.1:{self.port}", f"localhost:{self.port}"}
        origin = named.get("origin")
        return named.get("host") in hosts and (
            origin is None or origin in {f"http://{host}" for host in hosts}
        )

    def _answer(self, body: bytes, headers: Mapping[str, str]) -> Response:
        if not self._same_origin(headers):
            return Response(403, "text/plain", b"answers come only from this page")
        try:
            request: dict[str, Any] = json.loads(body)
            item = self.items[int(request["index"])]
        except ValueError, KeyError, IndexError, TypeError:
            return Response(400, "text/plain", b"expected {index, question, answer|pick}")
        key = str(request.get("question"))
        problem = self._refuse(item, key, request)
        if problem is not None:
            return Response(400, "text/plain", problem.encode())
        row = ClipAuditAnswerRow(
            event_id=item.event_id,
            question=key,  # type: ignore[arg-type]  # _refuse validated this shape above
            answer=request.get("answer"),  # type: ignore[arg-type]
            pick=request.get("pick"),
            time=self.now(),
        )
        with self._lock:
            self.log.parent.mkdir(parents=True, exist_ok=True)
            with self.log.open("a", encoding="utf-8") as out:
                # json.dumps of the validated model dump: pydantic's own serializer cannot
                # sort keys, and the stills log's canonical sorted-key shape is what the
                # report reads line by line.
                out.write(json.dumps(row.model_dump(exclude_none=True), sort_keys=True) + "\n")
            # The in-memory replay of load_answers, one row at a time: only a prop answer
            # stamps the binding, with the scene pick standing at that moment; moving the
            # scene pick on leaves the stamp, which is exactly why a moved-on mark reads
            # stale and the same pick coming back revives it.
            self.answers[(item.event_id, key)] = str(row.answer if row.pick is None else row.pick)
            if key == PROP:
                self._prop_bind[item.event_id] = self.answers.get((item.event_id, SCENE), "")
        return Response(200, "application/json", json.dumps({"next": self.next_open()}).encode())

    def _refuse(self, item: ClipAuditItem, key: str, request: dict[str, Any]) -> str | None:
        """Why this request is not an answer for this clip, or None to accept it. The
        contract row checks the shape and the closed choice lists; these two rules are the
        page's own: the scene pick must be a real scenario, and the prop question belongs to
        the pick currently standing, so an un-asked prop is not an answer."""
        askable = {question.key for question in _static_questions(self.tax)}
        if key not in askable:
            return f"no question {key!r} on this page"
        if key == SCENE:
            picked = request.get("pick")
            if not any(s.id == picked for s in self.tax.scenarios):
                return "the scene pick must be a scenario id"
        elif key == PROP:
            if self.prop_question_for(item) is None:
                return "prop is asked only behind a scenario pick that names a prop"
        try:
            ClipAuditAnswerRow.model_validate(
                {
                    "event_id": item.event_id,
                    "question": key,
                    "answer": request.get("answer"),
                    "pick": request.get("pick"),
                    "time": self.now(),
                }
            )
        except ValidationError as error:
            return str(error.errors()[0]["msg"])
        return None

    # -- the two pages ---------------------------------------------------------------

    def _page(self, index: int) -> Response:
        done = sum(1 for item in self.items if self.answered(item))
        head = f"<p>{done}/{len(self.items)} clips fully answered.</p>"
        if index < 0:
            return _html(head + "<h1>Every clip is answered.</h1>")
        item = self.items[index]
        rows = "".join(self._row_html(item, question) for question in self.questions(item))
        body = (
            f"{head}<h1>{index + 1}. {escape(item.event_id)}</h1>"
            f'<video src="/clip/{index}" controls autoplay muted loop playsinline'
            "></video>"
            f"<ol>{rows}</ol>"
            "<p>Pick an answer; it is saved at once, and the page returns here while a"
            " question is open. The scenario list is the whole taxonomy and the same on"
            " every clip - pick what the clip shows, not what a label says.</p>"
            f"<script>{_SCRIPT % {'index': index, 'last': len(self.items) - 1}}</script>"
        )
        return _html(body)

    def _row_html(self, item: ClipAuditItem, question: ClipQuestion) -> str:
        value = self.answers.get((item.event_id, question.key))
        if question.key == PROP and not self._prop_is_current(item):
            # An answer written under a moved-on pick: the page shows what answered() counts,
            # so no stale mark sits on a question that is not being asked.
            value = None
        mark = escape(value) if value is not None else "&middot;"
        control = (
            _buttons(question.key, MARKS)
            if not question.choices
            else _select(question.key, question.choices)
        )
        return (
            f'<li data-key="{escape(question.key)}">{escape(question.text)} '
            f"<b>{mark}</b>{control}</li>"
        )


def _scene_ids(tax: Taxonomy) -> tuple[str, ...]:
    """The scene pick's choices: the whole taxonomy, id order, identical on every clip
    (`scene_choices` is that list; only its ids reach the page)."""
    return tuple(s.id for s in scene_choices(tax))


def _static_questions(tax: Taxonomy) -> tuple[ClipQuestion, ...]:
    """Every question key the page knows (the scene list comes from the taxonomy, and the
    prop question's text is the auditor's pick's, so only the keys are static here)."""
    scene = scene_question()
    return (
        motion_question(),
        ClipQuestion(key=scene.key, text=scene.text, choices=_scene_ids(tax)),
        ClipQuestion(key="prop", text=""),
        ClipQuestion(key="conditions", text=""),
        threat_question(),
    )  # fmt: skip


def _select(key: str, choices: Sequence[str]) -> str:
    """One pick control - and never a per-clip preselection: a `selected` attribute would
    have to know this clip's truth."""
    options = "".join(
        f'<option value="{escape(choice)}">{escape(choice)}</option>' for choice in choices
    )
    return (
        f'<select name="{escape(key)}"><option value="">&mdash;</option>{options}</select>'
        f'<button data-shape="pick" data-key="{escape(key)}">answer</button>'
    )


def _buttons(key: str, marks: Sequence[str]) -> str:
    return "".join(
        f'<button data-shape="answer" data-key="{escape(key)}" data-mark="{mark}">{mark}</button>'
        for mark in marks
    )


_SCRIPT = """
document.querySelectorAll('button').forEach((b) => b.addEventListener('click', async () => {
  const key = b.dataset.key;
  const body = {index: %(index)d, question: key};
  if (b.dataset.shape === 'answer') body.answer = b.dataset.mark;
  else body.pick = document.querySelector(`select[name='${key}']`).value;
  const r = await fetch('/answer', {method: 'POST', body: JSON.stringify(body)});
  if (!r.ok) { document.title = await r.text(); return; }
  const next = (await r.json()).next;
  const open = [...document.querySelectorAll('li')].some(
    (li) => li.querySelector('b').textContent === '\\u00b7');
  location.href = open ? '/item/%(index)d' : (next < 0 ? '/' : '/item/' + next);
}));
"""


def _html(body: str) -> Response:
    page = (
        "<!doctype html><meta charset=utf-8><title>synthbench clip audit</title>"
        "<style>body{font-family:sans-serif;margin:16px} video{max-width:100%;max-height:60vh;"
        "background:#000} li{margin:10px 0;font-size:18px} button{margin-left:6px}</style>" + body
    )
    return Response(200, "text/html; charset=utf-8", page.encode())


def _not_found() -> Response:
    return Response(404, "text/plain", b"not found")


def serve(app: ClipAuditApp) -> None:
    """Serve `app` on 127.0.0.1 at its port until interrupted."""

    class Handler(BaseHTTPRequestHandler):
        def _respond(self, response: Response) -> None:
            self.send_response(response.status)
            self.send_header("Content-Type", response.content_type)
            self.send_header("Content-Length", str(len(response.body)))
            self.end_headers()
            self.wfile.write(response.body)

        def do_GET(self) -> None:
            self._respond(app.handle("GET", self.path, b"", dict(self.headers.items())))

        def do_POST(self) -> None:
            length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(length)
            self._respond(app.handle("POST", self.path, body, dict(self.headers.items())))

        def log_message(self, format: str, *args: object) -> None:
            del format, args  # quiet: the command prints its own progress

    with ThreadingHTTPServer(("127.0.0.1", app.port), Handler) as server:
        server.serve_forever()
