# Custom Pyroscope image with py-spy profiler for Python process profiling
# Extends the official Pyroscope image with py-spy to profile backend services
FROM docker.io/grafana/pyroscope:1.4.0

USER root

# Install py-spy and dependencies
# Note: Pyroscope base image is Alpine-based
# hadolint ignore=DL3018
RUN apk add --no-cache \
    python3 \
    py3-pip \
    curl \
    procps \
    bash \
    && pip3 install --no-cache-dir --break-system-packages py-spy==0.4.0

# Copy profiler script
COPY profiler.sh /usr/local/bin/profiler.sh
RUN chmod +x /usr/local/bin/profiler.sh

# Copy entrypoint wrapper
COPY entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

# Create log directory
RUN mkdir -p /var/log && touch /var/log/profiler.log && chmod 666 /var/log/profiler.log

# Switch back to pyroscope user for main process
USER pyroscope

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
