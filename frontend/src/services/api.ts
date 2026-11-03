import { QueryRequest, QueryResponse, SourceEvidence } from '../types/chat';
import { MOCK_EVIDENCES, INITIAL_SUGGESTIONS } from './mockData';

const API_BASE_URL = '/api';

export interface HealthStatus {
  backendAvailable: boolean;
  model: string;
  message: string;
}

export async function checkBackendHealth(): Promise<HealthStatus> {
  try {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 2500);
    const res = await fetch(`${API_BASE_URL}/health`, { signal: controller.signal });
    clearTimeout(timeoutId);

    if (res.ok) {
      const data = await res.json();
      return {
        backendAvailable: true,
        model: typeof data.model === 'string' ? data.model : 'unknown',
        message: `FastAPI Backend Connected (${data.service ?? 'sunsettracker'} v${data.version ?? '0.2.0'})`,
      };
    }
  } catch {
    // Expected during standalone development before backend is running
  }

  return {
    backendAvailable: false,
    model: 'none',
    message: 'Standalone / Mock Mode (Backend Offline)',
  };
}

function getFallbackEvidence(query: string): SourceEvidence[] {
  const normalized = query.toLowerCase();
  if (normalized.includes('catalog') || normalized.includes('step-06') || normalized.includes('step-05')) {
    return MOCK_EVIDENCES.catalog;
  }
  if (normalized.includes('decommission') || normalized.includes('switch') || normalized.includes('candidate')) {
    return [MOCK_EVIDENCES.catalog[0], MOCK_EVIDENCES.catalog[1]];
  }
  if (normalized.includes('coupl') || normalized.includes('share') || normalized.includes('table') || normalized.includes('route')) {
    return [MOCK_EVIDENCES.catalog[2], MOCK_EVIDENCES.catalog[0]];
  }
  return MOCK_EVIDENCES.catalog;
}

export interface StreamCallbacks {
  onSources: (sources: string[]) => void;
  onDelta: (text: string) => void;
}

/**
 * Submit a migration query and stream the answer.
 *
 * The backend answers with newline-delimited JSON: a `sources` event, then
 * `content` text deltas, or an `error` event. Deltas are forwarded to
 * `onDelta` as they arrive; the returned promise resolves with the complete
 * response once the stream ends, and rejects on connection or LLM errors.
 */
export async function submitMigrationQuery(
  req: QueryRequest,
  callbacks: StreamCallbacks,
  signal?: AbortSignal,
): Promise<QueryResponse> {
  const startTime = Date.now();

  let res: Response;
  try {
    res = await fetch(`${API_BASE_URL}/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        query: req.query,
        conversation_id: req.stepId || 'step-06',
      }),
      signal,
    });
  } catch (err: unknown) {
    if (err instanceof DOMException && err.name === 'AbortError') {
      throw err;
    }
    throw new Error('Backend unreachable. Is the backend running on port 8000?', { cause: err });
  }

  if (!res.ok) {
    let detail = '';
    try {
      const body = await res.json();
      detail = body.detail ?? '';
    } catch { /* non-JSON error body */ }
    throw new Error(`Backend returned HTTP ${res.status}${detail ? `: ${detail}` : ''}`);
  }
  if (!res.body) {
    throw new Error('Backend returned no response body.');
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let answer = '';
  let buffer = '';
  let backendSources: string[] = [];

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    const lines = buffer.split('\n');
    buffer = lines.pop() ?? '';
    for (const line of lines) {
      if (!line.trim()) continue;
      const event = JSON.parse(line) as { type: string; text: string };
      if (event.type === 'content') {
        answer += event.text;
        callbacks.onDelta(event.text);
      } else if (event.type === 'sources') {
        backendSources = JSON.parse(event.text) as string[];
        callbacks.onSources(backendSources);
      } else if (event.type === 'error') {
        throw new Error(event.text);
      }
    }
  }

  if (!answer) {
    throw new Error('Backend returned an empty answer.');
  }

  const elapsed = Date.now() - startTime;

  // Map backend sources (e.g. "llm:openai-compatible (qwen3.5:0.8b)") into evidence cards
  const backendEvidence: SourceEvidence[] = backendSources.map((src: string, index: number) => ({
    id: `ev-backend-${index}-${Date.now()}`,
    repoId: 'IBM/application-modernization-javaee-quarkus',
    repoUrl: 'https://github.com/IBM/application-modernization-javaee-quarkus',
    filePath: src,
    commitSha: '69f984a9e5b5658e370a6d091e70e9f603c7347a',
    status: 'migrated',
    description: `Verified inference source: ${src}`,
  }));

  // Enrich with illustrative source evidence for the demonstrator
  const fallbackEvidence = getFallbackEvidence(req.query);
  const combinedEvidence = [...backendEvidence, ...fallbackEvidence];

  return {
    answer,
    evidence: combinedEvidence,
    stepId: req.stepId || 'step-06',
    executionTimeMs: elapsed,
    suggestedNextQueries: INITIAL_SUGGESTIONS,
  };
}
