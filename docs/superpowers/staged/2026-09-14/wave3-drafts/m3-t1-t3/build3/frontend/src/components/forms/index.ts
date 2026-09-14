/**
 * Form Components - React 19 Form Action Patterns
 *
 * This module exports form components that leverage React 19's new form patterns:
 * - useActionState for managing form state with async actions
 * - useFormStatus for automatic pending state detection
 *
 * @see NEM-3356 - Implement useActionState and useFormStatus for forms
 *
 * @example
 * ```tsx
 * import { useActionState } from 'react';
 * import { SubmitButton, FormField, createFormAction, createInitialState } from '../components/forms';
 *
 * const submitAction = createFormAction(async (formData) => {
 *   const email = formData.get('email');
 *   await api.subscribe(email);
 *   return { success: true };
 * });
 *
 * function NewsletterForm() {
 *   const [state, action] = useActionState(submitAction, createInitialState());
 *
 *   return (
 *     <form action={action}>
 *       <FormField
 *         name="email"
 *         label="Email"
 *         type="email"
 *         error={state.fieldErrors?.email}
 *         required
 *       />
 *       <SubmitButton pendingText="Subscribing...">Subscribe</SubmitButton>
 *     </form>
 *   );
 * }
 * ```
 */

// Submit Button with useFormStatus
export {
  SubmitButton,
  PrimarySubmitButton,
  SecondarySubmitButton,
  DangerSubmitButton,
  default as SubmitButtonDefault,
} from './SubmitButton';
export type { SubmitButtonProps, SubmitButtonVariant, SubmitButtonSize } from './SubmitButton';

// Form Field Components
export { FormField, FormTextarea, FormSelect, default as FormFieldDefault } from './FormField';
export type { FormFieldProps, FormTextareaProps, FormSelectProps } from './FormField';

// Re-export form action utilities from hooks
export {
  createFormAction,
  useFormAction,
  createInitialState,
  extractValidationErrors,
  getErrorMessage,
  isActionPending,
  isActionSuccess,
  isActionError,
  hasFieldErrors,
  getFieldError,
} from '../../hooks/useFormAction';
export type {
  FormActionState,
  FormActionStatus,
  FormActionOptions,
  FormActionFn,
  ValidationError,
} from '../../hooks/useFormAction';
