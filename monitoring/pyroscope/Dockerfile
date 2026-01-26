# Pyroscope with wget for health checks
# The official grafana/pyroscope image is a scratch/distroless image without
# standard utilities like wget or curl, which are needed for health checks.
#
# This Dockerfile adds a statically-linked BusyBox to enable health checks.

# First stage: get statically-linked busybox
FROM docker.io/library/busybox:1.36-musl AS busybox

# Final stage: pyroscope with busybox
FROM docker.io/grafana/pyroscope:1.18.0

# Switch to root to create symlinks
USER root

# Copy statically-linked busybox binary
COPY --from=busybox /bin/busybox /bin/busybox

# Create symlinks for common utilities using busybox
# hadolint ignore=DL3059
RUN ["/bin/busybox", "ln", "-sf", "/bin/busybox", "/bin/sh"]
# hadolint ignore=DL3059
RUN ["/bin/busybox", "ln", "-sf", "/bin/busybox", "/bin/wget"]

# Switch back to pyroscope user
USER pyroscope

# The default entrypoint and command are inherited from the base image
