# syntax=docker/dockerfile:1
# Grafana with all required plugins pre-installed into /opt/grafana/plugins.
# Pre-installing avoids runtime downloads from grafana.com, which timeout
# when the container has no outbound internet access (e.g. air-gapped, firewall).
# The container runs read_only so no plugins can be installed at runtime.

FROM docker.io/grafana/grafana:12.3.2

USER root

RUN mkdir -p /opt/grafana/plugins /etc/grafana/provisioning/plugins && \
    grafana-cli --pluginsDir /opt/grafana/plugins plugins install marcusolsson-json-datasource && \
    grafana-cli --pluginsDir /opt/grafana/plugins plugins install grafana-pyroscope-app && \
    grafana-cli --pluginsDir /opt/grafana/plugins plugins install grafana-exploretraces-app && \
    grafana-cli --pluginsDir /opt/grafana/plugins plugins install grafana-lokiexplore-app && \
    grafana-cli --pluginsDir /opt/grafana/plugins plugins install grafana-metricsdrilldown-app && \
    chown -R grafana:root /opt/grafana

USER grafana
