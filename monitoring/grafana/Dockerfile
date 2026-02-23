# syntax=docker/dockerfile:1
# Grafana with marcusolsson-json-datasource plugin pre-installed.
# Pre-installing avoids runtime download from grafana.com, which can timeout
# when the container has no outbound internet access (e.g. air-gapped, firewall).
# See: https://github.com/mikesvoboda/nemotron-v3-home-security-intelligence/issues (Grafana restart loop)

FROM docker.io/grafana/grafana:12.3.2

USER root

# Pre-install JSON API datasource plugin (required for Backend-API datasource and dashboards)
# No runtime download needed; plugin is baked into the image
RUN grafana-cli plugins install marcusolsson-json-datasource

USER grafana
