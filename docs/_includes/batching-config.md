| Parameter      | Default | Environment Variable           | Description                                 |
| -------------- | ------- | ------------------------------ | ------------------------------------------- |
| Window timeout | 90s     | `BATCH_WINDOW_SECONDS`         | Maximum batch duration from first detection |
| Idle timeout   | 30s     | `BATCH_IDLE_TIMEOUT_SECONDS`   | Close batch if no new detections            |
| Check interval | 5s      | `BATCH_CHECK_INTERVAL_SECONDS` | How often BatchTimeoutWorker runs           |
| Max detections | 500     | `BATCH_MAX_DETECTIONS`         | Maximum detections per batch before split   |
