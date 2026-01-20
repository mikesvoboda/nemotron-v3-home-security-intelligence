import { Dialog, Switch, Transition } from '@headlessui/react';
import { clsx } from 'clsx';
import {
  AlertCircle,
  AlertTriangle,
  Bell,
  Check,
  Clock,
  Edit2,
  Loader2,
  Plus,
  RefreshCw,
  Shield,
  Trash2,
  X,
  Zap,
} from 'lucide-react';
import { Fragment, useCallback, useEffect, useRef, useState } from 'react';

import {
  createAlertRule,
  deleteAlertRule,
  fetchAlertRules,
  fetchCameras,
  fetchSeverityMetadata,
  testAlertRule,
  updateAlertRule,
  type AlertRule,
  type AlertRuleCreate,
  type AlertRuleSchedule,
  type AlertRuleUpdate,
  type AlertSeverity,
  type Camera,
  type RuleTestResponse,
  type SeverityMetadataResponse,
} from '../../services/api';
import {
  validateAlertRuleName,
  validateCooldownSeconds,
  validateMinConfidence,
  validateRiskThreshold,
  VALIDATION_LIMITS,
} from '../../utils/validation';
import ScheduleSelector from '../common/ScheduleSelector';
import SeverityConfigPanel from '../system/SeverityConfigPanel';

// Object types for filtering
const OBJECT_TYPES = ['person', 'vehicle', 'animal', 'package', 'face'];

// Notification channels
const CHANNELS = ['email', 'webhook', 'pushover'];

// Severity colors and icons
const SEVERITY_CONFIG: Record<AlertSeverity, { color: string; bgColor: string; label: string }> = {
  low: { color: 'text-blue-400', bgColor: 'bg-blue-500/10', label: 'Low' },
  medium: { color: 'text-yellow-400', bgColor: 'bg-yellow-500/10', label: 'Medium' },
  high: { color: 'text-orange-400', bgColor: 'bg-orange-500/10', label: 'High' },
  critical: { color: 'text-red-400', bgColor: 'bg-red-500/10', label: 'Critical' },
};

interface AlertRuleFormData {
  name: string;
  description: string;
  enabled: boolean;
  severity: AlertSeverity;
  risk_threshold: number | null;
  object_types: string[];
  camera_ids: string[];
  min_confidence: number | null;
  schedule: AlertRuleSchedule | null;
  cooldown_seconds: number;
  channels: string[];
}

interface FormErrors {
  name?: string;
  risk_threshold?: string;
  min_confidence?: string;
  schedule?: string;
  cooldown_seconds?: string;
}

/**
 * AlertRulesSettings component for managing alert rules
 *
 * Features:
 * - List all alert rules with status indicators
 * - Add new alert rule
 * - Edit existing alert rule
 * - Delete alert rule with confirmation
 * - Toggle rule enabled/disabled
 * - Test rule against recent events
 */
export default function AlertRulesSettings() {
  const [rules, setRules] = useState<AlertRule[]>([]);
  const [cameras, setCameras] = useState<Camera[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [isDeleteModalOpen, setIsDeleteModalOpen] = useState(false);
  const [isTestModalOpen, setIsTestModalOpen] = useState(false);
  const [editingRule, setEditingRule] = useState<AlertRule | null>(null);
  const [deletingRule, setDeletingRule] = useState<AlertRule | null>(null);
  const [testingRule, setTestingRule] = useState<AlertRule | null>(null);
  const [testResult, setTestResult] = useState<RuleTestResponse | null>(null);
  const [testLoading, setTestLoading] = useState(false);
  const [formData, setFormData] = useState<AlertRuleFormData>(getEmptyFormData());
  const [formErrors, setFormErrors] = useState<FormErrors>({});
  const [submitting, setSubmitting] = useState(false);
  const [togglingRuleId, setTogglingRuleId] = useState<string | null>(null);

  // State for camera loading (separate from rules)
  const [camerasLoading, setCamerasLoading] = useState(false);
  const [camerasError, setCamerasError] = useState<string | null>(null);

  // State for severity metadata
  const [severityMetadata, setSeverityMetadata] = useState<SeverityMetadataResponse | null>(null);
  const [severityLoading, setSeverityLoading] = useState(true);
  const [severityError, setSeverityError] = useState<string | null>(null);

  // Local display state for debounced inputs (immediate visual feedback)
  const [localRiskThreshold, setLocalRiskThreshold] = useState<string>('');
  const [localMinConfidence, setLocalMinConfidence] = useState<string>('');

  // Debounce refs for slider inputs
  const riskThresholdTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const minConfidenceTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Sync local state when form data changes (e.g., when editing a rule)
  useEffect(() => {
    setLocalRiskThreshold(formData.risk_threshold?.toString() ?? '');
  }, [formData.risk_threshold]);

  useEffect(() => {
    setLocalMinConfidence(formData.min_confidence?.toString() ?? '');
  }, [formData.min_confidence]);

  // Debounced handlers for risk threshold and confidence inputs (150ms delay)
  // Local state updates immediately for visual feedback, form state is debounced
  const handleRiskThresholdChange = useCallback((value: string) => {
    setLocalRiskThreshold(value);
    if (riskThresholdTimeoutRef.current) {
      clearTimeout(riskThresholdTimeoutRef.current);
    }
    riskThresholdTimeoutRef.current = setTimeout(() => {
      setFormData((prev) => ({
        ...prev,
        risk_threshold: value ? Number(value) : null,
      }));
    }, 150);
  }, []);

  const handleMinConfidenceChange = useCallback((value: string) => {
    setLocalMinConfidence(value);
    if (minConfidenceTimeoutRef.current) {
      clearTimeout(minConfidenceTimeoutRef.current);
    }
    minConfidenceTimeoutRef.current = setTimeout(() => {
      setFormData((prev) => ({
        ...prev,
        min_confidence: value ? Number(value) : null,
      }));
    }, 150);
  }, []);

  // Cleanup debounce timeouts on unmount
  useEffect(() => {
    return () => {
      if (riskThresholdTimeoutRef.current) {
        clearTimeout(riskThresholdTimeoutRef.current);
      }
      if (minConfidenceTimeoutRef.current) {
        clearTimeout(minConfidenceTimeoutRef.current);
      }
    };
  }, []);

  // Load rules and cameras on mount
  useEffect(() => {
    void loadData();
    // eslint-disable-next-line react-hooks/exhaustive-deps -- mount-only effect: loadData recreated on each render but should only run once
  }, []);

  // Fetch severity metadata
  useEffect(() => {
    async function loadSeverityMetadata() {
      setSeverityLoading(true);
      setSeverityError(null);

      try {
        const data = await fetchSeverityMetadata();
        setSeverityMetadata(data);
      } catch (err) {
        console.error('Failed to load severity metadata:', err);
        setSeverityError(err instanceof Error ? err.message : 'Failed to load severity metadata');
      } finally {
        setSeverityLoading(false);
      }
    }

    void loadSeverityMetadata();
  }, []);

  function getEmptyFormData(): AlertRuleFormData {
    return {
      name: '',
      description: '',
      enabled: true,
      severity: 'medium',
      risk_threshold: null,
      object_types: [],
      camera_ids: [],
      min_confidence: null,
      schedule: null,
      cooldown_seconds: 300,
      channels: [],
    };
  }

  const loadData = async () => {
    try {
      setLoading(true);
      setError(null);
      setCamerasError(null);

      // Fetch rules first (required) - cameras can fail independently
      const rulesData = await fetchAlertRules();
      setRules(rulesData.items);

      // Fetch cameras separately - don't block on failure
      await loadCameras();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load data');
    } finally {
      setLoading(false);
    }
  };

  const loadCameras = async () => {
    try {
      setCamerasLoading(true);
      setCamerasError(null);
      const camerasData = await fetchCameras();
      setCameras(camerasData);
    } catch (err) {
      console.error('Failed to load cameras:', err);
      setCamerasError(err instanceof Error ? err.message : 'Failed to load cameras');
    } finally {
      setCamerasLoading(false);
    }
  };

  const validateForm = (data: AlertRuleFormData): FormErrors => {
    const errors: FormErrors = {};

    // Validate name using centralized validation (aligned with backend)
    const nameResult = validateAlertRuleName(data.name);
    if (!nameResult.isValid) {
      errors.name = nameResult.error;
    }

    // Validate risk threshold using centralized validation (aligned with backend)
    const riskResult = validateRiskThreshold(data.risk_threshold);
    if (!riskResult.isValid) {
      errors.risk_threshold = riskResult.error;
    }

    // Validate min confidence using centralized validation (aligned with backend)
    const confidenceResult = validateMinConfidence(data.min_confidence);
    if (!confidenceResult.isValid) {
      errors.min_confidence = confidenceResult.error;
    }

    if (data.schedule) {
      if (!data.schedule.start_time || !data.schedule.end_time) {
        errors.schedule = 'Start and end times are required when schedule is enabled';
      }
    }

    // Validate cooldown using centralized validation (aligned with backend)
    const cooldownResult = validateCooldownSeconds(data.cooldown_seconds);
    if (!cooldownResult.isValid) {
      errors.cooldown_seconds = cooldownResult.error;
    }

    return errors;
  };

  const handleOpenAddModal = () => {
    setEditingRule(null);
    setFormData(getEmptyFormData());
    setFormErrors({});
    setIsModalOpen(true);
  };

  const handleOpenEditModal = (rule: AlertRule) => {
    setEditingRule(rule);
    setFormData({
      name: rule.name,
      description: rule.description || '',
      enabled: rule.enabled,
      severity: rule.severity,
      risk_threshold: rule.risk_threshold ?? null,
      object_types: rule.object_types || [],
      camera_ids: rule.camera_ids || [],
      min_confidence: rule.min_confidence ?? null,
      schedule: rule.schedule || null,
      cooldown_seconds: rule.cooldown_seconds,
      channels: rule.channels || [],
    });
    setFormErrors({});
    setIsModalOpen(true);
  };

  const handleCloseModal = () => {
    setIsModalOpen(false);
    setEditingRule(null);
    setFormData(getEmptyFormData());
    setFormErrors({});
  };

  const handleOpenDeleteModal = (rule: AlertRule) => {
    setDeletingRule(rule);
    setIsDeleteModalOpen(true);
  };

  const handleCloseDeleteModal = () => {
    setIsDeleteModalOpen(false);
    setDeletingRule(null);
  };

  const handleOpenTestModal = async (rule: AlertRule) => {
    setTestingRule(rule);
    setTestResult(null);
    setIsTestModalOpen(true);
    setTestLoading(true);

    try {
      const result = await testAlertRule(rule.id);
      setTestResult(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to test rule');
    } finally {
      setTestLoading(false);
    }
  };

  const handleCloseTestModal = () => {
    setIsTestModalOpen(false);
    setTestingRule(null);
    setTestResult(null);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    const errors = validateForm(formData);
    if (Object.keys(errors).length > 0) {
      setFormErrors(errors);
      return;
    }

    setSubmitting(true);
    setFormErrors({});

    try {
      if (editingRule) {
        // Update existing rule
        const updateData: AlertRuleUpdate = {
          name: formData.name.trim(),
          description: formData.description.trim() || null,
          enabled: formData.enabled,
          severity: formData.severity,
          risk_threshold: formData.risk_threshold,
          object_types: formData.object_types.length > 0 ? formData.object_types : null,
          camera_ids: formData.camera_ids.length > 0 ? formData.camera_ids : null,
          min_confidence: formData.min_confidence,
          schedule: formData.schedule,
          cooldown_seconds: formData.cooldown_seconds,
          channels: formData.channels.length > 0 ? formData.channels : null,
        };
        await updateAlertRule(editingRule.id, updateData);
      } else {
        // Create new rule
        const createData: AlertRuleCreate = {
          name: formData.name.trim(),
          description: formData.description.trim() || null,
          enabled: formData.enabled,
          severity: formData.severity,
          risk_threshold: formData.risk_threshold,
          object_types: formData.object_types.length > 0 ? formData.object_types : null,
          camera_ids: formData.camera_ids.length > 0 ? formData.camera_ids : null,
          min_confidence: formData.min_confidence,
          schedule: formData.schedule,
          cooldown_seconds: formData.cooldown_seconds,
          channels: formData.channels,
          dedup_key_template: '{camera_id}:{rule_id}',
        };
        await createAlertRule(createData);
      }

      // Reload rules and close modal
      await loadData();
      handleCloseModal();
    } catch (err) {
      setFormErrors({
        name: err instanceof Error ? err.message : 'Failed to save rule',
      });
    } finally {
      setSubmitting(false);
    }
  };

  const handleDelete = async () => {
    if (!deletingRule) return;

    setSubmitting(true);

    try {
      await deleteAlertRule(deletingRule.id);
      await loadData();
      handleCloseDeleteModal();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete rule');
      handleCloseDeleteModal();
    } finally {
      setSubmitting(false);
    }
  };

  const handleToggleEnabled = async (rule: AlertRule) => {
    setTogglingRuleId(rule.id);
    try {
      await updateAlertRule(rule.id, { enabled: !rule.enabled });
      await loadData();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to toggle rule');
    } finally {
      setTogglingRuleId(null);
    }
  };

  const formatSchedule = (schedule: AlertRuleSchedule | null | undefined): string => {
    if (!schedule) return 'Always active';
    const days =
      (schedule.days?.length ?? 0) > 0
        ? (schedule.days?.map((d) => d.charAt(0).toUpperCase() + d.slice(1, 3)).join(', ') ??
          'All days')
        : 'All days';
    const times =
      schedule.start_time && schedule.end_time
        ? `${schedule.start_time} - ${schedule.end_time}`
        : '';
    return times ? `${days}, ${times}` : days;
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="mr-2 h-5 w-5 animate-spin text-gray-400" />
        <span className="text-text-secondary">Loading alert rules...</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-lg border border-red-500/20 bg-red-500/10 p-4">
        <div className="flex items-start gap-3">
          <AlertCircle className="h-5 w-5 text-red-500" />
          <div>
            <h3 className="font-semibold text-red-500">Error loading alert rules</h3>
            <p className="mt-1 text-sm text-red-400">{error}</p>
            <button
              onClick={() => {
                void loadData();
              }}
              className="mt-2 text-sm font-medium text-red-500 hover:text-red-400"
            >
              Try again
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Severity Configuration Panel */}
      <SeverityConfigPanel
        data={severityMetadata}
        loading={severityLoading}
        error={severityError}
        data-testid="severity-config-panel-section"
      />

      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-text-primary">Alert Rules</h2>
          <p className="mt-1 text-sm text-text-secondary">
            Configure custom alert rules for security events
          </p>
        </div>
        <button
          onClick={handleOpenAddModal}
          className="inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 font-medium text-gray-900 transition-all hover:bg-primary-400 hover:shadow-nvidia-glow focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-2 focus:ring-offset-background"
        >
          <Plus className="h-4 w-4" />
          Add Rule
        </button>
      </div>

      {/* Rules Table */}
      {rules.length === 0 ? (
        <div className="rounded-lg border border-gray-800 bg-card p-8 text-center">
          <Shield className="mx-auto h-12 w-12 text-gray-600" />
          <h3 className="mt-4 text-lg font-medium text-text-primary">No alert rules configured</h3>
          <p className="mt-2 text-sm text-text-secondary">
            Create your first alert rule to get notified about security events
          </p>
          <button
            onClick={handleOpenAddModal}
            className="mt-4 inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 font-medium text-gray-900 transition-all hover:bg-primary-400 focus:outline-none focus:ring-2 focus:ring-primary"
          >
            <Plus className="h-4 w-4" />
            Add Rule
          </button>
        </div>
      ) : (
        <div className="overflow-hidden rounded-lg border border-gray-800">
          <table className="w-full">
            <thead className="bg-gray-900">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-text-secondary">
                  Enabled
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-text-secondary">
                  Name
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-text-secondary">
                  Severity
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-text-secondary">
                  Schedule
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-text-secondary">
                  Channels
                </th>
                <th className="px-6 py-3 text-right text-xs font-medium uppercase tracking-wider text-text-secondary">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-800 bg-card">
              {rules.map((rule) => {
                const severityConfig = SEVERITY_CONFIG[rule.severity];
                return (
                  <tr key={rule.id} className="hover:bg-gray-900/50">
                    <td className="whitespace-nowrap px-6 py-4">
                      <Switch
                        checked={rule.enabled}
                        onChange={() => void handleToggleEnabled(rule)}
                        disabled={togglingRuleId === rule.id}
                        aria-label={`Toggle ${rule.name} rule ${rule.enabled ? 'off' : 'on'}`}
                        className={clsx(
                          'relative inline-flex h-6 w-11 items-center rounded-full transition-colors focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-2 focus:ring-offset-background',
                          rule.enabled ? 'bg-primary' : 'bg-gray-600'
                        )}
                      >
                        <span
                          className={clsx(
                            'inline-block h-4 w-4 transform rounded-full bg-white transition-transform',
                            rule.enabled ? 'translate-x-6' : 'translate-x-1'
                          )}
                        />
                      </Switch>
                    </td>
                    <td className="whitespace-nowrap px-6 py-4">
                      <div className="flex flex-col">
                        <span className="font-medium text-text-primary">{rule.name}</span>
                        {rule.description && (
                          <span className="text-xs text-text-secondary">{rule.description}</span>
                        )}
                      </div>
                    </td>
                    <td className="whitespace-nowrap px-6 py-4">
                      <span
                        className={clsx(
                          'inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium',
                          severityConfig.bgColor,
                          severityConfig.color
                        )}
                      >
                        {severityConfig.label}
                      </span>
                    </td>
                    <td className="whitespace-nowrap px-6 py-4">
                      <div className="flex items-center gap-1.5 text-sm text-text-secondary">
                        <Clock className="h-3.5 w-3.5" />
                        <span>{formatSchedule(rule.schedule)}</span>
                      </div>
                    </td>
                    <td className="whitespace-nowrap px-6 py-4">
                      <div className="flex flex-wrap gap-1">
                        {rule.channels && rule.channels.length > 0 ? (
                          rule.channels.map((channel) => (
                            <span
                              key={channel}
                              className="rounded bg-gray-700 px-1.5 py-0.5 text-xs text-text-secondary"
                            >
                              {channel}
                            </span>
                          ))
                        ) : (
                          <span className="text-xs text-gray-500">None</span>
                        )}
                      </div>
                    </td>
                    <td className="whitespace-nowrap px-6 py-4 text-right">
                      <div className="flex items-center justify-end gap-2">
                        <button
                          onClick={() => void handleOpenTestModal(rule)}
                          className="rounded p-1.5 text-gray-400 transition-colors hover:bg-gray-800 hover:text-primary focus:outline-none focus:ring-2 focus:ring-primary"
                          aria-label={`Test ${rule.name}`}
                          title="Test rule"
                        >
                          <Zap className="h-4 w-4" />
                        </button>
                        <button
                          onClick={() => handleOpenEditModal(rule)}
                          className="rounded p-1.5 text-gray-400 transition-colors hover:bg-gray-800 hover:text-primary focus:outline-none focus:ring-2 focus:ring-primary"
                          aria-label={`Edit ${rule.name}`}
                        >
                          <Edit2 className="h-4 w-4" />
                        </button>
                        <button
                          onClick={() => handleOpenDeleteModal(rule)}
                          className="rounded p-1.5 text-gray-400 transition-colors hover:bg-gray-800 hover:text-red-500 focus:outline-none focus:ring-2 focus:ring-red-500"
                          aria-label={`Delete ${rule.name}`}
                        >
                          <Trash2 className="h-4 w-4" />
                        </button>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* Add/Edit Rule Modal */}
      <Transition appear show={isModalOpen} as={Fragment}>
        <Dialog as="div" className="relative z-50" onClose={handleCloseModal}>
          <Transition.Child
            as={Fragment}
            enter="ease-out duration-300"
            enterFrom="opacity-0"
            enterTo="opacity-100"
            leave="ease-in duration-200"
            leaveFrom="opacity-100"
            leaveTo="opacity-0"
          >
            <div className="fixed inset-0 bg-black/50 backdrop-blur-sm" />
          </Transition.Child>

          <div className="fixed inset-0 overflow-y-auto">
            <div className="flex min-h-full items-center justify-center p-4">
              <Transition.Child
                as={Fragment}
                enter="ease-out duration-300"
                enterFrom="opacity-0 scale-95"
                enterTo="opacity-100 scale-100"
                leave="ease-in duration-200"
                leaveFrom="opacity-100 scale-100"
                leaveTo="opacity-0 scale-95"
              >
                <Dialog.Panel className="w-full max-w-2xl transform overflow-hidden rounded-lg border border-gray-800 bg-panel shadow-dark-xl transition-all">
                  <div className="flex items-center justify-between border-b border-gray-800 p-6">
                    <Dialog.Title className="text-xl font-bold text-text-primary">
                      {editingRule ? 'Edit Alert Rule' : 'Add Alert Rule'}
                    </Dialog.Title>
                    <button
                      onClick={handleCloseModal}
                      className="rounded p-1 text-gray-400 transition-colors hover:bg-gray-800 hover:text-text-primary focus:outline-none"
                      aria-label="Close modal"
                    >
                      <X className="h-5 w-5" />
                    </button>
                  </div>

                  <form
                    onSubmit={(e) => {
                      void handleSubmit(e);
                    }}
                    className="max-h-[70vh] overflow-y-auto p-6"
                  >
                    <div className="space-y-6">
                      {/* Basic Info Section */}
                      <div className="space-y-4">
                        <h3 className="flex items-center gap-2 text-sm font-semibold text-text-primary">
                          <Bell className="h-4 w-4 text-primary" />
                          Basic Information
                        </h3>

                        {/* Name */}
                        <div>
                          <label
                            htmlFor="name"
                            className="block text-sm font-medium text-text-primary"
                          >
                            Rule Name *
                          </label>
                          <input
                            type="text"
                            id="name"
                            value={formData.name}
                            onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                            maxLength={VALIDATION_LIMITS.alertRule.name.maxLength}
                            className={clsx(
                              'mt-1 block w-full rounded-lg border bg-card px-3 py-2 text-text-primary focus:outline-none focus:ring-2',
                              formErrors.name
                                ? 'border-red-500 focus:border-red-500 focus:ring-red-500'
                                : 'border-gray-800 focus:border-primary focus:ring-primary'
                            )}
                            placeholder="Night Intruder Alert"
                          />
                          {formErrors.name && (
                            <p className="mt-1 text-sm text-red-500">{formErrors.name}</p>
                          )}
                        </div>

                        {/* Description */}
                        <div>
                          <label
                            htmlFor="description"
                            className="block text-sm font-medium text-text-primary"
                          >
                            Description
                          </label>
                          <textarea
                            id="description"
                            value={formData.description}
                            onChange={(e) =>
                              setFormData({ ...formData, description: e.target.value })
                            }
                            rows={2}
                            className="mt-1 block w-full rounded-lg border border-gray-800 bg-card px-3 py-2 text-text-primary focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary"
                            placeholder="Alert for detecting people at night"
                          />
                        </div>

                        {/* Enabled & Severity Row */}
                        <div className="grid grid-cols-2 gap-4">
                          <div>
                            <span className="block text-sm font-medium text-text-primary">
                              Status
                            </span>
                            <div className="mt-2 flex items-center gap-2">
                              <Switch
                                checked={formData.enabled}
                                onChange={(checked) =>
                                  setFormData({ ...formData, enabled: checked })
                                }
                                aria-label={`Rule status: ${formData.enabled ? 'enabled' : 'disabled'}`}
                                className={clsx(
                                  'relative inline-flex h-6 w-11 items-center rounded-full transition-colors focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-2 focus:ring-offset-panel',
                                  formData.enabled ? 'bg-primary' : 'bg-gray-600'
                                )}
                              >
                                <span
                                  className={clsx(
                                    'inline-block h-4 w-4 transform rounded-full bg-white transition-transform',
                                    formData.enabled ? 'translate-x-6' : 'translate-x-1'
                                  )}
                                />
                              </Switch>
                              <span className="text-sm text-gray-300">
                                {formData.enabled ? 'Enabled' : 'Disabled'}
                              </span>
                            </div>
                          </div>

                          <div>
                            <label
                              htmlFor="severity"
                              className="block text-sm font-medium text-text-primary"
                            >
                              Severity
                            </label>
                            <select
                              id="severity"
                              value={formData.severity}
                              onChange={(e) =>
                                setFormData({
                                  ...formData,
                                  severity: e.target.value as AlertSeverity,
                                })
                              }
                              className="mt-1 block w-full rounded-lg border border-gray-800 bg-card px-3 py-2 text-text-primary focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary"
                            >
                              <option value="low">Low</option>
                              <option value="medium">Medium</option>
                              <option value="high">High</option>
                              <option value="critical">Critical</option>
                            </select>
                          </div>
                        </div>
                      </div>

                      {/* Conditions Section */}
                      <div className="space-y-4 border-t border-gray-800 pt-6">
                        <h3 className="flex items-center gap-2 text-sm font-semibold text-text-primary">
                          <AlertTriangle className="h-4 w-4 text-primary" />
                          Trigger Conditions
                        </h3>

                        {/* Risk Threshold & Confidence Row */}
                        <div className="grid grid-cols-2 gap-4">
                          <div>
                            <label
                              htmlFor="risk_threshold"
                              className="block text-sm font-medium text-text-primary"
                            >
                              Risk Threshold (0-100)
                            </label>
                            <input
                              type="number"
                              id="risk_threshold"
                              value={localRiskThreshold}
                              onChange={(e) => handleRiskThresholdChange(e.target.value)}
                              min={0}
                              max={100}
                              className={clsx(
                                'mt-1 block w-full rounded-lg border bg-card px-3 py-2 text-text-primary focus:outline-none focus:ring-2',
                                formErrors.risk_threshold
                                  ? 'border-red-500 focus:border-red-500 focus:ring-red-500'
                                  : 'border-gray-800 focus:border-primary focus:ring-primary'
                              )}
                              placeholder="70"
                            />
                            {formErrors.risk_threshold && (
                              <p className="mt-1 text-sm text-red-500">
                                {formErrors.risk_threshold}
                              </p>
                            )}
                          </div>

                          <div>
                            <label
                              htmlFor="min_confidence"
                              className="block text-sm font-medium text-text-primary"
                            >
                              Min Confidence (0-1)
                            </label>
                            <input
                              type="number"
                              id="min_confidence"
                              value={localMinConfidence}
                              onChange={(e) => handleMinConfidenceChange(e.target.value)}
                              min={0}
                              max={1}
                              step={0.1}
                              className={clsx(
                                'mt-1 block w-full rounded-lg border bg-card px-3 py-2 text-text-primary focus:outline-none focus:ring-2',
                                formErrors.min_confidence
                                  ? 'border-red-500 focus:border-red-500 focus:ring-red-500'
                                  : 'border-gray-800 focus:border-primary focus:ring-primary'
                              )}
                              placeholder="0.8"
                            />
                            {formErrors.min_confidence && (
                              <p className="mt-1 text-sm text-red-500">
                                {formErrors.min_confidence}
                              </p>
                            )}
                          </div>
                        </div>

                        {/* Object Types */}
                        <div>
                          <span className="block text-sm font-medium text-text-primary">
                            Object Types
                          </span>
                          <div className="mt-2 flex flex-wrap gap-2">
                            {OBJECT_TYPES.map((type) => (
                              <button
                                key={type}
                                type="button"
                                onClick={() => {
                                  const newTypes = formData.object_types.includes(type)
                                    ? formData.object_types.filter((t) => t !== type)
                                    : [...formData.object_types, type];
                                  setFormData({ ...formData, object_types: newTypes });
                                }}
                                className={clsx(
                                  'rounded-full px-3 py-1 text-sm font-medium transition-colors',
                                  formData.object_types.includes(type)
                                    ? 'bg-primary text-gray-900'
                                    : 'bg-gray-700 text-text-secondary hover:bg-gray-600'
                                )}
                              >
                                {type}
                              </button>
                            ))}
                          </div>
                          <p className="mt-1 text-xs text-text-secondary">
                            Leave empty to match all object types
                          </p>
                        </div>

                        {/* Cameras */}
                        <div>
                          <span className="block text-sm font-medium text-text-primary">
                            Cameras
                          </span>
                          {camerasError ? (
                            <div
                              className="mt-2 rounded-lg border border-red-500/20 bg-red-500/10 p-3"
                              data-testid="cameras-error"
                            >
                              <div className="flex items-center gap-2">
                                <AlertCircle className="h-4 w-4 text-red-500" />
                                <span className="text-sm text-red-400">
                                  Failed to load cameras.
                                </span>
                                <button
                                  type="button"
                                  onClick={() => {
                                    void loadCameras();
                                  }}
                                  disabled={camerasLoading}
                                  className="inline-flex items-center gap-1 text-sm font-medium text-red-500 hover:text-red-400 disabled:opacity-50"
                                  data-testid="cameras-retry-button"
                                >
                                  {camerasLoading ? (
                                    <Loader2 className="h-3 w-3 animate-spin" />
                                  ) : (
                                    <RefreshCw className="h-3 w-3" />
                                  )}
                                  Retry
                                </button>
                              </div>
                            </div>
                          ) : camerasLoading ? (
                            <div className="mt-2 flex items-center gap-2 text-sm text-text-secondary">
                              <Loader2 className="h-4 w-4 animate-spin" />
                              Loading cameras...
                            </div>
                          ) : cameras.length === 0 ? (
                            <div className="mt-2 text-sm text-text-secondary">
                              No cameras available
                            </div>
                          ) : (
                            <div className="mt-2 flex flex-wrap gap-2">
                              {cameras.map((camera) => (
                                <button
                                  key={camera.id}
                                  type="button"
                                  onClick={() => {
                                    const newCameras = formData.camera_ids.includes(camera.id)
                                      ? formData.camera_ids.filter((c) => c !== camera.id)
                                      : [...formData.camera_ids, camera.id];
                                    setFormData({ ...formData, camera_ids: newCameras });
                                  }}
                                  className={clsx(
                                    'rounded-full px-3 py-1 text-sm font-medium transition-colors',
                                    formData.camera_ids.includes(camera.id)
                                      ? 'bg-primary text-gray-900'
                                      : 'bg-gray-700 text-text-secondary hover:bg-gray-600'
                                  )}
                                >
                                  {camera.name}
                                </button>
                              ))}
                            </div>
                          )}
                          <p className="mt-1 text-xs text-text-secondary">
                            Leave empty to match all cameras
                          </p>
                        </div>
                      </div>

                      {/* Schedule Section */}
                      <div className="border-t border-gray-800 pt-6">
                        <ScheduleSelector
                          value={formData.schedule}
                          onChange={(schedule) => setFormData({ ...formData, schedule })}
                          disabled={submitting}
                        />
                        {formErrors.schedule && (
                          <p className="mt-2 text-sm text-red-500">{formErrors.schedule}</p>
                        )}
                      </div>

                      {/* Notification Section */}
                      <div className="space-y-4 border-t border-gray-800 pt-6">
                        <h3 className="flex items-center gap-2 text-sm font-semibold text-text-primary">
                          <Bell className="h-4 w-4 text-primary" />
                          Notifications
                        </h3>

                        {/* Channels */}
                        <div>
                          <span className="block text-sm font-medium text-text-primary">
                            Notification Channels
                          </span>
                          <div className="mt-2 flex flex-wrap gap-2">
                            {CHANNELS.map((channel) => (
                              <button
                                key={channel}
                                type="button"
                                onClick={() => {
                                  const newChannels = formData.channels.includes(channel)
                                    ? formData.channels.filter((c) => c !== channel)
                                    : [...formData.channels, channel];
                                  setFormData({ ...formData, channels: newChannels });
                                }}
                                className={clsx(
                                  'rounded-full px-3 py-1 text-sm font-medium transition-colors',
                                  formData.channels.includes(channel)
                                    ? 'bg-primary text-gray-900'
                                    : 'bg-gray-700 text-text-secondary hover:bg-gray-600'
                                )}
                              >
                                {channel}
                              </button>
                            ))}
                          </div>
                        </div>

                        {/* Cooldown */}
                        <div>
                          <label
                            htmlFor="cooldown"
                            className="block text-sm font-medium text-text-primary"
                          >
                            Cooldown (seconds)
                          </label>
                          <input
                            type="number"
                            id="cooldown"
                            value={formData.cooldown_seconds}
                            onChange={(e) =>
                              setFormData({
                                ...formData,
                                cooldown_seconds: Number(e.target.value),
                              })
                            }
                            min={0}
                            className={clsx(
                              'mt-1 block w-full rounded-lg border bg-card px-3 py-2 text-text-primary focus:outline-none focus:ring-2',
                              formErrors.cooldown_seconds
                                ? 'border-red-500 focus:border-red-500 focus:ring-red-500'
                                : 'border-gray-800 focus:border-primary focus:ring-primary'
                            )}
                            placeholder="300"
                          />
                          <p className="mt-1 text-xs text-text-secondary">
                            Minimum seconds between duplicate alerts
                          </p>
                          {formErrors.cooldown_seconds && (
                            <p className="mt-1 text-sm text-red-500">
                              {formErrors.cooldown_seconds}
                            </p>
                          )}
                        </div>
                      </div>
                    </div>

                    {/* Action Buttons */}
                    <div className="mt-6 flex justify-end gap-3 border-t border-gray-800 pt-6">
                      <button
                        type="button"
                        onClick={handleCloseModal}
                        disabled={submitting}
                        className="rounded-lg border border-gray-700 px-4 py-2 font-medium text-text-primary transition-colors hover:bg-gray-800 focus:outline-none focus:ring-2 focus:ring-gray-700 disabled:opacity-50"
                      >
                        Cancel
                      </button>
                      <button
                        type="submit"
                        disabled={submitting}
                        className="inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 font-medium text-gray-900 transition-all hover:bg-primary-400 hover:shadow-nvidia-glow focus:outline-none focus:ring-2 focus:ring-primary disabled:opacity-50"
                      >
                        {submitting && <Loader2 className="h-4 w-4 animate-spin" />}
                        {submitting ? 'Saving...' : editingRule ? 'Update Rule' : 'Add Rule'}
                      </button>
                    </div>
                  </form>
                </Dialog.Panel>
              </Transition.Child>
            </div>
          </div>
        </Dialog>
      </Transition>

      {/* Delete Confirmation Modal */}
      <Transition appear show={isDeleteModalOpen} as={Fragment}>
        <Dialog as="div" className="relative z-50" onClose={handleCloseDeleteModal}>
          <Transition.Child
            as={Fragment}
            enter="ease-out duration-300"
            enterFrom="opacity-0"
            enterTo="opacity-100"
            leave="ease-in duration-200"
            leaveFrom="opacity-100"
            leaveTo="opacity-0"
          >
            <div className="fixed inset-0 bg-black/50 backdrop-blur-sm" />
          </Transition.Child>

          <div className="fixed inset-0 overflow-y-auto">
            <div className="flex min-h-full items-center justify-center p-4">
              <Transition.Child
                as={Fragment}
                enter="ease-out duration-300"
                enterFrom="opacity-0 scale-95"
                enterTo="opacity-100 scale-100"
                leave="ease-in duration-200"
                leaveFrom="opacity-100 scale-100"
                leaveTo="opacity-0 scale-95"
              >
                <Dialog.Panel className="w-full max-w-md transform overflow-hidden rounded-lg border border-gray-800 bg-panel p-6 shadow-dark-xl transition-all">
                  <div className="flex items-start gap-4">
                    <div className="flex h-10 w-10 items-center justify-center rounded-full bg-red-500/10">
                      <AlertCircle className="h-6 w-6 text-red-500" />
                    </div>
                    <div className="flex-1">
                      <Dialog.Title className="text-lg font-semibold text-text-primary">
                        Delete Alert Rule
                      </Dialog.Title>
                      <p className="mt-2 text-sm text-text-secondary">
                        Are you sure you want to delete{' '}
                        <span className="font-medium text-text-primary">{deletingRule?.name}</span>?
                        This action cannot be undone.
                      </p>
                    </div>
                  </div>

                  <div className="mt-6 flex justify-end gap-3">
                    <button
                      type="button"
                      onClick={handleCloseDeleteModal}
                      disabled={submitting}
                      className="rounded-lg border border-gray-700 px-4 py-2 font-medium text-text-primary transition-colors hover:bg-gray-800 focus:outline-none focus:ring-2 focus:ring-gray-700 disabled:opacity-50"
                    >
                      Cancel
                    </button>
                    <button
                      type="button"
                      onClick={() => {
                        void handleDelete();
                      }}
                      disabled={submitting}
                      className="inline-flex items-center gap-2 rounded-lg bg-red-700 px-4 py-2 font-medium text-white transition-all hover:bg-red-800 focus:outline-none focus:ring-2 focus:ring-red-700 disabled:opacity-50"
                    >
                      {submitting && <Loader2 className="h-4 w-4 animate-spin" />}
                      {submitting ? 'Deleting...' : 'Delete Rule'}
                    </button>
                  </div>
                </Dialog.Panel>
              </Transition.Child>
            </div>
          </div>
        </Dialog>
      </Transition>

      {/* Test Rule Modal */}
      <Transition appear show={isTestModalOpen} as={Fragment}>
        <Dialog as="div" className="relative z-50" onClose={handleCloseTestModal}>
          <Transition.Child
            as={Fragment}
            enter="ease-out duration-300"
            enterFrom="opacity-0"
            enterTo="opacity-100"
            leave="ease-in duration-200"
            leaveFrom="opacity-100"
            leaveTo="opacity-0"
          >
            <div className="fixed inset-0 bg-black/50 backdrop-blur-sm" />
          </Transition.Child>

          <div className="fixed inset-0 overflow-y-auto">
            <div className="flex min-h-full items-center justify-center p-4">
              <Transition.Child
                as={Fragment}
                enter="ease-out duration-300"
                enterFrom="opacity-0 scale-95"
                enterTo="opacity-100 scale-100"
                leave="ease-in duration-200"
                leaveFrom="opacity-100 scale-100"
                leaveTo="opacity-0 scale-95"
              >
                <Dialog.Panel className="w-full max-w-lg transform overflow-hidden rounded-lg border border-gray-800 bg-panel shadow-dark-xl transition-all">
                  <div className="flex items-center justify-between border-b border-gray-800 p-6">
                    <Dialog.Title className="text-xl font-bold text-text-primary">
                      Test Rule: {testingRule?.name}
                    </Dialog.Title>
                    <button
                      onClick={handleCloseTestModal}
                      className="rounded p-1 text-gray-400 transition-colors hover:bg-gray-800 hover:text-text-primary focus:outline-none"
                      aria-label="Close modal"
                    >
                      <X className="h-5 w-5" />
                    </button>
                  </div>

                  <div className="p-6">
                    {testLoading ? (
                      <div className="flex items-center justify-center py-8">
                        <Loader2 className="mr-2 h-6 w-6 animate-spin text-primary" />
                        <span className="text-text-secondary">
                          Testing rule against recent events...
                        </span>
                      </div>
                    ) : testResult ? (
                      <div className="space-y-4">
                        {/* Summary */}
                        <div className="grid grid-cols-3 gap-4">
                          <div className="rounded-lg border border-gray-800 bg-card p-3 text-center">
                            <p className="text-2xl font-bold text-text-primary">
                              {testResult.events_tested}
                            </p>
                            <p className="text-xs text-text-secondary">Events Tested</p>
                          </div>
                          <div className="rounded-lg border border-gray-800 bg-card p-3 text-center">
                            <p className="text-2xl font-bold text-green-400">
                              {testResult.events_matched}
                            </p>
                            <p className="text-xs text-text-secondary">Matched</p>
                          </div>
                          <div className="rounded-lg border border-gray-800 bg-card p-3 text-center">
                            <p className="text-2xl font-bold text-text-primary">
                              {((testResult.match_rate ?? 0) * 100).toFixed(0)}%
                            </p>
                            <p className="text-xs text-text-secondary">Match Rate</p>
                          </div>
                        </div>

                        {/* Results */}
                        {testResult.results.length > 0 && (
                          <div className="space-y-2">
                            <h4 className="text-sm font-semibold text-text-primary">
                              Event Results
                            </h4>
                            <div className="max-h-60 space-y-2 overflow-y-auto">
                              {testResult.results.map((result) => (
                                <div
                                  key={result.event_id}
                                  className={clsx(
                                    'rounded-lg border p-3',
                                    result.matches
                                      ? 'border-green-500/30 bg-green-500/10'
                                      : 'border-gray-800 bg-card'
                                  )}
                                >
                                  <div className="flex items-center justify-between">
                                    <div className="flex items-center gap-2">
                                      {result.matches ? (
                                        <Check className="h-4 w-4 text-green-400" />
                                      ) : (
                                        <X className="h-4 w-4 text-gray-500" />
                                      )}
                                      <span className="text-sm font-medium text-text-primary">
                                        Event #{result.event_id}
                                      </span>
                                    </div>
                                    <span className="text-xs text-text-secondary">
                                      {result.camera_id}
                                    </span>
                                  </div>
                                  <div className="mt-1 flex items-center gap-4 text-xs text-text-secondary">
                                    <span>Risk: {result.risk_score ?? 'N/A'}</span>
                                    <span>Objects: {result.object_types.join(', ') || 'None'}</span>
                                  </div>
                                  {result.matches && result.matched_conditions.length > 0 && (
                                    <div className="mt-2 text-xs text-green-400">
                                      Matched: {result.matched_conditions.join(', ')}
                                    </div>
                                  )}
                                </div>
                              ))}
                            </div>
                          </div>
                        )}

                        {testResult.events_tested === 0 && (
                          <div className="py-4 text-center text-text-secondary">
                            No recent events to test against
                          </div>
                        )}
                      </div>
                    ) : null}
                  </div>

                  <div className="border-t border-gray-800 p-6">
                    <button
                      onClick={handleCloseTestModal}
                      className="w-full rounded-lg border border-gray-700 px-4 py-2 font-medium text-text-primary transition-colors hover:bg-gray-800 focus:outline-none focus:ring-2 focus:ring-gray-700"
                    >
                      Close
                    </button>
                  </div>
                </Dialog.Panel>
              </Transition.Child>
            </div>
          </div>
        </Dialog>
      </Transition>
    </div>
  );
}
