import { QueryRequest, QueryResponse, SourceEvidence } from '../types/chat';
import { INITIAL_SUGGESTIONS } from './mockData';

// Decoupled architecture: the browser calls the backend origin directly.
// Vite bakes VITE_BACKEND_URL (origin only, no path) into the build
// (Dockerfile ARG); in dev it is unset, so requests stay relative and the
// Vite dev/preview proxy forwards them to the backend on 127.0.0.1:8000.
const API_BASE_URL = `${import.meta.env.VITE_BACKEND_URL ?? ''}/api`;

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

function readEvidence(text: string): SourceEvidence[] {
  const fragments: SourceEvidence[] = JSON.parse(text);
  if (!Array.isArray(fragments)) return [];

  const byUrl = new Map<string, SourceEvidence>();
  for (const item of fragments) {
    const position = item?.position;
    if (
      !position || typeof item.githubUrl !== 'string' || typeof item.fragment !== 'string' ||
      typeof position.repoId !== 'string' || !position.repoId ||
      typeof position.path !== 'string' || !position.path ||
      typeof position.commitSha !== 'string' || !/^(?:[0-9a-f]{40}|[0-9a-f]{64})$/.test(position.commitSha) ||
      !Number.isSafeInteger(position.startLine) || position.startLine < 1 ||
      !Number.isSafeInteger(position.endLine) || position.endLine < position.startLine
    ) continue;

    try {
      const url = new URL(item.githubUrl);
      const [, owner, ...file] = decodeURIComponent(url.pathname).split('/');
      const expectedFile = `${position.repoId}/blob/${position.commitSha}/${position.path}`;
      const start = `#L${position.startLine}`;
      const range = `${start}-L${position.endLine}`;
      if (
        url.origin !== 'https://github.com' || url.username || url.password || !owner ||
        file.join('/') !== expectedFile ||
        (url.hash !== range && !(position.startLine === position.endLine && url.hash === start))
      ) continue;
      byUrl.set(url.href, { ...item, githubUrl: url.href });
    } catch {
      // A malformed source link is not evidence the reader can open.
    }
  }
  return [...byUrl.values()];
}

export interface StreamCallbacks {
  onThinking: (text: string) => void;
  onDelta: (text: string) => void;
}

/**
 * Submit a migration query and stream the answer.
 *
 * The backend answers with newline-delimited JSON. An optional `evidence`
 * event carries a JSON array of backend SourceFragment objects in `text`.
 * Legacy `sources` events carry model labels. Text and reasoning deltas are forwarded as they
 * arrive; the returned promise resolves with the complete
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
  let thinking = '';
  let buffer = '';
  let evidence: SourceEvidence[] = [];

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
      } else if (event.type === 'thinking') {
        thinking += event.text;
        callbacks.onThinking(event.text);
      } else if (event.type === 'evidence') {
        evidence = readEvidence(event.text);
      } else if (event.type === 'error') {
        throw new Error(event.text);
      }
    }
  }

  if (!answer) {
    throw new Error('Backend returned an empty answer.');
  }

  const elapsed = Date.now() - startTime;

  return {
    answer,
    thinking: thinking || undefined,
    evidence,
    stepId: req.stepId || 'step-06',
    executionTimeMs: elapsed,
    suggestedNextQueries: INITIAL_SUGGESTIONS,
  };
}
