import { act } from 'react';
import { createRoot } from 'react-dom/client';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { ChatInterface } from './ChatInterface';
import * as api from '../../services/api';

function renderChat() {
  const container = document.createElement('div');
  document.body.appendChild(container);
  const root = createRoot(container);
  act(() => root.render(<ChatInterface selectedStep="step-06" />));
  return { container, root };
}

function enterQuery(container: HTMLElement, query: string) {
  const textarea = container.querySelector('textarea');
  if (!textarea) throw new Error('Chat textarea was not rendered.');

  act(() => {
    const setter = Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, 'value')?.set;
    setter?.call(textarea, query);
    textarea.dispatchEvent(new Event('input', { bubbles: true }));
    textarea.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true }));
  });
}

afterEach(() => {
  vi.restoreAllMocks();
  document.body.innerHTML = '';
});

describe('ChatInterface', () => {
  it('hides suggestions and the blank assistant bubble while the first answer is pending', async () => {
    let resolveQuery: ((value: Awaited<ReturnType<typeof api.submitMigrationQuery>>) => void) | undefined;
    vi.spyOn(api, 'submitMigrationQuery').mockReturnValue(
      new Promise((resolve) => {
        resolveQuery = resolve;
      }),
    );

    const { container } = renderChat();
    expect(container.textContent).toContain('Accepted Migration Verification Queries');

    enterQuery(container, 'How far along is the migration?');

    expect(container.textContent).not.toContain('Accepted Migration Verification Queries');
    expect(container.textContent).toContain('The LLM is warming up.');
    expect(container.textContent).not.toContain('Waiting for the LLM to start answering');
    expect(container.textContent).toContain('DEVELOPER INQUIRY');

    await act(async () => {
      resolveQuery?.({
        answer: 'The migration is progressing.',
        evidence: [],
        stepId: 'step-06',
        executionTimeMs: 120,
        suggestedNextQueries: ['What remains?'],
      });
    });

    expect(container.textContent).toContain('The migration is progressing.');
  });
});
