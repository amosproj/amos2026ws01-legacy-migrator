export type ComponentMigrationStatus = 
  | 'legacy'
  | 'migrated'
  | 'coupled'
  | 'decommissioned'
  | 'target_in_progress';

export interface SourceEvidence {
  id: string;
  repoId: string;
  repoUrl: string;
  filePath: string;
  startLine?: number;
  endLine?: number;
  commitSha: string;
  status: ComponentMigrationStatus;
  snippet?: string;
  description: string;
}

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
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
  evidence: SourceEvidence[];
  stepId: string;
  executionTimeMs: number;
  suggestedNextQueries?: string[];
}
