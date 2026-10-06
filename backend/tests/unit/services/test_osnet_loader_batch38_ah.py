# TARGET-MODULE: backend.services.osnet_loader
"""Battery AH - campaign #32 backend/services/osnet_loader.py (221 survivors).

The shipped suite drove load/extract with MagicMocks, and a MagicMock
ABSORBS mutants (transform(x).unsqueeze(0) rides whatever the mutant
passes). This battery replaces every seam with a RECORDING fake:

  * FakeTensor logs every unsqueeze(dim)/to(device) - the batch dim and
    the device IDENTITY (a sentinel object) become observable.
  * FakeTransform pins the ARGUMENT by identity and mode - a convert flip
    handing the transform a non-RGB image, or a dropped argument, bite.
  * FakeModel records model(x), .parameters().device, cuda()/eval()
    counts; FakeFeats hands back a REAL ndarray so the L2 arithmetic
    (norm > 0 vs >= 0 vs > 1, / vs *) is pinned on REAL numbers: a zero
    vector must stay exactly zeros (>= 0 divides by zero -> NaN), a
    0.5-norm vector must end at norm 1.0 (> 1 would skip it).
  * FakeTorch/FakeTransformsNS record torch.load / jit.load / stack /
    Compose WHOLE - NEM-4519 weights_only=True, map_location cpu, the
    Resize((256,128))/Normalize literal list, and every drop-kwarg family
    die on the recorded call tuple (M30 capture #7: a DELETED kwarg is a
    MISSING key, invisible to .get-equality).
  * backend.core.security is swapped in sys.modules: validate_model_path
    recorded as (args, kwargs) whole - must_exist=False -> omitted is a
    DISTINCT recorded shape.
  * build_model/load_state_dict pinned with exact kwargs (strict=False).
  * Log records captured through a real Handler on a swapped logger:
    whole-message equality, LEVEL, record.exc_info (True renders a REAL
    tuple in the LogRecord; False/None stay falsy VERBATIM - capture #10)
    and the flattened extra (LogRecord merges extra= keys into record
    attributes: record.model_path).
  * The weights resolver is driven with real tmp_path directory shapes so
    the model.pth / osnet-named / sorted-glob priorities each OBSERVE the
    right file being torch.load'ed.
  * The critical-prefix guard is driven per-prefix (all six), with a
    7-missing case pinning critical_missing[:5] + the true total, and a
    4-missing pair pinning the non-critical [:3] slices.

Honesty ledger (registered EQUIVALENTS - value-identical by construction,
each re-proven by the disposition sweep):
  1. _osnet_zoo_row m4 (parents[2] -> parents[3]): a SWEEP-WORLD
     equivalence, disclosed exactly as such - the mutant def lives at
     mutants/backend/services/, so its parents[2] is mutants/models.yml
     and parents[3] is workspace/models.yml, and the two files are
     BYTE-IDENTICAL (md5 d2d144ab..., proven this session), so the yaml
     read returns the same document and the whole row - hence the belt -
     is unchanged. (In the REAL tree parents[3] is
     /agents/agent-veranda3/models.yml, which does not exist - absent
     from the sweep world only because the mutant copy sits one
     directory deeper; no battery can distinguish two byte-identical
     files by value.)
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import sys
import threading
import types
from unittest.mock import patch

import numpy as np
import PIL.Image
import pytest

# ------------------------------------------------------------------ fakes


def run(coro):
    return asyncio.run(coro)


class Boom(Exception):
    pass


class PathSecErr(Exception):
    pass


class CallLog:
    def __init__(self) -> None:
        self.entries: list[object] = []


class FakeTensor:
    def __init__(self, log: CallLog, tag: str = "t") -> None:
        self.log = log
        self.tag = tag

    def unsqueeze(self, dim):
        self.log.entries.append(("unsqueeze", self.tag, dim))
        return self

    def to(self, device):
        self.log.entries.append(("to", self.tag, device))
        return self


class FakeFeats:
    def __init__(self, arr) -> None:
        self.arr = arr

    def squeeze(self):
        return self

    def cpu(self):
        return self

    def numpy(self):
        return self.arr


class _Param:
    def __init__(self, device) -> None:
        self.device = device


class FakeModel:
    def __init__(self, arr, device="FAKE-DEVICE") -> None:
        self.arr = arr
        self.device = device
        self.calls: list[object] = []
        self.eval_count = 0
        self.cuda_count = 0
        self.return_tuple = False

    def parameters(self):
        yield _Param(self.device)

    def __call__(self, x):
        self.calls.append(x)
        feats = FakeFeats(self.arr)
        return (feats,) if self.return_tuple else feats

    def cuda(self):
        self.cuda_count += 1
        return self

    def eval(self):
        self.eval_count += 1
        return self


class FakeTransform:
    def __init__(self) -> None:
        self.calls: list[object] = []
        self.made: list[FakeTensor] = []
        self.log = CallLog()

    def __call__(self, img):
        self.calls.append(img)
        t = FakeTensor(self.log, tag="x")
        self.made.append(t)
        return t


class BoomTransform(FakeTransform):
    def __call__(self, img):
        raise Boom("inner")


class FakeJitModel:
    def __init__(self) -> None:
        self.eval_count = 0
        self.cuda_count = 0

    def eval(self):
        self.eval_count += 1
        return self

    def cuda(self):
        self.cuda_count += 1
        return self


class FakeJit:
    def __init__(self, owner) -> None:
        self.owner = owner

    def load(self, *a, **kw):
        self.owner.jit_rec.entries.append((a, kw))
        if self.owner.jit_result is None:
            raise RuntimeError("jit refuses")
        return self.owner.jit_result


class FakeTorch:
    def __init__(self, cuda_available: bool = False) -> None:
        self.load_rec = CallLog()
        self.stack_rec = CallLog()
        self.stack_log = CallLog()
        self.jit_rec = CallLog()
        self.cuda_flag = cuda_available
        self.im_count = 0
        self.load_result: object = {}
        self.jit_result: object = FakeJitModel()
        self.jit = FakeJit(self)
        self.stack_made: list = []

    class _Cuda:
        def __init__(self, owner) -> None:
            self.owner = owner

        def is_available(self):
            return self.owner.cuda_flag

    @property
    def cuda(self):
        return FakeTorch._Cuda(self)

    def inference_mode(self):
        self.im_count += 1
        return contextlib.nullcontext()

    def load(self, *a, **kw):
        self.load_rec.entries.append((a, kw))
        return self.load_result

    def stack(self, *a, **kw):
        self.stack_rec.entries.append((a, kw))
        t = FakeTensor(self.stack_log, tag="batch")
        self.stack_made.append(t)
        return t


class FakeTransformsNS:
    def __init__(self) -> None:
        self.compose_rec = CallLog()

    class Op:
        def __init__(self, name, args, kw) -> None:
            self.name, self.args, self.kw = name, args, kw

        def __eq__(self, other):
            return isinstance(other, FakeTransformsNS.Op) and (self.name, self.args, self.kw) == (
                other.name,
                other.args,
                other.kw,
            )

        def __hash__(self):
            return hash((self.name, str(self.args), str(self.kw)))

        def __repr__(self):
            return f"{self.name}{self.args}{self.kw}"

    def Resize(self, *a, **kw):
        return self.Op("Resize", a, kw)

    def ToTensor(self, *a, **kw):
        return self.Op("ToTensor", a, kw)

    def Normalize(self, *a, **kw):
        return self.Op("Normalize", a, kw)

    def Compose(self, *a, **kw):
        self.compose_rec.entries.append((a, kw))
        return ("COMPOSE", a, kw)


class SecurityStub(types.ModuleType):
    def __init__(self, exc: Exception | None = None) -> None:
        super().__init__("backend.core.security")
        self.PathSecurityError = PathSecErr
        self.calls: list = []
        self._exc = exc

    def validate_model_path(self, *a, **kw):
        self.calls.append((a, kw))
        if self._exc is not None:
            raise self._exc
        return a[0]


class LoadResult:
    def __init__(self, missing=(), unexpected=()) -> None:
        self.missing_keys = list(missing)
        self.unexpected_keys = list(unexpected)


class NoAttrs:
    """A load_result object with NO missing_keys/unexpected_keys attrs."""


class FakeStateModel:
    def __init__(self, result, raise_exc: Exception | None = None) -> None:
        self.result = result
        self.raise_exc = raise_exc
        self.load_sd_calls: list = []
        self.eval_count = 0
        self.cuda_count = 0

    def load_state_dict(self, *a, **kw):
        self.load_sd_calls.append((a, kw))
        if self.raise_exc is not None:
            raise self.raise_exc
        return self.result

    def eval(self):
        self.eval_count += 1
        return self

    def cuda(self):
        self.cuda_count += 1
        return self

    def parameters(self):
        yield _Param("load-device")


class BuildModelRecorder:
    def __init__(self, model) -> None:
        self.model = model
        self.calls: list = []

    def __call__(self, *a, **kw):
        self.calls.append((a, kw))
        return self.model


class ModuleSwaps(contextlib.AbstractContextManager):
    """Swap torch / torchvision(.transforms) / backend.core.security /
    torchreid spellings; tensorboard sys.modules hygiene in and out."""

    def __init__(self, torch_obj, transforms_obj, security_obj, builder=None) -> None:
        self.torch = torch_obj
        self.transforms = transforms_obj
        self.security = security_obj
        self.builder = builder

    def __enter__(self):
        tv = types.ModuleType("torchvision")
        tv.transforms = self.transforms
        patches = {
            "torch": self.torch,
            "torchvision": tv,
            "backend.core.security": self.security,
        }
        if self.builder is not None:
            m1 = types.ModuleType("torchreid.reid.models")
            m1.build_model = self.builder
            m2 = types.ModuleType("torchreid.models")
            m2.build_model = self.builder
            patches["torchreid.reid.models"] = m1
            patches["torchreid.models"] = m2
        self._stack = []
        p = patch.dict(sys.modules, patches)
        p.start()
        self._stack.append(p)
        # tensorboard hygiene: drop any earlier stub so the stub branch
        # runs again inside this world; restore on exit.
        self._tb = sys.modules.pop("torch.utils.tensorboard", None)
        return self

    def __exit__(self, *exc):
        for p in self._stack:
            p.stop()
        if self._tb is not None:
            sys.modules["torch.utils.tensorboard"] = self._tb
        else:
            sys.modules.pop("torch.utils.tensorboard", None)
        return False


class LoadWorld:
    """Everything load_osnet_model touches, wired + recorded."""

    def __init__(
        self,
        *,
        state_dict=None,
        load_result=None,
        cuda=False,
        torchreid=True,
        security_exc=None,
        sd_raise=None,
    ) -> None:
        self.torch = FakeTorch(cuda_available=cuda)
        self.transforms = FakeTransformsNS()
        self.security = SecurityStub(exc=security_exc)
        self.state_dict = {"conv1.w": 1} if state_dict is None else state_dict
        self.torch.load_result = self.state_dict
        self.load_result = load_result if load_result is not None else LoadResult()
        self.model = FakeStateModel(self.load_result, raise_exc=sd_raise)
        self.builder = BuildModelRecorder(self.model)
        self.torchreid = torchreid
        self.swaps = ModuleSwaps(self.torch, self.transforms, self.security, self.builder)

    def __enter__(self):
        self.swaps.__enter__()
        if not self.torchreid:
            # None entries: importing either spelling raises ImportError
            sys.modules["torchreid.reid.models"] = None
            sys.modules["torchreid.models"] = None
        return self

    def __exit__(self, *exc):
        self.swaps.__exit__(*exc)
        return False


class LogRec:
    __slots__ = ("exc_info", "levelno", "model_path", "msg")

    def __init__(self, level, msg, exc_info, model_path) -> None:
        self.levelno = level
        self.msg = msg
        self.exc_info = exc_info
        self.model_path = model_path


@contextlib.contextmanager
def caplogger():
    """Swap a fresh real logger into the module; yield captured REAL
    LogRecords (rendered message, exc_info VERBATIM as the LogRecord
    stored it, the flattened extra's model_path attribute)."""
    import backend.services.osnet_loader as m

    recs: list[LogRec] = []

    class H(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            recs.append(
                LogRec(
                    record.levelno,
                    record.getMessage(),
                    record.__dict__.get("exc_info", None),
                    record.__dict__.get("model_path", None),
                )
            )

    lg = logging.getLogger("battery_ah_probe")
    lg.handlers.clear()
    lg.addHandler(H())
    lg.setLevel(logging.DEBUG)
    lg.propagate = False
    old = m.logger
    m.logger = lg
    try:
        yield recs
    finally:
        m.logger = old
        lg.handlers.clear()


def _mk_dict(model=None, transform=None, model_id="osnet-ain-x1-0@f@abc"):
    return {
        "model": model if model is not None else FakeModel(np.ones(512)),
        "transform": transform if transform is not None else FakeTransform(),
        "model_id": model_id,
        "embedding_dim": 512,
    }


def _img(mode="RGB", size=(100, 200)):
    return PIL.Image.new(mode, size)


def _vec(scale=1.0, dim=512):
    return np.ones(dim, dtype=np.float64) * (scale / np.sqrt(dim))


# The b30-sweep harness calls test functions with NO pytest fixtures, so
# every tmp_path test takes it as an OPTIONAL arg and self-provisions a
# temp directory (removed at interpreter exit).
import atexit  # noqa: E402
import shutil  # noqa: E402
import tempfile  # noqa: E402
from pathlib import Path  # noqa: E402

_TMPDIRS: list = []


def _tmpdir(p):
    if p is not None:
        return p
    d = Path(tempfile.mkdtemp(prefix="battery_ah_"))
    _TMPDIRS.append(d)
    return d


@atexit.register
def _cleanup_tmpdirs():
    for d in _TMPDIRS:
        shutil.rmtree(d, ignore_errors=True)


# --------------------------------------------------------- pure functions


def test_osnet_model_id_grammar_from_real_row():
    """Belt recomputed INDEPENDENTLY from the real models.yml row: the
    role@stem@sha grammar, the 12-char sha prefix, no missing field."""
    import backend.services.osnet_loader as m

    got = m.osnet_model_id()
    assert got.startswith("osnet-ain-x1-0@")
    parts = got.split("@")
    assert len(parts) == 3 and parts[0] == "osnet-ain-x1-0"  # role@stem@sha
    _, stem, sha12 = parts
    from pathlib import Path

    import yaml

    yml = Path(m.__file__).resolve().parents[2] / "models.yml"
    row = next(
        e for e in yaml.safe_load(yml.read_text())["models"] if e.get("name") == "osnet-ain-x1-0"
    )
    expect_stem = Path(str(row.get("runtime_file") or "osnet_ain_x1_0_msmt17.pth")).stem
    sha = str(row.get("sha256") or "")
    assert sha and len(sha) == 64  # a real pin exists: the @sha arm runs
    assert stem == expect_stem
    assert sha12 == sha[:12]  # the [:12] slice pinned ([:8]/[:16] twins die)
    assert len(sha12) == 12


def test_osnet_model_id_row_polarities():
    """The row.get()/fallback/default-expression arms driven by PATCHED
    zoo rows the real models.yml can never express: a row whose
    runtime_file DIFFERS from the fallback (kills or->and, get(None),
    get('XXruntime_fileXX'), get('RUNTIME_FILE')); a row WITHOUT
    runtime_file (kills the XX/UPPER fallback-default twins and the
    sha-or-'XXXX'/if-sha-or-True twins which only differ when sha is
    falsy)."""
    import backend.services.osnet_loader as m

    # row WITHOUT the keys at all: the fallback stem, NO @sha field
    with patch.object(m, "_osnet_zoo_row", lambda: {}):
        assert m.osnet_model_id() == "osnet-ain-x1-0@osnet_ain_x1_0_msmt17"
    # row WITH a different runtime_file and no sha
    with patch.object(m, "_osnet_zoo_row", lambda: {"runtime_file": "custom_r.pth"}):
        assert m.osnet_model_id() == "osnet-ain-x1-0@custom_r"
    # full custom row: grammar with the custom file + 12-char sha
    with patch.object(m, "_osnet_zoo_row", lambda: {"runtime_file": "c2.pth", "sha256": "c" * 64}):
        assert m.osnet_model_id() == "osnet-ain-x1-0@c2@" + "c" * 12
    # falsy runtime_file falls back to the default name
    with patch.object(m, "_osnet_zoo_row", lambda: {"runtime_file": "", "sha256": "d" * 64}):
        assert m.osnet_model_id() == "osnet-ain-x1-0@osnet_ain_x1_0_msmt17@" + "d" * 12


def test_model_id_belt_grammar():
    from pathlib import Path

    import backend.services.osnet_loader as m

    assert m._model_id("role", Path("/x/osnet_ain_x1_0_msmt17.pth"), "a" * 64) == (
        f"role@osnet_ain_x1_0_msmt17@{'a' * 12}"
    )
    assert m._model_id("role", Path("/x/w.pth"), None) == "role@w"
    assert m._model_id("role", Path("/x/w.pth"), "") == "role@w"  # falsy pin


def test_sha256_reads_1mb_chunks_and_digests(tmp_path=None):
    tmp_path = _tmpdir(tmp_path)
    """Three reads of EXACTLY 1 MiB over a 2 MiB file (the last empty -
    chunk-size twins: 2<<20 gives two reads, 1<<21 wrong sizes) plus the
    correct digest."""
    import hashlib

    import backend.services.osnet_loader as m

    data = bytes(range(256)) * 8192  # exactly 2 MiB
    f = tmp_path / "w.pth"
    f.write_bytes(data)
    reads: list = []

    class RecFile:
        def __init__(self, fh) -> None:
            self.fh = fh

        def read(self, n):
            reads.append(n)
            return self.fh.read(n)

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            self.fh.close()
            return False

    class RecPath:
        def __init__(self, p) -> None:
            self.p = p

        def open(self, mode):
            return RecFile(self.p.open(mode))

    assert m._sha256(RecPath(f)) == hashlib.sha256(data).hexdigest()
    assert reads == [1 << 20, 1 << 20, 1 << 20]


def test_enforce_dim_identity_flatten_and_loud_refusal():
    import backend.services.osnet_loader as m

    v = _vec()
    assert m._enforce_embedding_dim(v) is v  # 1-D passes by IDENTITY
    got = m._enforce_embedding_dim(np.zeros((1, 512)))
    assert got.shape == (512,)  # the flatten branch ran (and-False raises)
    with caplogger() as recs:
        with pytest.raises(RuntimeError) as ei:
            m._enforce_embedding_dim(_vec(dim=256))
    msg = str(ei.value)
    assert msg.startswith("OSNet produced a 256-dim feature vector, expected 512")
    errs = [r.msg for r in recs if r.levelno == logging.ERROR]
    assert errs == [msg]  # the loud refusal logs its own message, ERROR


def test_tensorboard_stub_branches():
    import backend.services.osnet_loader as m

    calls: list = []
    outcome = {"mod": None}

    def import_module(name):
        calls.append(name)
        if outcome["mod"] is not None:
            return outcome["mod"]
        raise ModuleNotFoundError("no tensorboard")

    fake_importlib = types.SimpleNamespace(import_module=import_module)
    with caplogger() as recs, patch.object(m, "importlib", fake_importlib):
        sys.modules.pop("torch.utils.tensorboard", None)
        m._ensure_tensorboard_importable()
        stub = sys.modules.pop("torch.utils.tensorboard")
        assert stub.__name__ == "torch.utils.tensorboard"
        w = stub.SummaryWriter("x", y=1)
        assert w.add_scalar(1) is None and w.flush() is None and w.close() is None
        assert calls == ["torch.utils.tensorboard"]
        dbg = [r.msg for r in recs if r.levelno == logging.DEBUG]
        assert dbg == [
            "torch.utils.tensorboard not importable (no tensorboard); stubbing",
            "Registered inert torch.utils.tensorboard stub for torchreid",
        ]

        # real-importable: returns AFTER the import, registers nothing
        outcome["mod"] = types.ModuleType("torch.utils.tensorboard")
        m._ensure_tensorboard_importable()
        assert sys.modules.get("torch.utils.tensorboard") is None
        assert calls == ["torch.utils.tensorboard"] * 2
        assert len([r for r in recs if r.levelno == logging.DEBUG]) == 2

        # already registered: returns WITHOUT any import attempt
        sys.modules["torch.utils.tensorboard"] = outcome["mod"]
        m._ensure_tensorboard_importable()
        assert calls == ["torch.utils.tensorboard"] * 2
        sys.modules.pop("torch.utils.tensorboard")


def test_import_build_model_layouts():
    import backend.services.osnet_loader as m

    sentinel = object()

    # nested layout wins; the flat spelling is never tried
    calls: list = []

    def imp_nested_ok(name):
        calls.append(name)
        if name == "torchreid.reid.models":
            return types.SimpleNamespace(build_model=sentinel)
        raise AssertionError("second spelling must not run")

    with patch.object(m, "importlib", types.SimpleNamespace(import_module=imp_nested_ok)):
        assert m._import_build_model() is sentinel
    assert calls == ["torchreid.reid.models"]

    # nested import fails -> flat spelling used
    def imp_flat_only(name):
        calls.append(name)
        if name == "torchreid.models":
            return types.SimpleNamespace(build_model=sentinel)
        raise ImportError("no nested")

    calls.clear()
    with patch.object(m, "importlib", types.SimpleNamespace(import_module=imp_flat_only)):
        assert m._import_build_model() is sentinel
    assert calls == ["torchreid.reid.models", "torchreid.models"]

    # module WITHOUT build_model: the getattr default keeps the probe loop
    # going and the final ImportError raises (a 2-arg getattr would leak an
    # AttributeError out of the probe instead)
    def imp_no_attr(name):
        calls.append(name)
        return types.SimpleNamespace()

    calls.clear()
    with patch.object(m, "importlib", types.SimpleNamespace(import_module=imp_no_attr)):
        with pytest.raises(ImportError) as ei:
            m._import_build_model()
    assert str(ei.value) == "torchreid build_model is not importable"
    assert calls == ["torchreid.reid.models", "torchreid.models"]


def test_get_reid_handle_membership():
    import backend.services.model_zoo as mz
    import backend.services.osnet_loader as m

    handle = {"model": object()}

    class Mgr:
        def __init__(self, loaded) -> None:
            self._loaded_models = loaded

    def swap(loaded):
        return patch.object(mz, "get_model_manager", lambda: Mgr(loaded))

    with swap({"osnet-ain-x1-0": handle}):
        assert m.get_reid_handle() is handle
    with swap({}):
        assert m.get_reid_handle() is None
    with swap({"osnet-ain-x1-0": {"nope": 1}}):
        assert m.get_reid_handle() is None
    # NON-dict handles that CONTAIN "model": pristine's isinstance term
    # refuses them; and/or re-associations would RETURN the raw list/str.
    with swap({"osnet-ain-x1-0": ["model"]}):
        assert m.get_reid_handle() is None
    with swap({"osnet-ain-x1-0": "xmodelx"}):
        assert m.get_reid_handle() is None


def test_result_to_dict_shape():
    import backend.services.osnet_loader as m

    e = _vec(2.0)
    r = m.PersonEmbeddingResult(embedding=e, detection_id="d1", confidence=0.8, model_id="b")
    assert r.to_dict() == {
        "embedding": e.tolist(),
        "detection_id": "d1",
        "confidence": 0.8,
        "embedding_dim": 512,
        "model_id": "b",
    }


def test_cosine_similarity_values():
    import backend.services.osnet_loader as m

    R = m.PersonEmbeddingResult
    same = np.zeros(512)
    same[0] = 1.0
    orth = np.zeros(512)
    orth[1] = 1.0
    opp = np.zeros(512)
    opp[0] = -1.0
    big = np.zeros(512)
    big[0] = 3.0  # un-normalized on purpose
    assert R(embedding=same).cosine_similarity(R(embedding=same)) == pytest.approx(1.0)
    assert R(embedding=same).cosine_similarity(R(embedding=orth)) == pytest.approx(0.0)
    assert R(embedding=same).cosine_similarity(R(embedding=opp)) == pytest.approx(-1.0)
    v = R(embedding=big).cosine_similarity(R(embedding=big))
    assert v == pytest.approx(1.0, abs=1e-6)  # the /norm path (*norm gives 9)
    assert v < 1.0  # the +1e-8 epsilon keeps it strictly below 1 (-1e-8: above)


def test_match_threshold_equality_and_sort_order():
    import backend.services.osnet_loader as m

    R = m.PersonEmbeddingResult

    def res(off):
        e = np.zeros(512)
        e[0], e[1] = 1.0, off
        return R(embedding=e / np.linalg.norm(e))

    q = res(0.0)
    exact = res(0.0)
    sim = q.cosine_similarity(exact)
    # equality polarity: threshold EXACTLY sim must match (the > twin drops)
    assert m.match_person_embeddings(q, [exact], threshold=sim) == [(exact, sim)]
    assert m.match_person_embeddings(q, [exact], threshold=sim + 1e-6) == []
    # sort order highest-first (the reverse=True drop flips it)
    near, mid = res(0.5), res(2.0)
    got = [g for g, _s in m.match_person_embeddings(q, [near, mid, exact], threshold=0.1)]
    assert got == [exact, near, mid]


def test_format_context_bands_slice_and_unknown():
    import backend.services.osnet_loader as m

    R = m.PersonEmbeddingResult

    def mk(sid, s):
        return (R(embedding=_vec(), detection_id=sid), s)

    matches = [mk("a", 0.9), mk("", 0.8), mk("c", 0.79), mk("d", 0.95)]
    got = m.format_person_reid_context(matches, "det-7")
    assert got == (
        "Person det-7 re-identification:\n"
        "  - HIGH CONFIDENCE match to a (90%)\n"
        "  - Likely same person as unknown (80%)\n"
        "  - Possible match to c (79%)"
    )
    # ^ the 4th match (d) must NOT appear: the [:3] slice pinned; the
    # empty-string id rides `or "unknown"`; EXACT 0.9/0.8 pin the >= band
    # edges (> twins drop each into the lower band).
    assert m.format_person_reid_context([], "det-7") == (
        "Person det-7: No prior matches found (new individual)"
    )


# ------------------------------------------------- extract_person_embedding


def _extract_ok(image=None, arr=None, ids=None, model=None):
    import backend.services.osnet_loader as m

    arr = _vec(3.0) if arr is None else arr
    model = model if model is not None else FakeModel(arr)
    tf = FakeTransform()
    md = _mk_dict(model, tf)
    img = _img() if image is None else image
    t = FakeTorch()
    with patch.dict(sys.modules, {"torch": t}):
        res = run(m.extract_person_embedding(md, img, detection_id=ids))
    return res, model, tf, t


def test_extract_single_success_pinned():
    res, model, tf, t = _extract_ok(ids="d-1")
    assert res.detection_id == "d-1"
    assert res.confidence == 1.0  # (100, 200) passes both size gates
    assert res.model_id == "osnet-ain-x1-0@f@abc"
    assert len(tf.calls) == 1
    ops = tf.log.entries
    assert ("unsqueeze", "x", 0) in ops  # batch dim 0
    assert ("to", "x", "FAKE-DEVICE") in ops
    assert len(model.calls) == 1
    assert model.calls[0] is tf.made[0]  # model(input_tensor) ARGUMENT pin
    assert t.im_count == 1  # inference_mode entered exactly once
    assert np.linalg.norm(res.embedding) == pytest.approx(1.0)
    assert res.embedding.shape == (512,) and res.embedding[0] > 0


def test_extract_device_identity_pinned():
    sentinel = object()
    arr = _vec(2.0)
    res, _, tf, _ = _extract_ok(arr=arr, model=FakeModel(arr, device=sentinel))
    assert ("to", "x", sentinel) in tf.log.entries  # a None/other swap is NOT it
    assert np.linalg.norm(res.embedding) == pytest.approx(1.0)


def test_extract_tuple_output_unwrapped():
    model = FakeModel(_vec(1.0))
    model.return_tuple = True
    res, _, _, _ = _extract_ok(arr=_vec(1.0), model=model)
    assert res.embedding.shape == (512,)


def test_extract_zero_norm_never_divides():
    # norm > 0 -> >= 0 divides the zero vector by zero -> NaN
    res, _, _, _ = _extract_ok(arr=np.zeros(512))
    assert np.all(res.embedding == 0.0)
    assert np.all(np.isfinite(res.embedding))


def test_extract_subunit_norm_still_normalized():
    # a norm > 1 twin would skip the 0.5-norm vector
    res, _, _, _ = _extract_ok(arr=_vec(0.5))
    assert np.linalg.norm(res.embedding) == pytest.approx(1.0)


def test_extract_normalization_divides():
    # the / -> * twin: a norm-3 input would end at norm 9
    res, _, _, _ = _extract_ok(arr=_vec(3.0))
    assert np.linalg.norm(res.embedding) == pytest.approx(1.0)


def test_extract_model_id_provenance():
    import backend.services.osnet_loader as m

    md = _mk_dict(model_id="belt-string-42")
    t = FakeTorch()
    with patch.dict(sys.modules, {"torch": t}):
        res = run(m.extract_person_embedding(md, _img()))
    assert res.model_id == "belt-string-42"
    md2 = _mk_dict(model_id="x")
    del md2["model_id"]
    with patch.dict(sys.modules, {"torch": t}):
        res2 = run(m.extract_person_embedding(md2, _img()))
    assert res2.model_id is None  # .get with no default: absent -> None


def test_extract_confidence_matrix():
    # pristine: width < 32 or height < 64 -> 0.5; elif width < 64 or
    # height < 128 -> 0.8; else 1.0. The (32,200)/(200,127)/(200,64) rows
    # kill or->and; (32,64)/(64,128) pin the < boundaries; (31,*) the <32.
    cases = [
        ((16, 100), 0.5),
        ((31, 100), 0.5),
        ((31, 200), 0.5),  # width-ONLY small: or->and on the FIRST if
        ((200, 63), 0.5),  # height-ONLY small: same polarity
        ((32, 63), 0.5),
        ((31, 63), 0.5),
        ((32, 64), 0.8),
        ((63, 127), 0.8),
        ((32, 200), 0.8),
        ((200, 127), 0.8),
        ((200, 64), 0.8),
        ((100, 64), 0.8),
        ((64, 200), 1.0),
        ((64, 128), 1.0),
        ((200, 128), 1.0),
    ]
    for (w, h), expect in cases:
        res, _, _, _ = _extract_ok(image=_img(size=(w, h)))
        assert res.confidence == expect, (w, h, res.confidence)


def test_extract_rgb_convert():
    img = _img(mode="L")
    res, _, tf, _ = _extract_ok(image=img)
    assert len(tf.calls) == 1
    got = tf.calls[0]
    assert got.mode == "RGB"  # the L image arrived CONVERTED
    assert got is not img
    rgb = _img()
    res2, _, tf2, _ = _extract_ok(image=rgb)
    assert tf2.calls[0] is rgb  # already-RGB rides by IDENTITY


def test_extract_failure_logs_and_wraps():
    import backend.services.osnet_loader as m

    tf = BoomTransform()
    t = FakeTorch()
    with caplogger() as recs, patch.dict(sys.modules, {"torch": t}):
        with pytest.raises(RuntimeError) as ei:
            run(m.extract_person_embedding(_mk_dict(transform=tf), _img()))
    assert str(ei.value) == "Person embedding extraction failed: inner"
    errs = [r for r in recs if r.levelno == logging.ERROR]
    assert [r.msg for r in errs] == ["Person embedding extraction failed"]
    # exc_info=True -> the LogRecord stores a REAL tuple; the True->False/
    # None/omitted twins store falsy VERBATIM (capture #10).
    assert isinstance(errs[0].exc_info, tuple)
    assert errs[0].exc_info[0] is Boom


# ------------------------------------------- extract_person_embeddings_batch


def _batch_ok(images=None, ids=None, rows=None, model=None):
    import backend.services.osnet_loader as m

    n = len(images) if images else 1
    rows = np.vstack([_vec(3.0)] * n) if rows is None else rows
    model = model if model is not None else FakeModel(rows)
    tf = FakeTransform()
    md = _mk_dict(model, tf)
    imgs = images if images else [_img()]
    t = FakeTorch()
    with patch.dict(sys.modules, {"torch": t}):
        res = run(m.extract_person_embeddings_batch(md, imgs, detection_ids=ids))
    return res, model, tf, t


def test_batch_empty_returns_empty():
    import backend.services.osnet_loader as m

    assert run(m.extract_person_embeddings_batch(_mk_dict(), [])) == []


def test_batch_success_pinned():
    imgs = [_img(size=(100, 200)), _img(size=(16, 50))]
    res, model, tf, t = _batch_ok(images=imgs, ids=["a", "b"])
    assert [r.detection_id for r in res] == ["a", "b"]
    assert [r.confidence for r in res] == [1.0, 0.5]
    assert [r.model_id for r in res] == ["osnet-ain-x1-0@f@abc"] * 2
    assert np.linalg.norm(res[0].embedding) == pytest.approx(1.0)
    assert np.linalg.norm(res[1].embedding) == pytest.approx(1.0)
    assert len(tf.calls) == 2 and tf.calls[0] is imgs[0] and tf.calls[1] is imgs[1]
    # stack received the per-image tensors BY IDENTITY (an empty list or a
    # None append changes the recorded args)
    ((a, kw),) = t.stack_rec.entries
    assert a == (tf.made,) and kw == {}
    assert ("to", "batch", "FAKE-DEVICE") in t.stack_log.entries
    assert len(model.calls) == 1  # ONE stacked batch through the model
    assert model.calls[0] is t.stack_made[0]  # model(batch_tensor) pin
    assert t.im_count == 1


def test_batch_ids_absent_gives_none():
    res, _, _, _ = _batch_ok(ids=None)
    assert res[0].detection_id is None
    # an empty LIST is falsy -> None too (an `is not None` twin IndexErrors)
    res2, _, _, _ = _batch_ok(ids=[])
    assert res2[0].detection_id is None


def test_batch_confidence_matrix():
    cases = [
        ((31, 63), 0.5),
        ((31, 200), 0.5),  # width-ONLY small: or->and on the FIRST if
        ((200, 63), 0.5),  # height-ONLY small: same polarity
        ((32, 64), 0.8),
        ((32, 200), 0.8),
        ((200, 127), 0.8),
        ((200, 64), 0.8),
        ((64, 128), 1.0),
    ]
    imgs = [_img(size=s) for s, _ in cases]
    res, _, _, _ = _batch_ok(images=imgs)
    assert [r.confidence for r in res] == [e for _, e in cases]


def test_batch_rgb_convert():
    rgb_img = _img()
    imgs = [_img(mode="L"), rgb_img]
    res, _, tf, _ = _batch_ok(images=imgs)
    assert tf.calls[0].mode == "RGB" and tf.calls[0] is not imgs[0]
    assert tf.calls[1] is rgb_img


def test_batch_tuple_output():
    rows = np.vstack([_vec(1.0)])
    model = FakeModel(rows)
    model.return_tuple = True
    res, _, _, _ = _batch_ok(model=model, rows=rows)
    assert len(res) == 1


def test_batch_norms():
    res, _, _, _ = _batch_ok(rows=np.zeros((1, 512)))
    assert np.all(res[0].embedding == 0.0) and np.all(np.isfinite(res[0].embedding))
    res2, _, _, _ = _batch_ok(rows=np.array([_vec(0.5)]))
    assert np.linalg.norm(res2[0].embedding) == pytest.approx(1.0)


def test_batch_model_id_provenance():
    import backend.services.osnet_loader as m

    md = _mk_dict(model_id="belt-9")
    md["model"] = FakeModel(np.vstack([_vec(1.0)]))
    md["transform"] = FakeTransform()
    t = FakeTorch()
    with patch.dict(sys.modules, {"torch": t}):
        res = run(m.extract_person_embeddings_batch(md, [_img()]))
    assert res[0].model_id == "belt-9"


def test_batch_failure_logs_and_wraps():
    import backend.services.osnet_loader as m

    t = FakeTorch()
    md = _mk_dict(model=FakeModel(np.zeros((1, 512))), transform=BoomTransform())
    with caplogger() as recs, patch.dict(sys.modules, {"torch": t}):
        with pytest.raises(RuntimeError) as ei:
            run(m.extract_person_embeddings_batch(md, [_img()]))
    assert str(ei.value) == "Batch person embedding extraction failed: inner"
    errs = [r for r in recs if r.levelno == logging.ERROR]
    assert [r.msg for r in errs] == ["Batch person embedding extraction failed"]
    assert isinstance(errs[0].exc_info, tuple)


# ---------------------------------------------------------- load_osnet_model


def test_load_success_full_pin(tmp_path=None):
    tmp_path = _tmpdir(tmp_path)
    import backend.services.osnet_loader as m

    wfile = tmp_path / "model.pth"
    wfile.write_bytes(b"x")
    world = LoadWorld()
    with caplogger() as recs, world:
        out = run(m.load_osnet_model(str(tmp_path)))
    assert out["model"] is world.model
    assert out["transform"][0] == "COMPOSE"
    assert out["embedding_dim"] == 512
    assert out["model_id"] == "osnet-ain-x1-0@model"
    # security validation pinned WHOLE: must_exist=False EXPLICIT (the
    # omitted/None twins record a DIFFERENT kwargs dict)
    assert world.security.calls == [
        ((str(tmp_path),), {"allowed_extensions": frozenset(), "must_exist": False})
    ]
    # torch.load pinned: NEM-4519 weights_only=True + map_location cpu
    assert world.torch.load_rec.entries == [
        ((wfile,), {"map_location": "cpu", "weights_only": True})
    ]
    assert world.builder.calls == [
        ((), {"name": "osnet_ain_x1_0", "num_classes": 1, "pretrained": False})
    ]
    assert world.model.load_sd_calls == [(({"conv1.w": 1},), {"strict": False})]
    assert world.model.eval_count == 1 and world.model.cuda_count == 0
    ops = world.transforms.compose_rec.entries[0][0][0]
    assert list(ops) == [
        FakeTransformsNS.Op("Resize", ((256, 128),), {}),
        FakeTransformsNS.Op("ToTensor", (), {}),
        FakeTransformsNS.Op(
            "Normalize", (), {"mean": [0.485, 0.456, 0.406], "std": [0.229, 0.224, 0.225]}
        ),
    ]
    infos = [(r.levelno, r.msg) for r in recs if r.levelno >= logging.INFO]
    assert (logging.INFO, f"Loading OSNet-AIN x1.0 model from {tmp_path}") in infos
    assert (
        logging.INFO,
        f"Loaded OSNet-AIN x1.0 weights from {wfile} "
        "(model_id=osnet-ain-x1-0@model, verified critical layers)",
    ) in infos
    assert (logging.INFO, "OSNet model using CPU") in infos
    assert (logging.INFO, f"Successfully loaded OSNet-AIN x1.0 model from {tmp_path}") in infos


def test_load_cuda_branch(tmp_path=None):
    tmp_path = _tmpdir(tmp_path)
    import backend.services.osnet_loader as m

    (tmp_path / "model.pth").write_bytes(b"x")
    world = LoadWorld(cuda=True)
    with caplogger() as recs, world:
        run(m.load_osnet_model(str(tmp_path)))
    assert world.model.cuda_count == 1 and world.model.eval_count == 1
    assert any(r.msg == "OSNet model moved to CUDA" for r in recs)
    assert not any(r.msg == "OSNet model using CPU" for r in recs)


def test_load_file_path_used_directly(tmp_path=None):
    tmp_path = _tmpdir(tmp_path)
    import backend.services.osnet_loader as m

    wfile = tmp_path / "special_weights.pth"
    wfile.write_bytes(b"x")
    world = LoadWorld()
    with caplogger(), world:
        out = run(m.load_osnet_model(str(wfile)))
    assert out["model_id"] == "osnet-ain-x1-0@special_weights"
    assert world.torch.load_rec.entries[0][0] == (wfile,)


def test_load_dir_name_priority(tmp_path=None):
    tmp_path = _tmpdir(tmp_path)
    import backend.services.osnet_loader as m

    (tmp_path / "model.pth").write_bytes(b"a")
    (tmp_path / "aaa.pth").write_bytes(b"a")
    (tmp_path / "osnet_ain_x1_0_msmt17.pth").write_bytes(b"a")
    world = LoadWorld()
    with caplogger(), world:
        out = run(m.load_osnet_model(str(tmp_path)))
    assert out["model_id"] == "osnet-ain-x1-0@model"

    d2 = tmp_path / "d2"
    d2.mkdir()
    (d2 / "aaa.pth").write_bytes(b"a")
    (d2 / "osnet_ain_x1_0_msmt17.pth").write_bytes(b"a")
    world2 = LoadWorld()
    with caplogger(), world2:
        out2 = run(m.load_osnet_model(str(d2)))
    assert out2["model_id"] == "osnet-ain-x1-0@osnet_ain_x1_0_msmt17"

    d3 = tmp_path / "d3"
    d3.mkdir()
    (d3 / "zzz.pth").write_bytes(b"a")
    (d3 / "aaa.pth").write_bytes(b"a")
    world3 = LoadWorld()
    with caplogger(), world3:
        out3 = run(m.load_osnet_model(str(d3)))
    assert out3["model_id"] == "osnet-ain-x1-0@aaa"  # sorted glob FIRST


def test_load_no_weights_raises(tmp_path=None):
    tmp_path = _tmpdir(tmp_path)
    import backend.services.osnet_loader as m

    empty = tmp_path / "e"
    empty.mkdir()
    world = LoadWorld()
    with caplogger() as recs, world:
        with pytest.raises(RuntimeError) as ei:
            run(m.load_osnet_model(str(empty)))
    assert "No model weights found in" in str(ei.value)
    errs = [r for r in recs if r.levelno == logging.ERROR]
    assert [r.msg for r in errs] == ["Failed to load OSNet model"]
    assert isinstance(errs[0].exc_info, tuple)
    assert errs[0].model_path == str(empty)  # the flattened extra=


def test_load_path_security_rejection(tmp_path=None):
    tmp_path = _tmpdir(tmp_path)
    import backend.services.osnet_loader as m

    world = LoadWorld(security_exc=PathSecErr("traversal detected"))
    with caplogger(), world:
        with pytest.raises(RuntimeError) as ei:
            run(m.load_osnet_model("/bad/.."))
    # the "Invalid model path" RuntimeError is ITSELF caught by the outer
    # handler and wrapped once more - full message pinned:
    assert str(ei.value) == ("Failed to load OSNet model: Invalid model path: traversal detected")
    assert world.security.calls  # validation DID run before anything else


def test_load_sha_pin_enforced_pre_load(tmp_path=None):
    tmp_path = _tmpdir(tmp_path)
    import hashlib

    import backend.services.osnet_loader as m

    wfile = tmp_path / "model.pth"
    wfile.write_bytes(b"payload")
    actual = hashlib.sha256(b"payload").hexdigest()
    world = LoadWorld()
    with caplogger(), world:
        with pytest.raises(RuntimeError) as ei:
            run(m.load_osnet_model(str(tmp_path), expected_sha256="f" * 64))
    msg = str(ei.value)
    assert f"OSNet weights sha256 mismatch for model.pth: got {actual}, pinned {'f' * 64}" in msg
    assert world.torch.load_rec.entries == []  # NEVER deserialized
    world2 = LoadWorld()
    with caplogger(), world2:
        out = run(m.load_osnet_model(str(tmp_path), expected_sha256=actual))
    assert out["model_id"] == f"osnet-ain-x1-0@model@{actual[:12]}"


def test_load_module_prefix_strip_and_classifier_filter(tmp_path=None):
    tmp_path = _tmpdir(tmp_path)
    import backend.services.osnet_loader as m

    (tmp_path / "model.pth").write_bytes(b"x")
    sd = {
        "module.conv1.w": 1,
        "module.bn1.w": 2,
        "classifier.weight": 3,
        "classifier.bias": 4,
        "layer.0": 5,
    }
    world = LoadWorld(state_dict=dict(sd))
    with caplogger() as recs, world:
        run(m.load_osnet_model(str(tmp_path)))
    (((passed,), kw),) = world.model.load_sd_calls
    assert passed == {"conv1.w": 1, "bn1.w": 2, "layer.0": 5}
    assert kw == {"strict": False}
    dbg = [r.msg for r in recs if r.levelno == logging.DEBUG]
    assert "Stripped 'module.' prefix from state dict keys" in dbg
    assert "Filtered out classifier keys: ['classifier.weight', 'classifier.bias']" in dbg


CRITICAL_MSG = (
    "Critical OSNet weights missing: {}... (total {} missing). "
    "This will cause degraded Re-ID accuracy. Check model architecture compatibility."
)


def test_load_critical_missing_raises_per_prefix(tmp_path=None):
    tmp_path = _tmpdir(tmp_path)
    import backend.services.osnet_loader as m

    (tmp_path / "model.pth").write_bytes(b"x")
    for pref in ("conv1.", "conv2.", "conv3.", "conv4.", "conv5.", "bn"):
        lr = LoadResult(missing=[f"{pref}x.weight", "fc.weight"])
        world = LoadWorld(load_result=lr)
        with caplogger() as recs, world:
            with pytest.raises(RuntimeError) as ei:
                run(m.load_osnet_model(str(tmp_path)))
        expect = CRITICAL_MSG.format(f"['{pref}x.weight']", 1)
        assert expect in str(ei.value)
        assert any(r.levelno == logging.ERROR and r.msg == expect for r in recs)


def test_load_critical_slice_and_count(tmp_path=None):
    tmp_path = _tmpdir(tmp_path)
    """7 critical missing keys: the message shows the FIRST FIVE and the
    TRUE total (kills [:5]->[:6]/[:]/[1:] and the count twins)."""
    import backend.services.osnet_loader as m

    (tmp_path / "model.pth").write_bytes(b"x")
    seven = [f"conv1.k{i}" for i in range(7)]  # critical-prefixed
    lr = LoadResult(missing=list(seven))
    world = LoadWorld(load_result=lr)
    with caplogger(), world:
        with pytest.raises(RuntimeError) as ei:
            run(m.load_osnet_model(str(tmp_path)))
    expect = CRITICAL_MSG.format(str(seven[:5]), 7)
    assert expect in str(ei.value)


def test_load_noncritical_warning_slices(tmp_path=None):
    tmp_path = _tmpdir(tmp_path)
    import backend.services.osnet_loader as m

    (tmp_path / "model.pth").write_bytes(b"x")
    four = ["fc.weight", "aux.b", "aux.c", "aux.d"]
    unexp = ["odd.k", "odd.j", "odd.l", "odd.m"]
    lr = LoadResult(missing=list(four), unexpected=list(unexp))
    world = LoadWorld(load_result=lr)
    with caplogger() as recs, world:
        run(m.load_osnet_model(str(tmp_path)))
    warns = [r.msg for r in recs if r.levelno == logging.WARNING]
    assert warns == [
        f"OSNet state dict: 4 missing keys (expected for classifier): {four[:3]}...",
        f"OSNet state dict: 4 unexpected keys: {unexp[:3]}...",
    ]


def test_load_missing_result_attrs_default_empty(tmp_path=None):
    tmp_path = _tmpdir(tmp_path)
    import backend.services.osnet_loader as m

    (tmp_path / "model.pth").write_bytes(b"x")
    world = LoadWorld()
    world.model.result = NoAttrs()
    with caplogger() as recs, world:
        out = run(m.load_osnet_model(str(tmp_path)))
    assert out["model"] is world.model  # the [] getattr defaults hold
    assert not any(r.levelno >= logging.WARNING for r in recs)


def test_load_torchreid_absent_torchscript_ok(tmp_path=None):
    tmp_path = _tmpdir(tmp_path)
    import backend.services.osnet_loader as m

    wfile = tmp_path / "model.pth"
    wfile.write_bytes(b"x")
    world = LoadWorld(torchreid=False)
    with caplogger() as recs, world:
        out = run(m.load_osnet_model(str(tmp_path)))
    assert out["model"] is world.torch.jit_result
    assert world.torch.jit_rec.entries == [((wfile,), {})]
    infos = [r.msg for r in recs if r.levelno == logging.INFO]
    assert "torchreid not available, trying direct model load" in infos
    assert "Loaded OSNet as TorchScript model" in infos
    assert world.torch.jit_result.eval_count == 1


def test_load_torchscript_fails_raise(tmp_path=None):
    tmp_path = _tmpdir(tmp_path)
    import backend.services.osnet_loader as m

    (tmp_path / "model.pth").write_bytes(b"x")
    world = LoadWorld(torchreid=False)
    world.torch.jit_result = None  # jit.load refuses
    with caplogger(), world:
        with pytest.raises(RuntimeError) as ei:
            run(m.load_osnet_model(str(tmp_path)))
    assert str(ei.value) == (
        "Failed to load OSNet model: OSNet requires either torchreid package "
        "or TorchScript model. Install torchreid: pip install torchreid"
    )


def test_load_torch_absent_import_error():
    import backend.services.osnet_loader as m

    with caplogger() as recs, patch.dict(sys.modules, {"torch": None}):
        with pytest.raises(ImportError) as ei:
            run(m.load_osnet_model("/models/x"))
    assert str(ei.value) == (
        "OSNet requires torch and torchvision. Install with: pip install torch torchvision"
    )
    warns = [r.msg for r in recs if r.levelno == logging.WARNING]
    assert warns == [
        "torch or torchvision package not installed. Install with: pip install torch torchvision"
    ]


def test_load_generic_failure_extra(tmp_path=None):
    tmp_path = _tmpdir(tmp_path)
    import backend.services.osnet_loader as m

    (tmp_path / "model.pth").write_bytes(b"x")
    world = LoadWorld(sd_raise=ValueError("sd exploded"))
    with caplogger() as recs, world:
        with pytest.raises(RuntimeError) as ei:
            run(m.load_osnet_model(str(tmp_path)))
    assert str(ei.value) == "Failed to load OSNet model: sd exploded"
    errs = [r for r in recs if r.levelno == logging.ERROR]
    assert [r.msg for r in errs] == ["Failed to load OSNet model"]
    assert isinstance(errs[0].exc_info, tuple)
    assert errs[0].model_path == str(tmp_path)


def test_load_runs_work_off_the_event_loop(tmp_path=None):
    tmp_path = _tmpdir(tmp_path)
    """_load runs inside run_in_executor(None, ...) - the patched _sha256
    spy must observe a NON-main thread (inline-call/arg-order twins)."""
    import backend.services.osnet_loader as m

    (tmp_path / "model.pth").write_bytes(b"x")
    seen = []
    orig = m._sha256

    def spy(p):
        seen.append(threading.get_ident())
        return orig(p)

    world = LoadWorld()
    main = threading.get_ident()
    with caplogger(), world, patch.object(m, "_sha256", spy):
        with pytest.raises(RuntimeError):
            run(m.load_osnet_model(str(tmp_path), expected_sha256="0" * 64))
    assert seen and seen[0] != main
