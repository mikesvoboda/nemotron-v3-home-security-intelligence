# SMTP Configuration for Email Alerts

> Configure email notifications for Grafana dashboards and Alertmanager alert routing.

This guide covers SMTP setup for both Grafana (dashboard alerts) and Alertmanager (Prometheus alert notifications). Both systems can be configured independently or share the same SMTP server.

---

## Overview

The Home Security Intelligence monitoring stack supports email alerts through two components:

| Component        | Purpose                                | Configuration Method  |
| ---------------- | -------------------------------------- | --------------------- |
| **Grafana**      | Dashboard-based alerts and reports     | Environment variables |
| **Alertmanager** | Prometheus alerting rule notifications | Configuration file    |

**When to use each:**

- **Grafana alerts**: For dashboard-defined thresholds, scheduled reports, and ad-hoc notifications
- **Alertmanager**: For infrastructure alerts, SLO violations, and on-call routing

---

## Quick Start

### Enable Grafana Email Alerts

1. **Configure SMTP in `.env`:**

   ```bash
   # Enable SMTP
   GF_SMTP_ENABLED=true
   GF_SMTP_HOST=smtp.gmail.com:587
   GF_SMTP_USER=your-email@gmail.com
   GF_SMTP_PASSWORD=your-app-password
   GF_SMTP_FROM_ADDRESS=your-email@gmail.com
   GF_SMTP_FROM_NAME=Home Security Alerts
   ```

2. **Restart Grafana:**

   ```bash
   podman-compose -f docker-compose.prod.yml restart grafana
   ```

3. **Verify in Grafana UI:**

   - Navigate to http://localhost:3002/admin/settings
   - Check the SMTP section shows "enabled"

### Enable Alertmanager Email Alerts

1. **Configure SMTP in `.env`:**

   ```bash
   ALERTMANAGER_SMTP_HOST=smtp.gmail.com:587
   ALERTMANAGER_SMTP_FROM=alertmanager@example.com
   ALERTMANAGER_SMTP_USER=your-email@gmail.com
   ALERTMANAGER_SMTP_PASSWORD=your-app-password
   ```

2. **Uncomment SMTP settings in `monitoring/alertmanager.yml`:**

   ```yaml
   global:
     smtp_smarthost: 'smtp.gmail.com:587'
     smtp_from: 'alertmanager@example.com'
     smtp_auth_username: 'your-email@gmail.com'
     smtp_auth_password: 'your-app-password' <!-- pragma: allowlist secret -->
     smtp_require_tls: true
   ```

3. **Enable email receivers:**

   ```yaml
   receivers:
     - name: 'critical-receiver'
       email_configs:
         - to: 'oncall@example.com'
           send_resolved: true
   ```

4. **Restart Alertmanager:**

   ```bash
   podman-compose -f docker-compose.prod.yml restart alertmanager
   ```

---

## Grafana SMTP Configuration

### Environment Variables

All Grafana SMTP settings are configured via environment variables in `docker-compose.prod.yml`:

| Variable                  | Default                | Description                       |
| ------------------------- | ---------------------- | --------------------------------- |
| `GF_SMTP_ENABLED`         | `false`                | Enable/disable SMTP               |
| `GF_SMTP_HOST`            | `smtp.example.com:587` | SMTP server host and port         |
| `GF_SMTP_USER`            | (empty)                | SMTP authentication username      |
| `GF_SMTP_PASSWORD`        | (empty)                | SMTP authentication password      |
| `GF_SMTP_FROM_ADDRESS`    | `grafana@example.com`  | Sender email address              |
| `GF_SMTP_FROM_NAME`       | `Grafana Alerts`       | Sender display name               |
| `GF_SMTP_STARTTLS_POLICY` | `MandatoryStartTLS`    | TLS policy (see below)            |
| `GF_SMTP_SKIP_VERIFY`     | `false`                | Skip TLS certificate verification |

### TLS Policies

| Policy                  | Description                                          |
| ----------------------- | ---------------------------------------------------- |
| `MandatoryStartTLS`     | Require TLS (recommended for production)             |
| `OpportunisticStartTLS` | Use TLS if available                                 |
| `NoStartTLS`            | No TLS (NOT recommended, only for internal networks) |

### Testing Grafana SMTP

1. Go to Grafana: http://localhost:3002
2. Navigate to **Alerting > Contact points**
3. Create a new contact point with email receiver
4. Click **Test** to send a test email

---

## Alertmanager SMTP Configuration

### Configuration File

Edit `monitoring/alertmanager.yml` to configure SMTP:

```yaml
global:
  # SMTP server settings
  smtp_smarthost: 'smtp.gmail.com:587'
  smtp_from: 'alertmanager@example.com'
  smtp_auth_username: 'your-email@gmail.com'
  smtp_auth_password: 'your-app-password' <!-- pragma: allowlist secret -->
  smtp_require_tls: true
  smtp_hello: 'localhost'
```

### Email Receiver Configuration

Add email receivers to the `receivers` section:

```yaml
receivers:
  # Critical alerts - immediate email notification
  - name: 'critical-receiver'
    webhook_configs:
      - url: 'http://backend:8000/api/webhooks/alerts'
        send_resolved: true
    email_configs:
      - to: 'oncall@example.com'
        send_resolved: true
        headers:
          subject: '[CRITICAL] {{ .GroupLabels.alertname }}'

  # SLO burn rate alerts
  - name: 'slo-receiver'
    email_configs:
      - to: 'sre-team@example.com'
        send_resolved: true
        headers:
          subject: '[SLO] {{ .GroupLabels.slo }} burn rate alert'
```

### Multiple Recipients

Send to multiple email addresses:

```yaml
email_configs:
  - to: 'primary@example.com,secondary@example.com'
    send_resolved: true
```

Or use separate email_configs for different recipients with different settings:

```yaml
email_configs:
  - to: 'oncall@example.com'
    send_resolved: true
  - to: 'manager@example.com'
    send_resolved: false # Only send firing alerts
```

### Testing Alertmanager SMTP

1. **Reload configuration:**

   ```bash
   curl -X POST http://localhost:9093/-/reload
   ```

2. **Manually fire a test alert:**

   ```bash
   curl -X POST http://localhost:9093/api/v2/alerts \
     -H "Content-Type: application/json" \
     -d '[{
       "labels": {
         "alertname": "TestAlert",
         "severity": "critical"
       },
       "annotations": {
         "summary": "Test alert for SMTP verification",
         "description": "This is a test alert to verify email delivery."
       }
     }]'
   ```

3. **Check alert status:**

   ```bash
   curl http://localhost:9093/api/v2/alerts | jq
   ```

---

## Provider-Specific Setup

### Gmail

Gmail requires an app-specific password (not your regular password):

1. Enable 2-Step Verification: https://myaccount.google.com/security
2. Generate App Password: https://myaccount.google.com/apppasswords
3. Select "Mail" and "Other (Custom name)"
4. Use the generated 16-character password

```bash
GF_SMTP_HOST=smtp.gmail.com:587
GF_SMTP_USER=your-email@gmail.com
GF_SMTP_PASSWORD=xxxx-xxxx-xxxx-xxxx  # App password
GF_SMTP_FROM_ADDRESS=your-email@gmail.com
```

### Microsoft 365 / Outlook

```bash
GF_SMTP_HOST=smtp.office365.com:587
GF_SMTP_USER=your-email@yourdomain.com
GF_SMTP_PASSWORD=your-password
GF_SMTP_FROM_ADDRESS=your-email@yourdomain.com
```

**Note:** Modern authentication may require OAuth2. For simpler setup, create a dedicated service account with basic auth enabled.

### Amazon SES

```bash
GF_SMTP_HOST=email-smtp.us-east-1.amazonaws.com:587
GF_SMTP_USER=AKIAIOSFODNN7EXAMPLE  # SES SMTP username
GF_SMTP_PASSWORD=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY
GF_SMTP_FROM_ADDRESS=alerts@yourdomain.com  # Must be verified in SES
```

### SendGrid

```bash
GF_SMTP_HOST=smtp.sendgrid.net:587
GF_SMTP_USER=apikey
GF_SMTP_PASSWORD=SG.xxxxxxxxxxxxxxxxxxxx  # API key
GF_SMTP_FROM_ADDRESS=alerts@yourdomain.com
```

### Mailgun

```bash
GF_SMTP_HOST=smtp.mailgun.org:587
GF_SMTP_USER=postmaster@yourdomain.mailgun.org
GF_SMTP_PASSWORD=your-mailgun-smtp-password
GF_SMTP_FROM_ADDRESS=alerts@yourdomain.com
```

### Self-Hosted (Postfix/Sendmail)

For internal SMTP servers without authentication:

```bash
GF_SMTP_HOST=mailserver.internal:25
GF_SMTP_USER=
GF_SMTP_PASSWORD=
GF_SMTP_FROM_ADDRESS=grafana@internal.local
GF_SMTP_STARTTLS_POLICY=OpportunisticStartTLS
```

---

## Security Best Practices

### Credential Management

1. **Never commit passwords to git**

   ```bash
   # Add to .gitignore
   .env
   secrets/
   ```

2. **Use Docker secrets for production**

   Create a secrets file:

   ```bash
   mkdir -p secrets
   echo "your-smtp-password" > secrets/smtp_password.txt
   chmod 600 secrets/smtp_password.txt
   ```

3. **Use environment-specific files**

   ```bash
   # .env.development - relaxed settings
   # .env.production - hardened settings with real credentials
   ```

### TLS Configuration

1. **Always use TLS** (`MandatoryStartTLS`) for external SMTP servers
2. **Never disable certificate verification** in production
3. **Use port 587** (submission) instead of port 25 (SMTP)
4. **Verify SMTP server certificates** are valid and trusted

### Rate Limiting

Configure alert grouping to prevent email flooding:

```yaml
# monitoring/alertmanager.yml
route:
  group_wait: 30s # Wait before first email
  group_interval: 5m # Wait before adding new alerts to group
  repeat_interval: 4h # Wait before resending same alert
```

---

## Troubleshooting

### Grafana SMTP Issues

**Error: "SMTP not configured"**

1. Verify `GF_SMTP_ENABLED=true` is set
2. Restart Grafana container after changing environment variables
3. Check Grafana logs:

   ```bash
   podman logs grafana 2>&1 | grep -i smtp
   ```

**Error: "Authentication failed"**

1. Verify username and password are correct
2. For Gmail, use app-specific password
3. Check if 2FA is enabled and requires app password

**Error: "TLS handshake failed"**

1. Verify the SMTP server supports TLS
2. Check port (587 for TLS, 465 for SSL)
3. Try `OpportunisticStartTLS` for testing
4. Check system CA certificates are up to date

**Emails not being received:**

1. Check spam/junk folder
2. Verify `GF_SMTP_FROM_ADDRESS` is valid
3. Check SPF/DKIM/DMARC records for your domain
4. Test with a different recipient email provider

### Alertmanager SMTP Issues

**Configuration syntax errors:**

```bash
# Validate configuration
podman exec alertmanager amtool check-config /etc/alertmanager/alertmanager.yml
```

**Alerts not triggering emails:**

1. Verify receiver is configured with `email_configs`
2. Check routing rules match the alert labels
3. Review Alertmanager logs:

   ```bash
   podman logs alertmanager 2>&1 | grep -i email
   ```

**Check notification history:**

```bash
curl http://localhost:9093/api/v2/alerts | jq '.[].status'
```

### Common Issues

| Symptom               | Cause                           | Solution                                    |
| --------------------- | ------------------------------- | ------------------------------------------- |
| Connection timeout    | Firewall blocking port          | Allow outbound 587/465                      |
| Authentication failed | Wrong credentials               | Verify username/password, use app password  |
| Certificate error     | Self-signed cert on SMTP server | Add CA cert or set `SKIP_VERIFY=true`       |
| Email in spam         | Missing SPF/DKIM                | Configure DNS records for your domain       |
| Rate limited          | Too many emails                 | Increase group_interval, use email batching |
| From address rejected | Domain verification required    | Verify sender domain with email provider    |

---

## Monitoring Email Delivery

### Grafana Metrics

Grafana exposes SMTP metrics at `/metrics`:

```promql
# Email send attempts
grafana_alerting_notifications_total{type="email"}

# Email send failures
grafana_alerting_notifications_failed_total{type="email"}
```

### Alertmanager Metrics

```promql
# Notifications sent
alertmanager_notifications_total{integration="email"}

# Notification failures
alertmanager_notifications_failed_total{integration="email"}

# Notification latency
alertmanager_notification_latency_seconds{integration="email"}
```

### Dashboard Panel

Add a panel to your monitoring dashboard:

```promql
# Email delivery success rate
rate(alertmanager_notifications_total{integration="email"}[5m])
/
(rate(alertmanager_notifications_total{integration="email"}[5m]) + rate(alertmanager_notifications_failed_total{integration="email"}[5m]))
```

---

## See Also

- [Prometheus Alerting](prometheus-alerting.md) - Alert rule configuration
- [Monitoring and Observability](monitoring.md) - Full monitoring stack documentation
- [Secrets Management](secrets-management.md) - Secure credential storage
- [Grafana Alerting Documentation](https://grafana.com/docs/grafana/latest/alerting/)
- [Alertmanager Configuration](https://prometheus.io/docs/alerting/latest/configuration/)
