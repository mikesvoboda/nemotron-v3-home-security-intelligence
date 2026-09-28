"""Minimal ComfyUI HTTP client (spec §3.1): upload, queue, wait, collect outputs."""

from __future__ import annotations

import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

Graph = dict[str, dict[str, Any]]


class ComfyError(RuntimeError):
    """ComfyUI rejected a graph or failed while executing it."""


_FAILURE_EVENTS = ("execution_error", "execution_interrupted")


def _failure_reason(prompt_id: str, messages: Any) -> str:
    """Lead with the failing node and exception: callers keep only a prefix of the text."""
    for event in reversed(messages if isinstance(messages, list) else []):
        if not (isinstance(event, list) and len(event) == 2 and event[0] in _FAILURE_EVENTS):
            continue
        name, data = event
        data = data if isinstance(data, dict) else {}
        where = f"node {data.get('node_id')} ({data.get('node_type')})"
        if name == "execution_interrupted":
            return f"{prompt_id} interrupted at {where}"
        return (
            f"{prompt_id} failed at {where}: "
            f"{data.get('exception_type')}: {data.get('exception_message')}"
        )
    return f"{prompt_id} failed (error): {messages}"


@dataclass(frozen=True)
class OutputFile:
    filename: str
    subfolder: str
    type: str


class ComfyClient:
    def __init__(
        self,
        base_url: str,
        *,
        transport: httpx.BaseTransport | None = None,
        timeout_s: float = 60.0,
    ) -> None:
        self._http = httpx.Client(base_url=base_url, transport=transport, timeout=timeout_s)
        self._client_id = uuid.uuid4().hex

    def close(self) -> None:
        self._http.close()

    def object_info(self) -> dict[str, Any]:
        resp = self._http.get("/object_info")
        resp.raise_for_status()
        info: dict[str, Any] = resp.json()
        return info

    def upload_image(self, path: Path) -> str:
        resp = self._http.post(
            "/upload/image",
            files={"image": (path.name, path.read_bytes(), "image/png")},
            data={"overwrite": "true"},
        )
        resp.raise_for_status()
        return str(resp.json()["name"])

    def queue(self, graph: Graph) -> str:
        resp = self._http.post("/prompt", json={"prompt": graph, "client_id": self._client_id})
        body: dict[str, Any] = resp.json()
        if resp.status_code != 200 or body.get("error") or body.get("node_errors"):
            raise ComfyError(f"graph rejected: {body}")
        return str(body["prompt_id"])

    def wait(
        self,
        prompt_id: str,
        *,
        timeout_s: float,
        poll_s: float = 1.0,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ) -> dict[str, Any]:
        deadline = clock() + timeout_s
        while True:
            resp = self._http.get(f"/history/{prompt_id}")
            resp.raise_for_status()
            entry: dict[str, Any] | None = resp.json().get(prompt_id)
            if entry is not None:
                status = entry.get("status", {})
                if status.get("status_str") == "error":
                    raise ComfyError(_failure_reason(prompt_id, status.get("messages")))
                return entry
            if clock() >= deadline:
                raise TimeoutError(f"{prompt_id} not finished after {timeout_s:.0f}s")
            sleep(poll_s)

    @staticmethod
    def outputs(entry: dict[str, Any]) -> list[OutputFile]:
        found: list[OutputFile] = []
        for node_output in entry.get("outputs", {}).values():
            for value in node_output.values():
                if not isinstance(value, list):
                    continue
                for item in value:
                    if isinstance(item, dict) and "filename" in item:
                        found.append(
                            OutputFile(
                                item["filename"],
                                item.get("subfolder", ""),
                                item.get("type", "output"),
                            )
                        )
        return found

    def download(self, out: OutputFile) -> bytes:
        resp = self._http.get(
            "/view", params={"filename": out.filename, "subfolder": out.subfolder, "type": out.type}
        )
        resp.raise_for_status()
        return bytes(resp.content)

    def run(
        self,
        graph: Graph,
        *,
        timeout_s: float,
        poll_s: float = 1.0,
        sleep: Callable[[float], None] = time.sleep,
    ) -> list[bytes]:
        prompt_id = self.queue(graph)
        try:
            entry = self.wait(prompt_id, timeout_s=timeout_s, poll_s=poll_s, sleep=sleep)
        except TimeoutError:
            # A prompt left on the server would delay, and time out, every later job.
            self._http.post("/interrupt")
            self._http.post("/queue", json={"delete": [prompt_id]})
            raise
        return [self.download(out) for out in self.outputs(entry)]

    def free(self) -> None:
        """Unload every model and free cached memory, so the next group's VRAM is its own."""
        resp = self._http.post("/free", json={"unload_models": True, "free_memory": True})
        resp.raise_for_status()
