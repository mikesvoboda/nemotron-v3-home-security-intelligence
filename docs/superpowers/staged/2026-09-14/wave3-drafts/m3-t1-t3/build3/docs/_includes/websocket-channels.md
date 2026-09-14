| Channel      | Endpoint                 | Purpose                      | Message Frequency |
| ------------ | ------------------------ | ---------------------------- | ----------------- |
| **Events**   | `/ws/events`             | Security event notifications | On event creation |
| **System**   | `/ws/system`             | System health and GPU stats  | Every 5 seconds   |
| **Job Logs** | `/ws/jobs/{job_id}/logs` | Real-time job log streaming  | On log emission   |
