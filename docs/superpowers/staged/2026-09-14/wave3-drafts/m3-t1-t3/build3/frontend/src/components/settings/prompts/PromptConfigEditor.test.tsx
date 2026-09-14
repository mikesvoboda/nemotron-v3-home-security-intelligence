/**
 * Tests for PromptConfigEditor component
 *
 * @see NEM-2697 - Build Prompt Management page
 */

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi } from 'vitest';

import PromptConfigEditor from './PromptConfigEditor';
import { AIModelEnum } from '../../../types/promptManagement';

// ============================================================================
// Test Utilities
// ============================================================================

function createTestQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
        gcTime: 0,
      },
    },
  });
}

function renderWithProviders(ui: React.ReactElement) {
  const queryClient = createTestQueryClient();
  return render(<QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>);
}

// ============================================================================
// Test Data
// ============================================================================

const nemotronConfig = {
  system_prompt: 'You are an AI security analyst.',
  temperature: 0.7,
  max_tokens: 4096,
};

const florence2Config = {
  queries: ['What objects are in this scene?'],
};

const yoloWorldConfig = {
  classes: ['person', 'car'],
  confidence_threshold: 0.5,
};

const xclipConfig = {
  action_classes: ['walking', 'running'],
};

const fashionClipConfig = {
  clothing_categories: ['hoodie', 'mask'],
  suspicious_indicators: ['face covering'],
};

// ============================================================================
// Tests
// ============================================================================

describe('PromptConfigEditor', () => {
  describe('rendering', () => {
    it('renders the modal when open', () => {
      renderWithProviders(
        <PromptConfigEditor
          isOpen={true}
          onClose={vi.fn()}
          model={AIModelEnum.NEMOTRON}
          initialConfig={nemotronConfig}
          onSave={vi.fn()}
        />
      );

      expect(screen.getByRole('dialog')).toBeInTheDocument();
      expect(screen.getByText(/Edit Nemotron Configuration/i)).toBeInTheDocument();
    });

    it('does not render when closed', () => {
      renderWithProviders(
        <PromptConfigEditor
          isOpen={false}
          onClose={vi.fn()}
          model={AIModelEnum.NEMOTRON}
          initialConfig={nemotronConfig}
          onSave={vi.fn()}
        />
      );

      expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    });

    it('renders change description input', () => {
      renderWithProviders(
        <PromptConfigEditor
          isOpen={true}
          onClose={vi.fn()}
          model={AIModelEnum.NEMOTRON}
          initialConfig={nemotronConfig}
          onSave={vi.fn()}
        />
      );

      expect(screen.getByLabelText(/Change Description/i)).toBeInTheDocument();
    });

    it('renders Save, Test Changes, and Cancel buttons', () => {
      renderWithProviders(
        <PromptConfigEditor
          isOpen={true}
          onClose={vi.fn()}
          model={AIModelEnum.NEMOTRON}
          initialConfig={nemotronConfig}
          onSave={vi.fn()}
        />
      );

      expect(screen.getByRole('button', { name: /Save Changes/i })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /Test Changes/i })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /Cancel/i })).toBeInTheDocument();
    });
  });

  describe('model-specific forms', () => {
    it('renders NemotronConfigForm for Nemotron model', () => {
      renderWithProviders(
        <PromptConfigEditor
          isOpen={true}
          onClose={vi.fn()}
          model={AIModelEnum.NEMOTRON}
          initialConfig={nemotronConfig}
          onSave={vi.fn()}
        />
      );

      expect(screen.getByTestId('nemotron-config-form')).toBeInTheDocument();
    });

    it('renders Florence2ConfigForm for Florence2 model', () => {
      renderWithProviders(
        <PromptConfigEditor
          isOpen={true}
          onClose={vi.fn()}
          model={AIModelEnum.FLORENCE2}
          initialConfig={florence2Config}
          onSave={vi.fn()}
        />
      );

      expect(screen.getByTestId('florence2-config-form')).toBeInTheDocument();
    });

    it('renders YoloWorldConfigForm for YOLO-World model', () => {
      renderWithProviders(
        <PromptConfigEditor
          isOpen={true}
          onClose={vi.fn()}
          model={AIModelEnum.YOLO_WORLD}
          initialConfig={yoloWorldConfig}
          onSave={vi.fn()}
        />
      );

      expect(screen.getByTestId('yoloworld-config-form')).toBeInTheDocument();
    });

    it('renders XClipConfigForm for X-CLIP model', () => {
      renderWithProviders(
        <PromptConfigEditor
          isOpen={true}
          onClose={vi.fn()}
          model={AIModelEnum.XCLIP}
          initialConfig={xclipConfig}
          onSave={vi.fn()}
        />
      );

      expect(screen.getByTestId('xclip-config-form')).toBeInTheDocument();
    });

    it('renders FashionClipConfigForm for Fashion-CLIP model', () => {
      renderWithProviders(
        <PromptConfigEditor
          isOpen={true}
          onClose={vi.fn()}
          model={AIModelEnum.FASHION_CLIP}
          initialConfig={fashionClipConfig}
          onSave={vi.fn()}
        />
      );

      expect(screen.getByTestId('fashionclip-config-form')).toBeInTheDocument();
    });
  });

  describe('interactions', () => {
    it('calls onClose when Cancel is clicked', async () => {
      const handleClose = vi.fn();
      const user = userEvent.setup();

      renderWithProviders(
        <PromptConfigEditor
          isOpen={true}
          onClose={handleClose}
          model={AIModelEnum.NEMOTRON}
          initialConfig={nemotronConfig}
          onSave={vi.fn()}
        />
      );

      await user.click(screen.getByRole('button', { name: /Cancel/i }));

      expect(handleClose).toHaveBeenCalled();
    });

    it('calls onClose when X button is clicked', async () => {
      const handleClose = vi.fn();
      const user = userEvent.setup();

      renderWithProviders(
        <PromptConfigEditor
          isOpen={true}
          onClose={handleClose}
          model={AIModelEnum.NEMOTRON}
          initialConfig={nemotronConfig}
          onSave={vi.fn()}
        />
      );

      await user.click(screen.getByRole('button', { name: /Close/i }));

      expect(handleClose).toHaveBeenCalled();
    });

    it('calls onSave with config and description when Save is clicked', async () => {
      const handleSave = vi.fn();
      const user = userEvent.setup();

      renderWithProviders(
        <PromptConfigEditor
          isOpen={true}
          onClose={vi.fn()}
          model={AIModelEnum.NEMOTRON}
          initialConfig={nemotronConfig}
          onSave={handleSave}
        />
      );

      const descriptionInput = screen.getByLabelText(/Change Description/i);
      await user.type(descriptionInput, 'Updated the prompt');

      await user.click(screen.getByRole('button', { name: /Save Changes/i }));

      expect(handleSave).toHaveBeenCalledWith(
        expect.objectContaining({ system_prompt: 'You are an AI security analyst.' }),
        'Updated the prompt'
      );
    });
  });

  describe('saving state', () => {
    it('disables buttons when saving', () => {
      renderWithProviders(
        <PromptConfigEditor
          isOpen={true}
          onClose={vi.fn()}
          model={AIModelEnum.NEMOTRON}
          initialConfig={nemotronConfig}
          onSave={vi.fn()}
          isSaving={true}
        />
      );

      expect(screen.getByRole('button', { name: /Save Changes/i })).toBeDisabled();
      expect(screen.getByRole('button', { name: /Cancel/i })).toBeDisabled();
    });

    it('disables form inputs when saving', () => {
      renderWithProviders(
        <PromptConfigEditor
          isOpen={true}
          onClose={vi.fn()}
          model={AIModelEnum.NEMOTRON}
          initialConfig={nemotronConfig}
          onSave={vi.fn()}
          isSaving={true}
        />
      );

      expect(screen.getByLabelText(/System Prompt/i)).toBeDisabled();
      expect(screen.getByLabelText(/Change Description/i)).toBeDisabled();
    });
  });
});
