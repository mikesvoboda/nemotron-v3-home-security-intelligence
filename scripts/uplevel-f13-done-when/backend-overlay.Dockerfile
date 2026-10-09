# F1.3 Done-when run: make the published backend image's app runtime match HEAD.
#
# The published :latest image was built at cd3a85a9, which predates the B1.5
# gate merge. Its venv therefore still carries python-jose, and mounting this
# working tree's backend/ over it fails at `import jwt` (auth_service.py:19).
# The app-runtime delta between cd3a85a9 and HEAD is exactly one swap in
# uv.lock: python-jose{,e cdsa,rsa,pyasn1} out, pyjwt in (root
# pyproject.toml). Installing that one package makes the venv satisfy
# HEAD's lock for every module the app imports; the residual jose dependencies
# are inert because no current module imports them.
#
# The working-tree source is mounted at runtime (see
# docker-compose.f13-stack.yml), so the process that answers
# /api/auth/setup-status and gates /ws is the tree under test.
FROM ghcr.io/mikesvoboda/nemotron-v3-home-security-intelligence/backend:latest

# hadolint ignore=DL3002
USER root
RUN uv pip install --python /app/.venv/bin/python --no-cache pyjwt==2.15.1 && \
    uv pip uninstall --python /app/.venv/bin/python python-jose && \
    /app/.venv/bin/python -c "import jwt; print('overlay jwt', jwt.__version__)"
USER appuser
