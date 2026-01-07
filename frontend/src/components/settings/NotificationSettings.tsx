import { Card, Title, Text, Button, Badge } from '@tremor/react';
import {
  AlertCircle,
  Bell,
  CheckCircle,
  Loader2,
  Mail,
  Send,
  Webhook,
  X,
} from 'lucide-react';
import { useEffect, useState } from 'react';

import {
  fetchNotificationConfig,
  testNotification,
  type NotificationConfig,
} from '../../services/api';

export interface NotificationSettingsProps {
  className?: string;
}

/**
 * NotificationSettings component displays notification configuration status
 * - Shows email (SMTP) configuration status
 * - Shows webhook configuration status
 * - Displays configured recipients and URLs
 * - Provides test notification buttons for each channel
 * - Handles loading, error, and success states
 */
export default function NotificationSettings({ className }: NotificationSettingsProps) {
  const [config, setConfig] = useState<NotificationConfig | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [testingEmail, setTestingEmail] = useState(false);
  const [testingWebhook, setTestingWebhook] = useState(false);
  const [testResult, setTestResult] = useState<{
    channel: string;
    success: boolean;
    message: string;
  } | null>(null);

  useEffect(() => {
    const loadConfig = async () => {
      try {
        setLoading(true);
        setError(null);
        const data = await fetchNotificationConfig();
        setConfig(data);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load notification configuration');
      } finally {
        setLoading(false);
      }
    };

    void loadConfig();
  }, []);

  const handleTestEmail = async () => {
    if (!config?.email_configured) return;

    try {
      setTestingEmail(true);
      setTestResult(null);
      const result = await testNotification('email');
      setTestResult({
        channel: 'email',
        success: result.success,
        message: result.message,
      });

      // Clear test result after 5 seconds
      setTimeout(() => setTestResult(null), 5000);
    } catch (err) {
      setTestResult({
        channel: 'email',
        success: false,
        message: err instanceof Error ? err.message : 'Failed to send test email',
      });
    } finally {
      setTestingEmail(false);
    }
  };

  const handleTestWebhook = async () => {
    if (!config?.webhook_configured) return;

    try {
      setTestingWebhook(true);
      setTestResult(null);
      const result = await testNotification('webhook');
      setTestResult({
        channel: 'webhook',
        success: result.success,
        message: result.message,
      });

      // Clear test result after 5 seconds
      setTimeout(() => setTestResult(null), 5000);
    } catch (err) {
      setTestResult({
        channel: 'webhook',
        success: false,
        message: err instanceof Error ? err.message : 'Failed to send test webhook',
      });
    } finally {
      setTestingWebhook(false);
    }
  };

  return (
    <Card className={`border-gray-800 bg-[#1A1A1A] shadow-lg ${className || ''}`}>
      <Title className="mb-4 flex items-center gap-2 text-white">
        <Bell className="h-5 w-5 text-[#76B900]" />
        Notification Settings
      </Title>

      {loading && (
        <div className="space-y-4">
          <div className="skeleton h-32 w-full"></div>
          <div className="skeleton h-32 w-full"></div>
        </div>
      )}

      {error && (
        <div className="mb-4 flex items-center gap-2 rounded-lg border border-red-500/30 bg-red-500/10 p-4">
          <AlertCircle className="h-5 w-5 flex-shrink-0 text-red-400" />
          <Text className="text-red-400">{error}</Text>
        </div>
      )}

      {testResult && (
        <div
          className={`mb-4 flex items-center gap-2 rounded-lg border p-4 ${
            testResult.success
              ? 'border-green-500/30 bg-green-500/10'
              : 'border-red-500/30 bg-red-500/10'
          }`}
        >
          {testResult.success ? (
            <CheckCircle className="h-5 w-5 flex-shrink-0 text-green-500" />
          ) : (
            <X className="h-5 w-5 flex-shrink-0 text-red-400" />
          )}
          <Text className={testResult.success ? 'text-green-500' : 'text-red-400'}>
            {testResult.message}
          </Text>
        </div>
      )}

      {!loading && config && (
        <div className="space-y-6">
          {/* Notifications Enabled Status */}
          <div className="flex items-center justify-between border-b border-gray-800 pb-4">
            <div>
              <Text className="font-medium text-gray-300">Notifications</Text>
              <Text className="mt-1 text-xs text-gray-500">
                Overall notification system status
              </Text>
            </div>
            <Badge
              color={config.notification_enabled ? 'green' : 'gray'}
              size="lg"
            >
              {config.notification_enabled ? 'Enabled' : 'Disabled'}
            </Badge>
          </div>

          {/* Email (SMTP) Configuration */}
          <div className="rounded-lg border border-gray-800 bg-[#121212] p-4">
            <div className="mb-4 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Mail className="h-5 w-5 text-blue-400" />
                <Text className="font-medium text-gray-300">Email (SMTP)</Text>
              </div>
              <Badge
                color={config.email_configured ? 'green' : 'gray'}
                size="sm"
              >
                {config.email_configured ? 'Configured' : 'Not Configured'}
              </Badge>
            </div>

            {config.email_configured ? (
              <div className="space-y-3">
                <div className="grid grid-cols-2 gap-4 text-sm">
                  <div>
                    <Text className="text-gray-500">SMTP Host</Text>
                    <Text className="text-white">{config.smtp_host || '-'}</Text>
                  </div>
                  <div>
                    <Text className="text-gray-500">Port</Text>
                    <Text className="text-white">{config.smtp_port || '-'}</Text>
                  </div>
                  <div>
                    <Text className="text-gray-500">From Address</Text>
                    <Text className="text-white">{config.smtp_from_address || '-'}</Text>
                  </div>
                  <div>
                    <Text className="text-gray-500">TLS</Text>
                    <Text className="text-white">
                      {config.smtp_use_tls ? 'Enabled' : 'Disabled'}
                    </Text>
                  </div>
                </div>

                {config.default_email_recipients.length > 0 && (
                  <div>
                    <Text className="mb-2 text-gray-500">Default Recipients</Text>
                    <div className="flex flex-wrap gap-2">
                      {config.default_email_recipients.map((email, index) => (
                        <Badge key={index} color="blue" size="sm">
                          {email}
                        </Badge>
                      ))}
                    </div>
                  </div>
                )}

                <Button
                  onClick={() => void handleTestEmail()}
                  disabled={testingEmail || !config.notification_enabled}
                  className="mt-3 bg-blue-600 text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50"
                  size="sm"
                >
                  {testingEmail ? (
                    <>
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                      Sending...
                    </>
                  ) : (
                    <>
                      <Send className="mr-2 h-4 w-4" />
                      Send Test Email
                    </>
                  )}
                </Button>
              </div>
            ) : (
              <div className="text-center py-4">
                <Text className="text-gray-500">
                  Email notifications are not configured.
                </Text>
                <Text className="mt-1 text-xs text-gray-600">
                  Set SMTP_HOST, SMTP_FROM_ADDRESS, and optionally SMTP_USER/SMTP_PASSWORD
                  environment variables to enable email notifications.
                </Text>
              </div>
            )}
          </div>

          {/* Webhook Configuration */}
          <div className="rounded-lg border border-gray-800 bg-[#121212] p-4">
            <div className="mb-4 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Webhook className="h-5 w-5 text-purple-400" />
                <Text className="font-medium text-gray-300">Webhook</Text>
              </div>
              <Badge
                color={config.webhook_configured ? 'green' : 'gray'}
                size="sm"
              >
                {config.webhook_configured ? 'Configured' : 'Not Configured'}
              </Badge>
            </div>

            {config.webhook_configured ? (
              <div className="space-y-3">
                <div className="grid grid-cols-2 gap-4 text-sm">
                  <div className="col-span-2">
                    <Text className="text-gray-500">Webhook URL</Text>
                    <Text className="break-all text-white">
                      {config.default_webhook_url || '-'}
                    </Text>
                  </div>
                  <div>
                    <Text className="text-gray-500">Timeout</Text>
                    <Text className="text-white">
                      {config.webhook_timeout_seconds || 30}s
                    </Text>
                  </div>
                </div>

                <Button
                  onClick={() => void handleTestWebhook()}
                  disabled={testingWebhook || !config.notification_enabled}
                  className="mt-3 bg-purple-600 text-white hover:bg-purple-700 disabled:cursor-not-allowed disabled:opacity-50"
                  size="sm"
                >
                  {testingWebhook ? (
                    <>
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                      Sending...
                    </>
                  ) : (
                    <>
                      <Send className="mr-2 h-4 w-4" />
                      Send Test Webhook
                    </>
                  )}
                </Button>
              </div>
            ) : (
              <div className="text-center py-4">
                <Text className="text-gray-500">
                  Webhook notifications are not configured.
                </Text>
                <Text className="mt-1 text-xs text-gray-600">
                  Set DEFAULT_WEBHOOK_URL environment variable to enable webhook notifications.
                </Text>
              </div>
            )}
          </div>

          {/* Available Channels Summary */}
          <div className="border-t border-gray-800 pt-4">
            <Text className="mb-2 text-sm text-gray-400">Available Notification Channels</Text>
            <div className="flex flex-wrap gap-2">
              {config.available_channels.length > 0 ? (
                config.available_channels.map((channel) => (
                  <Badge key={channel} color="green" size="sm">
                    {channel.toUpperCase()}
                  </Badge>
                ))
              ) : (
                <Text className="text-gray-500 text-sm">
                  No notification channels configured
                </Text>
              )}
            </div>
          </div>

          {/* Configuration Note */}
          <div className="mt-4 rounded-lg border border-yellow-500/30 bg-yellow-500/10 p-4">
            <Text className="text-yellow-400 text-sm">
              <strong>Note:</strong> Notification settings are configured via environment variables.
              Changes require restarting the backend service. See the documentation for available
              configuration options.
            </Text>
          </div>
        </div>
      )}
    </Card>
  );
}
