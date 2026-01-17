/**
 * Prompt Management Components
 *
 * Components for managing AI model prompt configurations.
 *
 * @see NEM-2697 - Build Prompt Management page
 * @see NEM-2698 - Implement prompt A/B testing UI with real inference comparison
 */

export { default as PromptManagementPage } from './PromptManagementPage';
export { default as PromptConfigEditor } from './PromptConfigEditor';
export { default as PromptTestModal } from './PromptTestModal';
export { default as EventSelector } from './EventSelector';
export { default as TestResultsComparison } from './TestResultsComparison';

// Re-export types for external use
export type { PromptConfigEditorProps } from './PromptConfigEditor';
export type { PromptTestModalProps } from './PromptTestModal';
export type { EventSelectorProps } from './EventSelector';
export type { TestResultsComparisonProps, TestResult } from './TestResultsComparison';

// Re-export model forms
export * from './model-forms';
