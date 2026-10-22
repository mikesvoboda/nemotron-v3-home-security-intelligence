# The CI notification sinks' image ([r308a]): one stdlib-only program, three
# sink services. No pip installs — the supply-chain surface is the base image
# alone (pinned in backend/tests/unit/scripts/test_ci_sinks_overlay.py, which
# refuses any "pip install" line in this file).
FROM python:3.14-slim-bookworm

COPY docker/ci-sinks/sink.py /usr/local/bin/sink.py

# Each sink service writes only under SINK_DATA_DIR (the overlay sets it to a
# tmpfs and runs the container read_only), announces its ports on stdout.
ENV SINK_DATA_DIR=/data \
    PYTHONUNBUFFERED=1

ENTRYPOINT ["python3", "/usr/local/bin/sink.py"]
