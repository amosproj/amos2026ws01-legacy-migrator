import { act } from 'react';
import { createRoot } from 'react-dom/client';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { DiffInterface } from './DiffInterface';
import * as diffApi from '../../services/diffApi';

const repository = {
  id: '1',
  provider: 'github' as const,
  fullName: 'amosproj/example',
  defaultBranch: 'main',
  branches: ['main', 'release', 'feature/account-api'],
  url: 'https://github.com/amosproj/example',
};

function renderDiffInterface() {
  const container = document.createElement('div');
  document.body.appendChild(container);
  const root = createRoot(container);
  act(() => root.render(<DiffInterface />));
  return { container, root };
}

async function flushEffects() {
  await act(async () => {});
}

function setSelectValue(select: HTMLSelectElement, value: string) {
  act(() => {
    const setter = Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, 'value')?.set;
    setter?.call(select, value);
    select.dispatchEvent(new Event('change', { bubbles: true }));
  });
}

afterEach(() => {
  vi.restoreAllMocks();
});

describe('DiffInterface', () => {
  beforeEach(() => {
    vi.spyOn(diffApi, 'listRepositories').mockResolvedValue([repository]);
  });

  it('loads a repository and explains a selected base/head comparison', async () => {
    vi.spyOn(diffApi, 'explainDiff').mockResolvedValue({
      summary: 'Moves account lookups to the target API.',
      risk: 'medium',
      files: [{
        path: 'src/account.ts',
        status: 'modified',
        additions: 4,
        deletions: 2,
        explanation: 'Replaces the legacy lookup.',
        patch: '- legacyLookup()\n+ targetApiLookup()',
      }],
      warnings: ['Review the worker dependency.'],
    });

    const { container, root } = renderDiffInterface();
    await flushEffects();

    expect(container.textContent).toContain('amosproj/example');
    const selects = container.querySelectorAll('select');
    setSelectValue(selects[1] as HTMLSelectElement, 'release');
    setSelectValue(selects[2] as HTMLSelectElement, 'feature/account-api');
    const form = container.querySelector('form');
    await act(async () => form?.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true })));
    await flushEffects();

    expect(diffApi.explainDiff).toHaveBeenCalledWith({
      repository: 'amosproj/example',
      provider: 'github',
      base: 'release',
      head: 'feature/account-api',
    });
    expect(container.textContent).toContain('Moves account lookups to the target API.');
    expect(container.textContent).toContain('src/account.ts');
    expect(container.textContent).toContain('Review the worker dependency.');
    act(() => root.unmount());
  });

  it('shows backend errors from the comparison request', async () => {
    vi.spyOn(diffApi, 'explainDiff').mockRejectedValue(new Error('GitHub token is missing.'));

    const { container, root } = renderDiffInterface();
    await flushEffects();
    const form = container.querySelector('form');
    await act(async () => form?.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true })));
    await flushEffects();

    expect(container.textContent).toContain('GitHub token is missing.');
    act(() => root.unmount());
  });
});
