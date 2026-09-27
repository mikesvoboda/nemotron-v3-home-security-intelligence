"""Face-vector provenance vocabulary (F11 ruling 2, the one-embedding-space rule).

A stored face vector must say WHICH weights computed it, and a vector whose
origin is unknown must not be trusted with an origin. This module is the
shared vocabulary for that flag — deliberately a dependency-free leaf,
because both the ORM models (the column's default) and the extractor that
computes the honest ids need it, and neither may import the other.

Since the person-vector swap (ledger item 20) the constant lives in
``core.vector_provenance``, which the person galleries read too: ONE
sentinel for every vector store, or "untrusted" would mean different things
in the face and person paths. This module re-exports it so the face-path
import sites stay exactly as they are.
"""

from __future__ import annotations

#: Provenance id for a stored face vector that the pinned server-side
#: extractor did NOT compute. It is deliberately NOT shaped like a
#: ``name@file@sha`` model id: a row carrying it says "I do not know what
#: produced this vector", and the face specialist reads that as
#: "unavailable (re-enroll)" instead of scoring the comparison.
#:
#: This is not hypothetical. Both enrollment extractors were literally
#: ``np.random.rand(512)`` until the enrollment slice (ledger row 1.3b), so
#: every vector enrolled before it — and any vector a client POSTed — is
#: noise in a space of its own. Flagging them is what makes the re-enroll
#: rule real rather than only forward-looking.
from backend.core.vector_provenance import LEGACY_MODEL_ID

__all__ = ["LEGACY_MODEL_ID"]
