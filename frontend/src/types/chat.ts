export type ComponentMigrationStatus = 
  | 'legacy'
  | 'migrated'
  | 'coupled'
  | 'decommissioned'
  | 'target_in_progress';

export interface SourceEvidence {
  position: {
    repoId: string;
    path: string;
    commitSha: string;
    startLine: number;
    endLine: number;
  };
  githubUrl: string;
  fragment: string;
}

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  thinking?: string;
  isThinkingOpen?: boolean;
  timestamp: string;
  evidence?: SourceEvidence[];
  status?: 'sending' | 'streaming' | 'done' | 'error';
  suggestedNextQueries?: string[];
  executionTimeMs?: number;
}

export interface QueryRequest {
  query: string;
  stepId?: string;
}

export interface QueryResponse {
  answer: string;
  thinking?: string;
  evidence: SourceEvidence[];
  stepId: string;
  executionTimeMs: number;
  suggestedNextQueries?: string[];
}
