# DCGM Exporter Configuration

Configuration files for NVIDIA DCGM (Data Center GPU Manager) Exporter.

## Purpose

DCGM Exporter exposes low-level GPU hardware metrics to Prometheus. This directory contains custom counter configurations that extend the default metrics.

## Files

| File                  | Purpose                                                         |
| --------------------- | --------------------------------------------------------------- |
| `custom-counters.csv` | Custom DCGM field definitions including PCIe throughput metrics |

## Custom Counters (custom-counters.csv)

The custom counters file extends the default DCGM exporter metrics to include:

### PCIe Throughput Metrics (NEM-4150)

- `DCGM_FI_PROF_PCIE_TX_BYTES` - PCIe transmit throughput (bytes/sec)
- `DCGM_FI_PROF_PCIE_RX_BYTES` - PCIe receive throughput (bytes/sec)

### Standard Metrics

- Clock frequencies (SM, Memory)
- Temperature (GPU, Memory)
- Power consumption
- Utilization (GPU, Memory, Encoder, Decoder)
- Framebuffer memory usage
- ECC error counters
- Retired pages
- XID errors

## Format

The CSV format is:

```
DCGM_FIELD, prometheus_metric_type, help_message
```

Example:

```csv
DCGM_FI_DEV_GPU_UTIL, gauge, GPU utilization (in %).
DCGM_FI_PROF_PCIE_TX_BYTES, gauge, The rate of data transmitted over the PCIe bus (bytes per second).
```

## Usage

The custom counters file is mounted into the DCGM exporter container at `/etc/dcgm-exporter/default-counters.csv` via docker-compose.prod.yml.

## References

- [DCGM Exporter Repository](https://github.com/NVIDIA/dcgm-exporter)
- [DCGM Field Identifiers](https://docs.nvidia.com/datacenter/dcgm/latest/dcgm-api/dcgm-api-field-ids.html)
- [Default Counters](https://github.com/NVIDIA/dcgm-exporter/blob/main/etc/default-counters.csv)

## Related

- Dashboard: `monitoring/grafana/dashboards/hsi-gpu-metrics.json` (PCIe Throughput panel)
- Prometheus config: `monitoring/prometheus.yml` (dcgm-exporter job)
- Alerts: `monitoring/gpu-alerts.yml`
