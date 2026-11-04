import { act } from 'react';
import { createRoot } from 'react-dom/client';
import { afterEach, describe, expect, it, vi } from 'vitest';
import App from './App';
import { checkBackendHealth } from './services/api';

vi.mock('./services/api', async () => {
  const actual = await vi.importActual<typeof import('./services/api')>('./services/api');
  return {
    ...actual,
    checkBackendHealth: vi.fn().mockResolvedValue({
      backendAvailable: false,
      mcpAvailable: false,
      graphAvailable: false,
      message: 'Test mock mode',
    }),
  };
});

function renderApp() {
  const container = document.createElement('div');
  document.body.appendChild(container);
  const root = createRoot(container);
  act(() => root.render(<App />));
  return { container, root };
}

async function flushEffects() {
  await act(async () => {});
}

afterEach(() => {
  vi.restoreAllMocks();
});

describe('App', () => {
  it('switches between query, architecture, and Git comparison tabs', async () => {
    const { container, root } = renderApp();
    await flushEffects();

    expect(container.textContent).toContain('Query Terminal');
    const diffTab = Array.from(container.querySelectorAll('button')).find((button) => button.textContent?.includes('Git Comparisons'));
    act(() => diffTab?.dispatchEvent(new MouseEvent('click', { bubbles: true })));
    expect(container.textContent).toContain('Change explanations');

    const viewsTab = Array.from(container.querySelectorAll('button')).find((button) => button.textContent?.includes('arc42 Architecture Views'));
    act(() => viewsTab?.dispatchEvent(new MouseEvent('click', { bubbles: true })));
    expect(container.textContent).toContain('Architecture Views');
    expect(checkBackendHealth).toHaveBeenCalled();
    act(() => root.unmount());
  });
});
