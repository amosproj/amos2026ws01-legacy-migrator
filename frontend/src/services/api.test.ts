import { describe, it, expect, vi, beforeEach } from 'vitest';
import { checkBackendHealth, submitMigrationQuery } from './api';

function ndjsonBody(lines: string[]): ReadableStream<Uint8Array> {
  const encoder = new TextEncoder();
  const text = lines.map((l) => `${l}\n`).join('');
  return new ReadableStream({
    start(controller) {
      controller.enqueue(encoder.encode(text));
      controller.close();
    },
  });
}

const noopCallbacks = { onSources: () => {}, onThinking: () => {}, onDelta: () => {} };

describe('Frontend API Service', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  describe('checkBackendHealth', () => {
    it('returns backendAvailable=true and the model when /api/health responds 200', async () => {
      globalThis.fetch = vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({
          status: 'ok',
          service: 'sunsettracker-backend',
          version: '0.2.0',
          model: 'openai-compatible (qwen3.5:0.8b)',
        }),
      } as unknown as Response);

      const status = await checkBackendHealth();
      expect(status.backendAvailable).toBe(true);
      expect(status.model).toBe('openai-compatible (qwen3.5:0.8b)');
      expect(status.message).toContain('sunsettracker-backend v0.2.0');
    });

    it('returns backendAvailable=false fallback when fetch fails', async () => {
      globalThis.fetch = vi.fn().mockRejectedValue(new Error('Connection refused'));

      const status = await checkBackendHealth();
      expect(status.backendAvailable).toBe(false);
      expect(status.message).toContain('Backend Offline');
    });
  });

  describe('submitMigrationQuery', () => {
    it('streams content deltas and assembles the answer', async () => {
      globalThis.fetch = vi.fn().mockResolvedValue({
        ok: true,
        body: ndjsonBody([
          JSON.stringify({ type: 'sources', text: JSON.stringify(['llm:mock']) }),
          JSON.stringify({ type: 'content', text: 'Catalog service ' }),
          JSON.stringify({ type: 'content', text: 'was migrated.' }),
        ]),
      } as unknown as Response);

      const deltas: string[] = [];
      const res = await submitMigrationQuery(
        { query: 'Tell me about catalog', stepId: 'step-06' },
        { onSources: () => {}, onThinking: () => {}, onDelta: (t) => deltas.push(t) },
      );

      expect(res.answer).toBe('Catalog service was migrated.');
      expect(deltas).toEqual(['Catalog service ', 'was migrated.']);
      expect(res.stepId).toBe('step-06');
      expect(res.evidence.length).toBeGreaterThan(0);
    });

    it('streams thinking deltas and reports them in the response', async () => {
      globalThis.fetch = vi.fn().mockResolvedValue({
        ok: true,
        body: ndjsonBody([
          JSON.stringify({ type: 'sources', text: JSON.stringify(['llm:mock']) }),
          JSON.stringify({ type: 'thinking', text: 'Let me' }),
          JSON.stringify({ type: 'thinking', text: ' check' }),
          JSON.stringify({ type: 'content', text: 'Yes.' }),
        ]),
      } as unknown as Response);

      const thinking: string[] = [];
      const deltas: string[] = [];
      const onThinking = (t: string) => thinking.push(t);
      const onDelta = (t: string) => deltas.push(t);
      const res = await submitMigrationQuery(
        { query: 'anything', stepId: 'step-06' },
        { onSources: () => {}, onThinking, onDelta },
      );

      expect(thinking).toEqual(['Let me', ' check']);
      expect(deltas).toEqual(['Yes.']);
      expect(res.thinking).toBe('Let me check');
    });

    it('throws a visible error on an error stream event', async () => {
      globalThis.fetch = vi.fn().mockResolvedValue({
        ok: true,
        body: ndjsonBody([
          JSON.stringify({ type: 'sources', text: JSON.stringify([]) }),
          JSON.stringify({ type: 'error', text: 'LLM provider request failed' }),
        ]),
      } as unknown as Response);

      await expect(
        submitMigrationQuery({ query: 'anything', stepId: 'step-06' }, noopCallbacks),
      ).rejects.toThrow('LLM provider request failed');
    });

    it('throws a visible error when the backend is unreachable', async () => {
      globalThis.fetch = vi.fn().mockRejectedValue(new Error('Backend down'));

      await expect(
        submitMigrationQuery(
          { query: 'Which parts are decommissioned?', stepId: 'step-06' },
          noopCallbacks,
        ),
      ).rejects.toThrow('Backend unreachable');
    });

    it('throws a visible error when the backend returns a non-2xx status', async () => {
      globalThis.fetch = vi.fn().mockResolvedValue({
        ok: false,
        status: 502,
        json: async () => ({ detail: 'LLM provider request failed' }),
      } as unknown as Response);

      await expect(
        submitMigrationQuery({ query: 'anything', stepId: 'step-06' }, noopCallbacks),
      ).rejects.toThrow('HTTP 502: LLM provider request failed');
    });
  });
});
