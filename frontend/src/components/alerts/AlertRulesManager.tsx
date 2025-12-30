import { Dialog, Transition, Switch } from '@headlessui/react';
import { clsx } from 'clsx';
import {
  AlertCircle,
  Bell,
  Clock,
  Edit2,
  Filter,
  Plus,
  RefreshCw,
  Settings2,
  Trash2,
  X,
} from 'lucide-react';
import { Fragment, useEffect, useState, useCallback } from 'react';

import {
  createAlertRule,
  deleteAlertRule,
  fetchAlertRules,
  updateAlertRule,
  type AlertRule,
  type AlertRuleCreate,
  type AlertRuleUpdate,
  type AlertSeverity,
} from '../../services/api';

// ============================================================================
// Types
// ============================================================================

interface RuleFormData {
  name: string;
  description: string;
  enabled: boolean;
  severity: AlertSeverity;
  risk_threshold: string;
  object_types: string;
  camera_ids: string;
  min_confidence: string;
  cooldown_seconds: string;
  channels: string;
}

interface RuleFormErrors {
  name?: string;
  risk_threshold?: string;
  min_confidence?: string;
  cooldown_seconds?: string;
  general?: string;
}

export interface AlertRulesManagerProps {
  className?: string;
}

// ============================================================================
// Constants
// ============================================================================

const SEVERITY_OPTIONS: { value: AlertSeverity; label: string; color: string }[] = [
  { value: 'low', label: 'Low', color: 'bg-green-500' },
  { value: 'medium', label: 'Medium', color: 'bg-yellow-500' },
  { value: 'high', label: 'High', color: 'bg-orange-500' },
  { value: 'critical', label: 'Critical', color: 'bg-red-500' },
];

const OBJECT_TYPE_OPTIONS = ['person', 'vehicle', 'animal', 'package'];

const DEFAULT_FORM_DATA: RuleFormData = {
  name: '',
  description: '',
  enabled: true,
  severity: 'medium',
  risk_threshold: '',
  object_types: '',
  camera_ids: '',
  min_confidence: '',
  cooldown_seconds: '300',
  channels: '',
};

// ============================================================================
// Helper Functions
// ============================================================================

function getSeverityBadgeColor(severity: AlertSeverity): string {
  switch (severity) {
    case 'critical':
      return 'bg-red-500/20 text-red-400 border-red-500/30';
    case 'high':
      return 'bg-orange-500/20 text-orange-400 border-orange-500/30';
    case 'medium':
      return 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30';
    case 'low':
      return 'bg-green-500/20 text-green-400 border-green-500/30';
    default:
      return 'bg-gray-500/20 text-gray-400 border-gray-500/30';
  }
}

function formatCooldown(seconds: number): string {
  if (seconds < 60) return `${seconds}s`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m`;
  return `${Math.floor(seconds / 3600)}h`;
}

function ruleToFormData(rule: AlertRule): RuleFormData {
  return {
    name: rule.name,
    description: rule.description || '',
    enabled: rule.enabled,
    severity: rule.severity,
    risk_threshold: rule.risk_threshold?.toString() || '',
    object_types: rule.object_types?.join(', ') || '',
    camera_ids: rule.camera_ids?.join(', ') || '',
    min_confidence: rule.min_confidence ? (rule.min_confidence * 100).toString() : '',
    cooldown_seconds: rule.cooldown_seconds.toString(),
    channels: rule.channels?.join(', ') || '',
  };
}

function formDataToCreate(data: RuleFormData): AlertRuleCreate {
  const result: AlertRuleCreate = {
    name: data.name.trim(),
    enabled: data.enabled,
    severity: data.severity,
    cooldown_seconds: parseInt(data.cooldown_seconds, 10) || 300,
  };

  if (data.description.trim()) {
    result.description = data.description.trim();
  }

  if (data.risk_threshold.trim()) {
    result.risk_threshold = parseInt(data.risk_threshold, 10);
  }

  if (data.object_types.trim()) {
    result.object_types = data.object_types
      .split(',')
      .map((s) => s.trim())
      .filter(Boolean);
  }

  if (data.camera_ids.trim()) {
    result.camera_ids = data.camera_ids
      .split(',')
      .map((s) => s.trim())
      .filter(Boolean);
  }

  if (data.min_confidence.trim()) {
    result.min_confidence = parseFloat(data.min_confidence) / 100;
  }

  if (data.channels.trim()) {
    result.channels = data.channels
      .split(',')
      .map((s) => s.trim())
      .filter(Boolean);
  }

  return result;
}

function formDataToUpdate(data: RuleFormData): AlertRuleUpdate {
  return formDataToCreate(data) as AlertRuleUpdate;
}

// ============================================================================
// Component
// ============================================================================

/**
 * AlertRulesManager component for managing alert rules
 * Features:
 * - List all alert rules with status indicators
 * - Add new rule with conditions
 * - Edit existing rules
 * - Enable/disable rules via toggle
 * - Delete rules with confirmation
 */
export default function AlertRulesManager({ className = '' }: AlertRulesManagerProps) {
  // State for rules data
  const [rules, setRules] = useState<AlertRule[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Modal states
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [isDeleteModalOpen, setIsDeleteModalOpen] = useState(false);
  const [editingRule, setEditingRule] = useState<AlertRule | null>(null);
  const [deletingRule, setDeletingRule] = useState<AlertRule | null>(null);

  // Form state
  const [formData, setFormData] = useState<RuleFormData>(DEFAULT_FORM_DATA);
  const [formErrors, setFormErrors] = useState<RuleFormErrors>({});
  const [submitting, setSubmitting] = useState(false);

  // Load rules
  const loadRules = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const response = await fetchAlertRules({ limit: 100 });
      setRules(response.rules);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load alert rules');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadRules();
  }, [loadRules]);

  // Form validation
  const validateForm = (data: RuleFormData): RuleFormErrors => {
    const errors: RuleFormErrors = {};

    if (!data.name || data.name.trim().length < 2) {
      errors.name = 'Name must be at least 2 characters';
    }

    if (data.risk_threshold.trim()) {
      const threshold = parseInt(data.risk_threshold, 10);
      if (isNaN(threshold) || threshold < 0 || threshold > 100) {
        errors.risk_threshold = 'Risk threshold must be between 0 and 100';
      }
    }

    if (data.min_confidence.trim()) {
      const confidence = parseFloat(data.min_confidence);
      if (isNaN(confidence) || confidence < 0 || confidence > 100) {
        errors.min_confidence = 'Confidence must be between 0 and 100';
      }
    }

    if (data.cooldown_seconds.trim()) {
      const cooldown = parseInt(data.cooldown_seconds, 10);
      if (isNaN(cooldown) || cooldown < 0) {
        errors.cooldown_seconds = 'Cooldown must be a non-negative number';
      }
    }

    return errors;
  };

  // Modal handlers
  const handleOpenAddModal = () => {
    setEditingRule(null);
    setFormData(DEFAULT_FORM_DATA);
    setFormErrors({});
    setIsModalOpen(true);
  };

  const handleOpenEditModal = (rule: AlertRule) => {
    setEditingRule(rule);
    setFormData(ruleToFormData(rule));
    setFormErrors({});
    setIsModalOpen(true);
  };

  const handleCloseModal = () => {
    setIsModalOpen(false);
    setEditingRule(null);
    setFormData(DEFAULT_FORM_DATA);
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

  // Form submission
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
        await updateAlertRule(editingRule.id, formDataToUpdate(formData));
      } else {
        await createAlertRule(formDataToCreate(formData));
      }

      await loadRules();
      handleCloseModal();
    } catch (err) {
      setFormErrors({
        general: err instanceof Error ? err.message : 'Failed to save rule',
      });
    } finally {
      setSubmitting(false);
    }
  };

  // Delete handler
  const handleDelete = async () => {
    if (!deletingRule) return;

    setSubmitting(true);

    try {
      await deleteAlertRule(deletingRule.id);
      await loadRules();
      handleCloseDeleteModal();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete rule');
      handleCloseDeleteModal();
    } finally {
      setSubmitting(false);
    }
  };

  // Toggle enabled handler
  const handleToggleEnabled = async (rule: AlertRule) => {
    try {
      await updateAlertRule(rule.id, { enabled: !rule.enabled });
      await loadRules();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to update rule');
    }
  };

  // Render loading state
  if (loading) {
    return (
      <div className={`rounded-lg border border-gray-800 bg-[#1F1F1F] p-8 ${className}`}>
        <div className="flex items-center justify-center">
          <div className="h-8 w-8 animate-spin rounded-full border-4 border-gray-700 border-t-[#76B900]" />
          <span className="ml-3 text-gray-400">Loading alert rules...</span>
        </div>
      </div>
    );
  }

  return (
    <div className={`space-y-6 ${className}`}>
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Settings2 className="h-6 w-6 text-[#76B900]" />
          <div>
            <h2 className="text-xl font-bold text-white">Alert Rules</h2>
            <p className="text-sm text-gray-400">Configure automated alert triggers</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => void loadRules()}
            disabled={loading}
            className="inline-flex items-center gap-2 rounded-lg border border-gray-700 px-3 py-2 text-sm font-medium text-gray-300 transition-colors hover:bg-gray-800 disabled:opacity-50"
            aria-label="Refresh rules"
          >
            <RefreshCw className={clsx('h-4 w-4', loading && 'animate-spin')} />
          </button>
          <button
            onClick={handleOpenAddModal}
            className="inline-flex items-center gap-2 rounded-lg bg-[#76B900] px-4 py-2 font-medium text-gray-900 transition-all hover:bg-[#8ed100] hover:shadow-[0_0_20px_rgba(118,185,0,0.3)] focus:outline-none focus:ring-2 focus:ring-[#76B900] focus:ring-offset-2 focus:ring-offset-[#0E0E0E]"
          >
            <Plus className="h-4 w-4" />
            Add Rule
          </button>
        </div>
      </div>

      {/* Error Display */}
      {error && (
        <div className="flex items-center gap-3 rounded-lg border border-red-500/30 bg-red-500/10 p-4">
          <AlertCircle className="h-5 w-5 text-red-500" />
          <span className="text-red-400">{error}</span>
          <button
            onClick={() => setError(null)}
            className="ml-auto rounded p-1 text-red-400 hover:bg-red-500/20"
            aria-label="Dismiss error"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
      )}

      {/* Rules List */}
      {rules.length === 0 ? (
        <div className="rounded-lg border border-gray-800 bg-[#1A1A1A] p-8 text-center">
          <Bell className="mx-auto h-12 w-12 text-gray-600" />
          <h3 className="mt-4 text-lg font-medium text-white">No Alert Rules</h3>
          <p className="mt-2 text-sm text-gray-400">
            Create your first alert rule to get notified about security events.
          </p>
          <button
            onClick={handleOpenAddModal}
            className="mt-4 inline-flex items-center gap-2 rounded-lg bg-[#76B900] px-4 py-2 font-medium text-gray-900 transition-all hover:bg-[#8ed100] focus:outline-none focus:ring-2 focus:ring-[#76B900]"
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
                <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-400">
                  Rule
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-400">
                  Severity
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-400">
                  Conditions
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-400">
                  Cooldown
                </th>
                <th className="px-6 py-3 text-center text-xs font-medium uppercase tracking-wider text-gray-400">
                  Enabled
                </th>
                <th className="px-6 py-3 text-right text-xs font-medium uppercase tracking-wider text-gray-400">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-800 bg-[#1A1A1A]">
              {rules.map((rule) => (
                <tr key={rule.id} className="hover:bg-gray-900/50">
                  <td className="px-6 py-4">
                    <div>
                      <div className="font-medium text-white">{rule.name}</div>
                      {rule.description && (
                        <div className="mt-1 text-sm text-gray-400 line-clamp-1">
                          {rule.description}
                        </div>
                      )}
                    </div>
                  </td>
                  <td className="px-6 py-4">
                    <span
                      className={clsx(
                        'inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium capitalize',
                        getSeverityBadgeColor(rule.severity)
                      )}
                    >
                      {rule.severity}
                    </span>
                  </td>
                  <td className="px-6 py-4">
                    <div className="flex flex-wrap gap-1.5">
                      {rule.risk_threshold !== null && (
                        <span className="inline-flex items-center gap-1 rounded bg-blue-500/10 px-2 py-0.5 text-xs text-blue-400">
                          <Filter className="h-3 w-3" />
                          Risk &ge; {rule.risk_threshold}
                        </span>
                      )}
                      {rule.object_types && rule.object_types.length > 0 && (
                        <span className="inline-flex items-center gap-1 rounded bg-purple-500/10 px-2 py-0.5 text-xs text-purple-400">
                          {rule.object_types.join(', ')}
                        </span>
                      )}
                      {rule.min_confidence !== null && (
                        <span className="inline-flex items-center gap-1 rounded bg-cyan-500/10 px-2 py-0.5 text-xs text-cyan-400">
                          Conf &ge; {Math.round(rule.min_confidence * 100)}%
                        </span>
                      )}
                      {!rule.risk_threshold &&
                        !rule.object_types?.length &&
                        !rule.min_confidence && (
                          <span className="text-xs text-gray-500">No conditions</span>
                        )}
                    </div>
                  </td>
                  <td className="px-6 py-4">
                    <span className="inline-flex items-center gap-1 text-sm text-gray-400">
                      <Clock className="h-3.5 w-3.5" />
                      {formatCooldown(rule.cooldown_seconds)}
                    </span>
                  </td>
                  <td className="px-6 py-4 text-center">
                    <Switch
                      checked={rule.enabled}
                      onChange={() => void handleToggleEnabled(rule)}
                      className={clsx(
                        'relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-[#76B900] focus:ring-offset-2 focus:ring-offset-[#1A1A1A]',
                        rule.enabled ? 'bg-[#76B900]' : 'bg-gray-700'
                      )}
                    >
                      <span
                        className={clsx(
                          'pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out',
                          rule.enabled ? 'translate-x-5' : 'translate-x-0'
                        )}
                      />
                    </Switch>
                  </td>
                  <td className="px-6 py-4 text-right">
                    <div className="flex items-center justify-end gap-2">
                      <button
                        onClick={() => handleOpenEditModal(rule)}
                        className="rounded p-1.5 text-gray-400 transition-colors hover:bg-gray-800 hover:text-[#76B900] focus:outline-none focus:ring-2 focus:ring-[#76B900]"
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
              ))}
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
                <Dialog.Panel className="w-full max-w-lg transform overflow-hidden rounded-lg border border-gray-800 bg-[#1A1A1A] p-6 shadow-xl transition-all">
                  <div className="flex items-center justify-between">
                    <Dialog.Title className="text-xl font-bold text-white">
                      {editingRule ? 'Edit Alert Rule' : 'Add Alert Rule'}
                    </Dialog.Title>
                    <button
                      onClick={handleCloseModal}
                      className="rounded p-1 text-gray-400 transition-colors hover:bg-gray-800 hover:text-white focus:outline-none"
                      aria-label="Close modal"
                    >
                      <X className="h-5 w-5" />
                    </button>
                  </div>

                  {formErrors.general && (
                    <div className="mt-4 flex items-center gap-2 rounded-lg border border-red-500/30 bg-red-500/10 p-3">
                      <AlertCircle className="h-4 w-4 text-red-500" />
                      <span className="text-sm text-red-400">{formErrors.general}</span>
                    </div>
                  )}

                  <form
                    onSubmit={(e) => {
                      void handleSubmit(e);
                    }}
                    className="mt-6 space-y-4"
                  >
                    {/* Name Input */}
                    <div>
                      <label htmlFor="name" className="block text-sm font-medium text-white">
                        Rule Name *
                      </label>
                      <input
                        type="text"
                        id="name"
                        value={formData.name}
                        onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                        className={clsx(
                          'mt-1 block w-full rounded-lg border bg-[#121212] px-3 py-2 text-white focus:outline-none focus:ring-2',
                          formErrors.name
                            ? 'border-red-500 focus:border-red-500 focus:ring-red-500'
                            : 'border-gray-700 focus:border-[#76B900] focus:ring-[#76B900]'
                        )}
                        placeholder="Night Intrusion Alert"
                      />
                      {formErrors.name && (
                        <p className="mt-1 text-sm text-red-500">{formErrors.name}</p>
                      )}
                    </div>

                    {/* Description Input */}
                    <div>
                      <label htmlFor="description" className="block text-sm font-medium text-white">
                        Description
                      </label>
                      <textarea
                        id="description"
                        value={formData.description}
                        onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                        rows={2}
                        className="mt-1 block w-full resize-none rounded-lg border border-gray-700 bg-[#121212] px-3 py-2 text-white focus:border-[#76B900] focus:outline-none focus:ring-2 focus:ring-[#76B900]"
                        placeholder="Alert for person detection during night hours"
                      />
                    </div>

                    {/* Severity and Enabled */}
                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        <label htmlFor="severity" className="block text-sm font-medium text-white">
                          Severity
                        </label>
                        <select
                          id="severity"
                          value={formData.severity}
                          onChange={(e) =>
                            setFormData({ ...formData, severity: e.target.value as AlertSeverity })
                          }
                          className="mt-1 block w-full rounded-lg border border-gray-700 bg-[#121212] px-3 py-2 text-white focus:border-[#76B900] focus:outline-none focus:ring-2 focus:ring-[#76B900]"
                        >
                          {SEVERITY_OPTIONS.map((opt) => (
                            <option key={opt.value} value={opt.value}>
                              {opt.label}
                            </option>
                          ))}
                        </select>
                      </div>
                      <div className="flex items-center justify-center pt-6">
                        <Switch.Group>
                          <div className="flex items-center gap-3">
                            <Switch
                              checked={formData.enabled}
                              onChange={(enabled) => setFormData({ ...formData, enabled })}
                              className={clsx(
                                'relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-[#76B900] focus:ring-offset-2 focus:ring-offset-[#1A1A1A]',
                                formData.enabled ? 'bg-[#76B900]' : 'bg-gray-700'
                              )}
                            >
                              <span
                                className={clsx(
                                  'pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out',
                                  formData.enabled ? 'translate-x-5' : 'translate-x-0'
                                )}
                              />
                            </Switch>
                            <Switch.Label className="text-sm font-medium text-white">
                              Enabled
                            </Switch.Label>
                          </div>
                        </Switch.Group>
                      </div>
                    </div>

                    {/* Conditions Section */}
                    <div className="border-t border-gray-800 pt-4">
                      <h4 className="mb-3 text-sm font-medium text-gray-400">
                        Trigger Conditions (all conditions must match)
                      </h4>

                      <div className="grid grid-cols-2 gap-4">
                        {/* Risk Threshold */}
                        <div>
                          <label
                            htmlFor="risk_threshold"
                            className="block text-sm font-medium text-white"
                          >
                            Min Risk Score
                          </label>
                          <input
                            type="number"
                            id="risk_threshold"
                            value={formData.risk_threshold}
                            onChange={(e) =>
                              setFormData({ ...formData, risk_threshold: e.target.value })
                            }
                            min="0"
                            max="100"
                            className={clsx(
                              'mt-1 block w-full rounded-lg border bg-[#121212] px-3 py-2 text-white focus:outline-none focus:ring-2',
                              formErrors.risk_threshold
                                ? 'border-red-500 focus:border-red-500 focus:ring-red-500'
                                : 'border-gray-700 focus:border-[#76B900] focus:ring-[#76B900]'
                            )}
                            placeholder="0-100"
                          />
                          {formErrors.risk_threshold && (
                            <p className="mt-1 text-xs text-red-500">{formErrors.risk_threshold}</p>
                          )}
                        </div>

                        {/* Min Confidence */}
                        <div>
                          <label
                            htmlFor="min_confidence"
                            className="block text-sm font-medium text-white"
                          >
                            Min Confidence %
                          </label>
                          <input
                            type="number"
                            id="min_confidence"
                            value={formData.min_confidence}
                            onChange={(e) =>
                              setFormData({ ...formData, min_confidence: e.target.value })
                            }
                            min="0"
                            max="100"
                            step="0.1"
                            className={clsx(
                              'mt-1 block w-full rounded-lg border bg-[#121212] px-3 py-2 text-white focus:outline-none focus:ring-2',
                              formErrors.min_confidence
                                ? 'border-red-500 focus:border-red-500 focus:ring-red-500'
                                : 'border-gray-700 focus:border-[#76B900] focus:ring-[#76B900]'
                            )}
                            placeholder="0-100"
                          />
                          {formErrors.min_confidence && (
                            <p className="mt-1 text-xs text-red-500">{formErrors.min_confidence}</p>
                          )}
                        </div>
                      </div>

                      {/* Object Types */}
                      <div className="mt-4">
                        <label
                          htmlFor="object_types"
                          className="block text-sm font-medium text-white"
                        >
                          Object Types (comma-separated)
                        </label>
                        <input
                          type="text"
                          id="object_types"
                          value={formData.object_types}
                          onChange={(e) =>
                            setFormData({ ...formData, object_types: e.target.value })
                          }
                          className="mt-1 block w-full rounded-lg border border-gray-700 bg-[#121212] px-3 py-2 text-white focus:border-[#76B900] focus:outline-none focus:ring-2 focus:ring-[#76B900]"
                          placeholder="person, vehicle, animal"
                        />
                        <p className="mt-1 text-xs text-gray-500">
                          Available: {OBJECT_TYPE_OPTIONS.join(', ')}
                        </p>
                      </div>

                      {/* Camera IDs */}
                      <div className="mt-4">
                        <label htmlFor="camera_ids" className="block text-sm font-medium text-white">
                          Camera IDs (comma-separated, leave empty for all)
                        </label>
                        <input
                          type="text"
                          id="camera_ids"
                          value={formData.camera_ids}
                          onChange={(e) => setFormData({ ...formData, camera_ids: e.target.value })}
                          className="mt-1 block w-full rounded-lg border border-gray-700 bg-[#121212] px-3 py-2 text-white focus:border-[#76B900] focus:outline-none focus:ring-2 focus:ring-[#76B900]"
                          placeholder="front_door, backyard"
                        />
                      </div>
                    </div>

                    {/* Alert Settings Section */}
                    <div className="border-t border-gray-800 pt-4">
                      <h4 className="mb-3 text-sm font-medium text-gray-400">Alert Settings</h4>

                      <div className="grid grid-cols-2 gap-4">
                        {/* Cooldown */}
                        <div>
                          <label
                            htmlFor="cooldown_seconds"
                            className="block text-sm font-medium text-white"
                          >
                            Cooldown (seconds)
                          </label>
                          <input
                            type="number"
                            id="cooldown_seconds"
                            value={formData.cooldown_seconds}
                            onChange={(e) =>
                              setFormData({ ...formData, cooldown_seconds: e.target.value })
                            }
                            min="0"
                            className={clsx(
                              'mt-1 block w-full rounded-lg border bg-[#121212] px-3 py-2 text-white focus:outline-none focus:ring-2',
                              formErrors.cooldown_seconds
                                ? 'border-red-500 focus:border-red-500 focus:ring-red-500'
                                : 'border-gray-700 focus:border-[#76B900] focus:ring-[#76B900]'
                            )}
                            placeholder="300"
                          />
                          {formErrors.cooldown_seconds && (
                            <p className="mt-1 text-xs text-red-500">
                              {formErrors.cooldown_seconds}
                            </p>
                          )}
                          <p className="mt-1 text-xs text-gray-500">
                            Min seconds between duplicate alerts
                          </p>
                        </div>

                        {/* Channels */}
                        <div>
                          <label htmlFor="channels" className="block text-sm font-medium text-white">
                            Channels (comma-separated)
                          </label>
                          <input
                            type="text"
                            id="channels"
                            value={formData.channels}
                            onChange={(e) => setFormData({ ...formData, channels: e.target.value })}
                            className="mt-1 block w-full rounded-lg border border-gray-700 bg-[#121212] px-3 py-2 text-white focus:border-[#76B900] focus:outline-none focus:ring-2 focus:ring-[#76B900]"
                            placeholder="email, webhook"
                          />
                          <p className="mt-1 text-xs text-gray-500">Notification delivery channels</p>
                        </div>
                      </div>
                    </div>

                    {/* Action Buttons */}
                    <div className="flex justify-end gap-3 border-t border-gray-800 pt-4">
                      <button
                        type="button"
                        onClick={handleCloseModal}
                        disabled={submitting}
                        className="rounded-lg border border-gray-700 px-4 py-2 font-medium text-white transition-colors hover:bg-gray-800 focus:outline-none focus:ring-2 focus:ring-gray-700 disabled:opacity-50"
                      >
                        Cancel
                      </button>
                      <button
                        type="submit"
                        disabled={submitting}
                        className="rounded-lg bg-[#76B900] px-4 py-2 font-medium text-gray-900 transition-all hover:bg-[#8ed100] hover:shadow-[0_0_20px_rgba(118,185,0,0.3)] focus:outline-none focus:ring-2 focus:ring-[#76B900] disabled:opacity-50"
                      >
                        {submitting ? 'Saving...' : editingRule ? 'Update Rule' : 'Create Rule'}
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
                <Dialog.Panel className="w-full max-w-md transform overflow-hidden rounded-lg border border-gray-800 bg-[#1A1A1A] p-6 shadow-xl transition-all">
                  <div className="flex items-start gap-4">
                    <div className="flex h-10 w-10 items-center justify-center rounded-full bg-red-500/10">
                      <AlertCircle className="h-6 w-6 text-red-500" />
                    </div>
                    <div className="flex-1">
                      <Dialog.Title className="text-lg font-semibold text-white">
                        Delete Alert Rule
                      </Dialog.Title>
                      <p className="mt-2 text-sm text-gray-400">
                        Are you sure you want to delete{' '}
                        <span className="font-medium text-white">{deletingRule?.name}</span>? This
                        action cannot be undone.
                      </p>
                    </div>
                  </div>

                  <div className="mt-6 flex justify-end gap-3">
                    <button
                      type="button"
                      onClick={handleCloseDeleteModal}
                      disabled={submitting}
                      className="rounded-lg border border-gray-700 px-4 py-2 font-medium text-white transition-colors hover:bg-gray-800 focus:outline-none focus:ring-2 focus:ring-gray-700 disabled:opacity-50"
                    >
                      Cancel
                    </button>
                    <button
                      type="button"
                      onClick={() => {
                        void handleDelete();
                      }}
                      disabled={submitting}
                      className="rounded-lg bg-red-500 px-4 py-2 font-medium text-white transition-all hover:bg-red-600 focus:outline-none focus:ring-2 focus:ring-red-500 disabled:opacity-50"
                    >
                      {submitting ? 'Deleting...' : 'Delete Rule'}
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
