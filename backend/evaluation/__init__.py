"""Evaluation of the VLM verdict path.

The shipped pipeline is a detector gate followed by ONE vision-language model that
describes, verifies and risk-scores each candidate (``vlm_assess``). This package measures
that path against the success bars. Import the submodules directly; the package exports
nothing.

Modules:
    - ``assess_input``: the self-contained ``EvalItem`` / ``AssessInput`` a replay feeds the client
    - ``eval_store``: the immutable item and result store (generation 2, SQLite)
    - ``control_freeze``: freezing real events into the store, with the media-residence guard
    - ``label_import``: labeled events and generated corpus sets -> store items
    - ``levels``: risk score -> level banding (the one definition the harness may use)
    - ``s_metrics``: S2 / S3 / S5 with Wilson intervals, against the owner-set bars
    - ``vlm_replay``: replays a served VLM over the store through the shipped ``VlmClient``

The synthbench package (``synthbench/run``, ``synthbench/score``) drives these through
``python -m synthbench replay`` and ``score``.
"""
