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
    expect(container.textContent).toContain('Suggested queries');

    enterQuery(container, 'How far along is the migration?');

    expect(container.textContent).not.toContain('Suggested queries');
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
    expect(container.textContent).not.toContain('Source evidence');
  });

  it('shows returned source fragments with pinned links to the reference repository', async () => {
    const position = {
      stage: 'step-06',
      repoId: 'legacy-example-catalog-service',
      path: 'src/main/java/com/ibm/catalog/CategoryResource.java',
      commitSha: '474422cf156eb9bcce4267578b089a15edcc3733',
      startLine: 17,
      endLine: 17,
    };
    const githubUrl = `https://github.com/legacy-modernization-example/${position.repoId}/blob/${position.commitSha}/${position.path}#L17-L17`;
    const fragment = '@Path("/CustomerOrderServicesWeb/jaxrs/Category")';
    const source = { position, githubUrl, fragment };
    const events = [
      { type: 'sources', text: JSON.stringify(['llm:mock']) },
      { type: 'evidence', text: JSON.stringify([
        source,
        source,
        { ...source, githubUrl: githubUrl.replace('#L17-L17', '#L18-L18') },
        { ...source, githubUrl: githubUrl.replace('github.com', 'github.com.example.org') },
      ]) },
      { type: 'content', text: 'The Category route is in the Catalog service.' },
    ];
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response(
      events.map((event) => `${JSON.stringify(event)}\n`).join(''),
    ));

    const { container, root } = renderChat();
    await act(async () => {
      enterQuery(container, 'Where is the Category route?');
    });

    const links = container.querySelectorAll('a[title="Open on GitHub"]');
    expect(links).toHaveLength(1);
    expect(links[0].getAttribute('href')).toBe(githubUrl);
    expect(container.textContent).toContain('CategoryResource.java:17');
    expect(container.querySelector('pre code')?.textContent).toBe(fragment);
    expect(container.textContent).not.toContain('llm:mock');
    expect(container.textContent).not.toContain('Migrated to Target');
    act(() => root.unmount());
  });
});
