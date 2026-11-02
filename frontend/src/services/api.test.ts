import { describe, it, expect, vi, beforeEach } from 'vitest';
import { checkBackendHealth, submitMigrationQuery } from './api';

describe('Frontend API Service', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  describe('checkBackendHealth', () => {
    it('returns backendAvailable=true when /api/health responds with 200', async () => {
      globalThis.fetch = vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({ status: 'ok', service: 'sunsettracker-backend', version: '0.2.0' }),
      } as unknown as Response);

      const status = await checkBackendHealth();
      expect(status.backendAvailable).toBe(true);
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
    it('successfully maps backend response and sources', async () => {
      globalThis.fetch = vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({
          answer: 'Catalog service was migrated in step-06',
          conversation_id: 'step-06',
          sources: ['llm:openai-compatible (gemini-2.5-flash)'],
        }),
      } as unknown as Response);

      const res = await submitMigrationQuery({ query: 'Tell me about catalog', stepId: 'step-06' });
      expect(res.answer).toBe('Catalog service was migrated in step-06');
      expect(res.stepId).toBe('step-06');
      expect(res.evidence.length).toBeGreaterThan(0);
      expect(res.evidence[0].filePath).toBe('llm:openai-compatible (gemini-2.5-flash)');
    });

    it('throws a visible error when the backend is unreachable', async () => {
      globalThis.fetch = vi.fn().mockRejectedValue(new Error('Backend down'));

      await expect(
        submitMigrationQuery({
          query: 'Which parts of the legacy system have already been decommissioned in Step-06?',
          stepId: 'step-06',
        }),
      ).rejects.toThrow('Backend unreachable');
    });

    it('throws a visible error when the backend returns a non-2xx status', async () => {
      globalThis.fetch = vi.fn().mockResolvedValue({
        ok: false,
        status: 502,
        json: async () => ({ detail: 'LLM provider request failed' }),
      } as unknown as Response);

      await expect(
        submitMigrationQuery({ query: 'anything', stepId: 'step-06' }),
      ).rejects.toThrow('HTTP 502: LLM provider request failed');
    });
  });
});
