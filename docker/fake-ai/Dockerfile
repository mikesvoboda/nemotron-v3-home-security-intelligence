# The fake AI stack's image (O2.1): the backend image, serving the
# deterministic fake in backend/ai_contract/fake/ instead of the backend app.
#
# FROM the backend image because the fake imports backend.ai_contract, whose
# __init__ registers the backend's own AI clients (providers.py), so it needs
# the backend's dependency set. Two additions on top:
#   - jsonschema: the fake validates every reply against its contract
#     schema, and only uv.lock's test group installs it. The four pins are
#     uv.lock's versions (attrs, its fifth dependency, is already in the prod
#     venv); backend/tests/unit/scripts/test_fake_ai_overlay.py pins them.
#   - this checkout's backend/, replacing the base image's tree (not laid over
#     it, so a file the checkout deleted is gone), so the fake that runs is
#     the one under review.
#
# docker-compose.fake-ai.yml builds it and runs it twice, as ai-vlm and
# ai-gateway. It is never a default; name the overlay with -f.
#
# BACKEND_IMAGE has no default: the overlay passes the backend image of the
# stack under test (the CI stack's ${IMAGE_TAG}), so the fake and the backend
# it answers share one dependency set. A standalone build must name it:
#   docker build -f docker/fake-ai/Dockerfile --build-arg BACKEND_IMAGE=<image:tag> .
ARG BACKEND_IMAGE
FROM ${BACKEND_IMAGE}

USER root
RUN uv pip install --python /app/.venv/bin/python --no-deps --no-cache \
        jsonschema==4.26.0 \
        jsonschema-specifications==2025.9.1 \
        referencing==0.37.0 \
        rpds-py==2026.6.3 \
    && rm -rf /app/backend
COPY --chown=appuser:appuser backend/ /app/backend/
USER appuser

# The backend's entrypoint waits for Postgres; the fake needs no database.
ENTRYPOINT []
# The overlay passes each service's own --port.
CMD ["uvicorn", "--factory", "backend.ai_contract.fake.app:create_served_app", \
     "--host", "0.0.0.0", "--port", "8000", "--no-server-header"]
