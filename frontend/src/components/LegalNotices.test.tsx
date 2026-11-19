import { act } from 'react';
import { createRoot, Root } from 'react-dom/client';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { LegalNotices } from './LegalNotices';

describe('LegalNotices', () => {
  let container: HTMLDivElement;
  let root: Root;

  afterEach(() => {
    act(() => root?.unmount());
    vi.unstubAllGlobals();
    document.body.innerHTML = '';
  });

  it('fetches and displays the generated notice document', async () => {
    const notices = '# Third-party legal notices\nMIT';
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      text: vi.fn().mockResolvedValue(notices),
    });
    vi.stubGlobal('fetch', fetchMock);
    container = document.createElement('div');
    document.body.appendChild(container);
    root = createRoot(container);

    await act(async () => {
      root.render(<LegalNotices onClose={vi.fn()} />);
    });

    expect(fetchMock).toHaveBeenCalledWith('/legal/THIRD_PARTY_NOTICES.md');
    expect(container.textContent).toContain(notices);
    expect(container.textContent).not.toContain('Loading legal notices');
  });

  it('shows an error when the notice document cannot be loaded', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false }));
    container = document.createElement('div');
    document.body.appendChild(container);
    root = createRoot(container);

    await act(async () => {
      root.render(<LegalNotices onClose={vi.fn()} />);
    });

    expect(container.querySelector('[role="alert"]')?.textContent).toBe(
      'Legal notices could not be loaded.',
    );
  });

  it('closes when the close button is clicked', () => {
    const onClose = vi.fn();
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, text: async () => '' }));
    container = document.createElement('div');
    document.body.appendChild(container);
    root = createRoot(container);

    act(() => {
      root.render(<LegalNotices onClose={onClose} />);
    });
    act(() => {
      container.querySelector('button')?.dispatchEvent(new MouseEvent('click', { bubbles: true }));
    });

    expect(onClose).toHaveBeenCalledOnce();
  });
});
