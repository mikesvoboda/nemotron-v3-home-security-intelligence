"""Vocabulary for vector PROVENANCE — F11's one-embedding-space ruling.

A stored embedding vector must always be able to answer WHICH weights
computed it. Every vector store in the system (face crops, household person
vectors, entity trail vectors) shares this one vocabulary so a comparison
can tell three states apart, never two:

* ``LEGACY_MODEL_ID``  — nobody said who computed this vector.  It is
  UNTRUSTED BY DEFAULT: it never participates in a score, only in the
  "re-enroll" answer.  A model id always contains '@' (the
  ``role@weights@sha`` grammar), so the sentinel can never collide with a
  real model id.
* a model id           — the weights are named; comparable with probes from
  the SAME id, incomparable (never scored) with any other.

This leaf has NO dependencies so every layer (models, loaders, services)
can import it without a cycle. ``backend.core.face_provenance`` re-exports
it so existing face-path imports keep working; a second literal here would
split the vocabulary between galleries, which is exactly the drift F11
rules out.
"""

from __future__ import annotations

__all__ = ["LEGACY_MODEL_ID"]

LEGACY_MODEL_ID = "legacy-unknown-provenance"
