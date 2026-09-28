"""ComfyClient against a fake ComfyUI (httpx.MockTransport)."""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest
from synthbench.generate.comfy.client import ComfyClient, ComfyError, OutputFile

GRAPH = {"1": {"class_type": "SaveImage", "inputs": {}}}


def _client(handler: httpx.MockTransport) -> ComfyClient:
    return ComfyClient("http://comfy", transport=handler)


class FakeComfy:
    def __init__(self, *, history_after: int = 0, status: str = "success") -> None:
        self.history_after = history_after
        self.status = status
        self.history_polls = 0
        self.queued: list[dict[str, object]] = []
        self.uploads: list[str] = []
        self.control: list[tuple[str, object]] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:  # noqa: PLR0911
        path = request.url.path
        if path == "/prompt":
            body = json.loads(request.content)
            self.queued.append(body)
            return httpx.Response(200, json={"prompt_id": "p1", "number": 0, "node_errors": {}})
        if path == "/history/p1":
            self.history_polls += 1
            if self.history_polls <= self.history_after:
                return httpx.Response(200, json={})
            entry = {
                "status": {"status_str": self.status, "completed": True, "messages": [["x", {}]]},
                "outputs": {
                    "9": {"images": [{"filename": "a.png", "subfolder": "s", "type": "output"}]},
                    "12": {
                        "images": [{"filename": "v.mp4", "subfolder": "", "type": "output"}],
                        "animated": [True],
                    },
                },
            }
            return httpx.Response(200, json={"p1": entry})
        if path == "/view":
            return httpx.Response(200, content=f"bytes:{request.url.params['filename']}".encode())
        if path == "/upload/image":
            self.uploads.append(request.headers["content-type"])
            return httpx.Response(200, json={"name": "ref.png", "subfolder": "", "type": "input"})
        if path == "/object_info":
            return httpx.Response(200, json={"SaveImage": {}})
        if path in {"/free", "/interrupt", "/queue"}:
            body = json.loads(request.content) if request.content else None
            self.control.append((path, body))
            return httpx.Response(200)
        return httpx.Response(404)


def _no_sleep(_s: float) -> None:
    return None


class TestComfyClient:
    def test_run_queues_waits_and_downloads_every_output(self) -> None:
        fake = FakeComfy(history_after=2)
        client = _client(httpx.MockTransport(fake))
        blobs = client.run(GRAPH, timeout_s=10, sleep=_no_sleep)
        assert blobs == [b"bytes:a.png", b"bytes:v.mp4"]
        assert fake.queued[0]["prompt"] == GRAPH
        assert fake.history_polls == 3

    def test_outputs_collect_images_and_videos(self) -> None:
        entry = {
            "outputs": {
                "9": {"images": [{"filename": "a.png", "subfolder": "s", "type": "output"}]},
                "3": {"text": ["not a file"]},
            }
        }
        assert ComfyClient("http://c").outputs(entry) == [OutputFile("a.png", "s", "output")]

    def test_a_failed_execution_raises(self) -> None:
        client = _client(httpx.MockTransport(FakeComfy(status="error")))
        with pytest.raises(ComfyError, match="error"):
            client.run(GRAPH, timeout_s=10, sleep=_no_sleep)

    def test_a_rejected_graph_raises_with_the_node_errors(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                400,
                json={
                    "error": {"type": "prompt_outputs_failed_validation"},
                    "node_errors": {"1": {"errors": ["bad"]}},
                },
            )

        with pytest.raises(ComfyError, match="prompt_outputs_failed_validation"):
            _client(httpx.MockTransport(handler)).queue(GRAPH)

    def test_wait_times_out(self) -> None:
        client = _client(httpx.MockTransport(FakeComfy(history_after=10**6)))
        now = [0.0]
        with pytest.raises(TimeoutError, match="p1"):
            client.wait(
                "p1",
                timeout_s=3.0,
                poll_s=1.0,
                sleep=lambda s: now.__setitem__(0, now[0] + s),
                clock=lambda: now[0],
            )

    def test_upload_sends_multipart_and_returns_the_name(self, tmp_path: Path) -> None:
        fake = FakeComfy()
        image = tmp_path / "ref.png"
        image.write_bytes(b"\x89PNG")
        assert _client(httpx.MockTransport(fake)).upload_image(image) == "ref.png"
        assert fake.uploads[0].startswith("multipart/form-data")

    def test_object_info(self) -> None:
        assert _client(httpx.MockTransport(FakeComfy())).object_info() == {"SaveImage": {}}

    def test_a_timed_out_run_interrupts_and_dequeues_its_prompt(self) -> None:
        fake = FakeComfy(history_after=10**6)
        with pytest.raises(TimeoutError, match="p1"):
            _client(httpx.MockTransport(fake)).run(GRAPH, timeout_s=0, sleep=_no_sleep)
        assert fake.control == [("/interrupt", None), ("/queue", {"delete": ["p1"]})]

    def test_free_unloads_models_and_frees_memory(self) -> None:
        fake = FakeComfy()
        _client(httpx.MockTransport(fake)).free()
        assert fake.control == [("/free", {"unload_models": True, "free_memory": True})]
