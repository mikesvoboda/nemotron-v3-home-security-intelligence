/**
 * FeedbackPanel component for EventDetailModal
 *
 * Displays feedback buttons for event classification:
 * - accurate: Detection was correct
 * - false_positive: Event was incorrectly flagged
 * - missed_threat: System failed to detect a threat
 * - severity_wrong: Risk level was incorrect
 *
 * Includes calibration fields for AI model improvement (NEM-3552):
 * - actual_threat_level: User's assessment of true threat level
 * - suggested_score: What the user thinks the risk score should have been
 * - actual_identity: Identity correction for household member learning
 * - what_was_wrong: Detailed explanation of what the AI got wrong
 * - model_failures: List of specific AI models that failed
 *
 * @see NEM-2353 - Create FeedbackPanel component for EventDetailModal
 * @see NEM-3552 - Integrate EventFeedback calibration fields into frontend
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { clsx } from 'clsx';
import {
  AlertTriangle,
  Check,
  CheckCircle2,
  Loader2,
  MessageSquare,
  ThumbsDown,
  ThumbsUp,
  X,
} from 'lucide-react';
import { useCallback, useState } from 'react';

import {
  getEventFeedback,
  submitEventFeedback,
  type ActualThreatLevel,
  type EventFeedbackResponse,
  type FeedbackType,
} from '../../services/api';

export interface FeedbackPanelProps {
  /** Event ID to submit feedback for */
  eventId: number;
  /** Current risk score of the event (0-100) */
  currentRiskScore?: number;
  /** Optional CSS class name */
  className?: string;
  /** Callback when feedback is successfully submitted */
  onFeedbackSubmitted?: (feedback: EventFeedbackResponse) => void;
}

interface FeedbackOption {
  type: FeedbackType;
  label: string;
  icon: React.ElementType;
  description: string;
  colorClass: string;
  bgClass: string;
  borderClass: string;
}

/** Available AI model names for failure reporting */
const AI_MODELS = [
  { id: 'rtdetr', label: 'RT-DETR (Object Detection)' },
  { id: 'florence_vqa', label: 'Florence VQA' },
  { id: 'clip', label: 'CLIP (Image Classification)' },
  { id: 'pose_model', label: 'Pose Estimation' },
  { id: 'vehicle_classifier', label: 'Vehicle Classifier' },
  { id: 'pet_model', label: 'Pet Detection' },
  { id: 'weather_model', label: 'Weather Analysis' },
] as const;

/** Threat level options for user assessment */
const THREAT_LEVEL_OPTIONS: { value: ActualThreatLevel; label: string; description: string }[] = [
  {
    value: 'no_threat',
    label: 'No Threat',
    description: 'Household member, pet, or harmless activity',
  },
  { value: 'minor_concern', label: 'Minor Concern', description: 'Worth noting but not alarming' },
  { value: 'genuine_threat', label: 'Genuine Threat', description: 'Actual security concern' },
];

const FEEDBACK_OPTIONS: FeedbackOption[] = [
  {
    type: 'accurate',
    label: 'Accurate',
    icon: ThumbsUp,
    description: 'Detection was correct',
    colorClass: 'text-green-400',
    bgClass: 'bg-green-600/10 hover:bg-green-600/20',
    borderClass: 'border-green-600/40',
  },
  {
    type: 'false_positive',
    label: 'False Positive',
    icon: ThumbsDown,
    description: 'Event was incorrectly flagged',
    colorClass: 'text-red-400',
    bgClass: 'bg-red-600/10 hover:bg-red-600/20',
    borderClass: 'border-red-600/40',
  },
  {
    type: 'missed_threat',
    label: 'Missed Threat',
    icon: AlertTriangle,
    description: 'System failed to detect a threat',
    colorClass: 'text-orange-400',
    bgClass: 'bg-orange-600/10 hover:bg-orange-600/20',
    borderClass: 'border-orange-600/40',
  },
  {
    type: 'severity_wrong',
    label: 'Severity Wrong',
    icon: MessageSquare,
    description: 'Risk level was incorrect',
    colorClass: 'text-yellow-400',
    bgClass: 'bg-yellow-600/10 hover:bg-yellow-600/20',
    borderClass: 'border-yellow-600/40',
  },
];

function getFeedbackTypeLabel(type: string): string {
  const option = FEEDBACK_OPTIONS.find((opt) => opt.type === type);
  return option?.label ?? type.replace(/_/g, ' ').replace(/\b\w/g, (c: string) => c.toUpperCase());
}

export default function FeedbackPanel({
  eventId,
  currentRiskScore,
  className,
  onFeedbackSubmitted,
}: FeedbackPanelProps) {
  const [selectedType, setSelectedType] = useState<FeedbackType | null>(null);
  const [notes, setNotes] = useState('');
  const [showNotesForm, setShowNotesForm] = useState(false);
  const [actualThreatLevel, setActualThreatLevel] = useState<ActualThreatLevel | null>(null);
  const [suggestedScore, setSuggestedScore] = useState<number>(currentRiskScore ?? 50);
  const [actualIdentity, setActualIdentity] = useState('');
  const [whatWasWrong, setWhatWasWrong] = useState('');
  const [modelFailures, setModelFailures] = useState<string[]>([]);

  const queryClient = useQueryClient();

  const {
    data: existingFeedback,
    isLoading: isLoadingFeedback,
    error: feedbackError,
  } = useQuery<EventFeedbackResponse | null>({
    queryKey: ['eventFeedback', eventId],
    queryFn: () => getEventFeedback(eventId),
    enabled: !isNaN(eventId),
    staleTime: 30000,
  });

  const feedbackMutation = useMutation({
    mutationFn: submitEventFeedback,
    onSuccess: (data) => {
      setSelectedType(null);
      setNotes('');
      setShowNotesForm(false);
      setActualThreatLevel(null);
      setSuggestedScore(currentRiskScore ?? 50);
      setActualIdentity('');
      setWhatWasWrong('');
      setModelFailures([]);
      void queryClient.invalidateQueries({ queryKey: ['eventFeedback', eventId] });
      void queryClient.invalidateQueries({ queryKey: ['feedbackStats'] });
      onFeedbackSubmitted?.(data);
    },
  });

  const handleQuickFeedback = useCallback(
    (type: FeedbackType) => {
      if (isNaN(eventId)) return;
      feedbackMutation.mutate({
        event_id: eventId,
        feedback_type: type,
      });
    },
    [eventId, feedbackMutation]
  );

  const handleOpenNotesForm = useCallback(
    (type: FeedbackType) => {
      setSelectedType(type);
      setShowNotesForm(true);
      setActualThreatLevel(null);
      setSuggestedScore(currentRiskScore ?? 50);
      setActualIdentity('');
      setWhatWasWrong('');
      setModelFailures([]);
    },
    [currentRiskScore]
  );

  const handleSubmitWithNotes = useCallback(() => {
    if (isNaN(eventId) || !selectedType) return;
    let finalNotes = notes.trim();
    if (selectedType === 'severity_wrong' && currentRiskScore !== undefined) {
      finalNotes = finalNotes
        ? 'Current score: ' + currentRiskScore + '. ' + finalNotes
        : 'Current score: ' + currentRiskScore;
    }
    feedbackMutation.mutate({
      event_id: eventId,
      feedback_type: selectedType,
      notes: finalNotes || undefined,
      actual_threat_level: actualThreatLevel ?? undefined,
      suggested_score: suggestedScore,
      actual_identity: actualIdentity.trim() || undefined,
      what_was_wrong: whatWasWrong.trim() || undefined,
      model_failures: modelFailures.length > 0 ? modelFailures : undefined,
    });
  }, [eventId, selectedType, notes, currentRiskScore, feedbackMutation, actualThreatLevel, suggestedScore, actualIdentity, whatWasWrong, modelFailures]);

  const handleCancelNotesForm = useCallback(() => {
    setSelectedType(null);
    setNotes('');
    setShowNotesForm(false);
    setActualThreatLevel(null);
    setSuggestedScore(currentRiskScore ?? 50);
    setActualIdentity('');
    setWhatWasWrong('');
    setModelFailures([]);
  }, [currentRiskScore]);

  const handleModelFailureToggle = useCallback((modelId: string) => {
    setModelFailures((prev) =>
      prev.includes(modelId) ? prev.filter((id) => id !== modelId) : [...prev, modelId]
    );
  }, []);

  if (isLoadingFeedback) {
    return (
      <div className={clsx('rounded-lg border border-gray-800 bg-[#1A1A1A] p-4', className)} data-testid="feedback-panel">
        <div className="flex items-center gap-2 text-sm text-gray-400">
          <Loader2 className="h-4 w-4 animate-spin" />
          Loading feedback...
        </div>
      </div>
    );
  }

  if (feedbackError && (feedbackError as { status?: number }).status !== 404) {
    return (
      <div className={clsx('rounded-lg border border-red-800 bg-red-900/20 p-4', className)} data-testid="feedback-panel">
        <p className="text-sm text-red-400">Failed to load feedback status.</p>
      </div>
    );
  }

  if (existingFeedback) {
    const option = FEEDBACK_OPTIONS.find((opt) => opt.type === existingFeedback.feedback_type);
    const Icon = option?.icon ?? Check;
    return (
      <div className={clsx('rounded-lg border border-gray-800 bg-[#1A1A1A] p-4', className)} data-testid="feedback-panel">
        <div className="flex items-center gap-3">
          <CheckCircle2 className="h-5 w-5 flex-shrink-0 text-[#76B900]" />
          <div>
            <div className="flex items-center gap-2">
              <Icon className={clsx('h-4 w-4', option?.colorClass ?? 'text-gray-400')} />
              <span className="font-medium text-white">{getFeedbackTypeLabel(existingFeedback.feedback_type)}</span>
            </div>
            {existingFeedback.notes && <p className="mt-1 text-sm text-gray-400">{existingFeedback.notes}</p>}
            <p className="mt-1 text-xs text-gray-500">Submitted {new Date(existingFeedback.created_at).toLocaleDateString()}</p>
          </div>
        </div>
      </div>
    );
  }

  if (showNotesForm && selectedType) {
    const option = FEEDBACK_OPTIONS.find((opt) => opt.type === selectedType);
    const showThreatLevel = selectedType === 'false_positive' || selectedType === 'missed_threat';
    const showSuggestedScore = selectedType === 'severity_wrong';
    const showIdentity = selectedType === 'false_positive';
    const showModelFailures = selectedType === 'false_positive' || selectedType === 'missed_threat' || selectedType === 'severity_wrong';

    return (
      <div className={clsx('rounded-lg border border-gray-800 bg-[#1A1A1A] p-4', className)} data-testid="feedback-panel">
        <div className="mb-4 flex items-center justify-between">
          <h4 className="flex items-center gap-2 text-sm font-semibold text-white">
            <MessageSquare className="h-4 w-4 text-[#76B900]" />
            {option?.label ?? 'Feedback'}
          </h4>
          <button type="button" onClick={handleCancelNotesForm} className="rounded p-1 text-gray-400 hover:bg-gray-700 hover:text-white" aria-label="Cancel feedback" data-testid="cancel-feedback-button">
            <X className="h-4 w-4" />
          </button>
        </div>

        {showThreatLevel && (
          <div className="mb-4">
            <span id="threat-level-label" className="mb-2 block text-sm text-gray-400">What was the actual threat level?</span>
            <div role="group" aria-labelledby="threat-level-label" className="flex flex-wrap gap-2" data-testid="threat-level-options">
              {THREAT_LEVEL_OPTIONS.map((opt) => (
                <button key={opt.value} type="button" onClick={() => setActualThreatLevel(opt.value)} className={clsx('rounded-lg border px-3 py-2 text-sm transition-colors', actualThreatLevel === opt.value ? 'border-[#76B900] bg-[#76B900]/20 text-[#76B900]' : 'border-gray-700 bg-black/30 text-gray-400 hover:border-gray-600 hover:text-gray-300')} title={opt.description} data-testid={'threat-level-' + opt.value}>{opt.label}</button>
              ))}
            </div>
          </div>
        )}

        {showSuggestedScore && (
          <div className="mb-4">
            <label htmlFor="suggested-score" className="mb-2 block text-sm text-gray-400">What should the risk score be? (Current: {currentRiskScore ?? 'N/A'})</label>
            <div className="flex items-center gap-4">
              <input id="suggested-score" type="range" min={0} max={100} value={suggestedScore} onChange={(e) => setSuggestedScore(Number(e.target.value))} className="h-2 flex-1 cursor-pointer appearance-none rounded-lg bg-gray-700 accent-[#76B900]" data-testid="suggested-score-slider" />
              <span className="w-12 text-center text-sm font-medium text-white">{suggestedScore}</span>
            </div>
          </div>
        )}

        {showIdentity && (
          <div className="mb-4">
            <label htmlFor="actual-identity" className="mb-2 block text-sm text-gray-400">Who was this person? (for household member learning)</label>
            <input id="actual-identity" type="text" value={actualIdentity} onChange={(e) => setActualIdentity(e.target.value)} placeholder="e.g., Mike (neighbor), Family dog, Delivery person" maxLength={100} className="w-full rounded-lg border border-gray-700 bg-black/30 px-3 py-2 text-sm text-gray-200 placeholder-gray-500 transition-colors focus:border-[#76B900] focus:outline-none focus:ring-2 focus:ring-[#76B900]/20" data-testid="actual-identity-input" />
          </div>
        )}

        <div className="mb-4">
          <label htmlFor="what-was-wrong" className="mb-2 block text-sm text-gray-400">What did the AI get wrong?</label>
          <textarea id="what-was-wrong" value={whatWasWrong} onChange={(e) => setWhatWasWrong(e.target.value)} placeholder="Describe what the AI misunderstood or missed..." rows={2} maxLength={500} className="w-full rounded-lg border border-gray-700 bg-black/30 px-3 py-2 text-sm text-gray-200 placeholder-gray-500 transition-colors focus:border-[#76B900] focus:outline-none focus:ring-2 focus:ring-[#76B900]/20" data-testid="what-was-wrong-textarea" />
          <div className="mt-1 text-right text-xs text-gray-500">{whatWasWrong.length}/500</div>
        </div>

        {showModelFailures && (
          <div className="mb-4">
            <span id="model-failures-label" className="mb-2 block text-sm text-gray-400">Which AI models failed? (optional)</span>
            <div role="group" aria-labelledby="model-failures-label" className="grid grid-cols-2 gap-2 sm:grid-cols-3" data-testid="model-failures-checkboxes">
              {AI_MODELS.map((model) => (
                <label key={model.id} className={clsx('flex cursor-pointer items-center gap-2 rounded-lg border px-3 py-2 text-sm transition-colors', modelFailures.includes(model.id) ? 'border-[#76B900] bg-[#76B900]/20 text-[#76B900]' : 'border-gray-700 bg-black/30 text-gray-400 hover:border-gray-600')}>
                  <input type="checkbox" checked={modelFailures.includes(model.id)} onChange={() => handleModelFailureToggle(model.id)} className="sr-only" data-testid={'model-failure-' + model.id} />
                  <span className="truncate">{model.label}</span>
                </label>
              ))}
            </div>
          </div>
        )}

        <div className="mb-4">
          <label htmlFor="feedback-notes" className="mb-2 block text-sm text-gray-400">{selectedType === 'severity_wrong' ? 'What should the severity be?' : 'Additional notes (optional)'}</label>
          <textarea id="feedback-notes" value={notes} onChange={(e) => setNotes(e.target.value)} placeholder={selectedType === 'false_positive' ? 'Explain why this is a false positive...' : selectedType === 'severity_wrong' ? 'Describe the expected severity level...' : 'Add any additional context...'} rows={3} maxLength={1000} className="w-full rounded-lg border border-gray-700 bg-black/30 px-3 py-2 text-sm text-gray-200 placeholder-gray-500 transition-colors focus:border-[#76B900] focus:outline-none focus:ring-2 focus:ring-[#76B900]/20" data-testid="feedback-notes" />
          <div className="mt-1 text-right text-xs text-gray-500">{notes.length}/1000</div>
        </div>

        {feedbackMutation.isError && (
          <div className="mb-4 flex items-center gap-2 rounded-md bg-red-900/20 px-3 py-2 text-sm text-red-400">
            <X className="h-4 w-4" />
            <span>Failed to submit feedback. Please try again.</span>
          </div>
        )}

        <div className="flex items-center justify-end gap-2">
          <button type="button" onClick={handleCancelNotesForm} disabled={feedbackMutation.isPending} className="rounded-lg px-4 py-2 text-sm font-medium text-gray-400 transition-colors hover:bg-gray-800 hover:text-white disabled:cursor-not-allowed disabled:opacity-50" data-testid="cancel-button">Cancel</button>
          <button type="button" onClick={handleSubmitWithNotes} disabled={feedbackMutation.isPending} className="flex items-center gap-2 rounded-lg bg-[#76B900] px-4 py-2 text-sm font-semibold text-black transition-all hover:bg-[#88d200] active:bg-[#68a000] disabled:cursor-not-allowed disabled:opacity-50" data-testid="submit-feedback-button">
            {feedbackMutation.isPending ? (<><Loader2 className="h-4 w-4 animate-spin" /><span>Submitting...</span></>) : (<span>Submit Feedback</span>)}
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className={clsx('rounded-lg border border-gray-800 bg-[#1A1A1A] p-4', className)} data-testid="feedback-panel">
      <h3 className="mb-3 text-sm font-semibold uppercase tracking-wide text-gray-400">Detection Feedback</h3>
      <p className="mb-3 text-sm text-gray-400">Help improve AI accuracy by providing feedback on this detection.</p>
      {feedbackMutation.isError && (
        <div className="mb-3 flex items-center gap-2 rounded-md bg-red-900/20 px-3 py-2 text-sm text-red-400">
          <X className="h-4 w-4" />
          <span>Failed to submit feedback. Please try again.</span>
        </div>
      )}
      <div className="flex flex-wrap gap-2" data-testid="feedback-buttons">
        {FEEDBACK_OPTIONS.map((option) => {
          const Icon = option.icon;
          const isAccurate = option.type === 'accurate';
          return (
            <button key={option.type} onClick={() => isAccurate ? handleQuickFeedback(option.type) : handleOpenNotesForm(option.type)} disabled={feedbackMutation.isPending} className={clsx('flex items-center gap-2 rounded-lg border px-3 py-2 text-sm font-medium transition-colors', 'disabled:cursor-not-allowed disabled:opacity-50', option.bgClass, option.borderClass, option.colorClass)} title={option.description} data-testid={'feedback-' + option.type + '-button'}>
              <Icon className="h-4 w-4" />
              {option.label}
            </button>
          );
        })}
      </div>
    </div>
  );
}
