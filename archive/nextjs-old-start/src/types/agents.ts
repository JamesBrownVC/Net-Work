// Shared types for structured agent outputs and execution logging.

export type AgentStatus = 'success' | 'error';

export interface AgentEvidence {
  source: string;
  summary: string;
  confidence: number;
}

export interface AgentResult<T> {
  agent: string;
  status: AgentStatus;
  summary: string;
  reasoning: string[];
  evidence: AgentEvidence[];
  data: T;
}

export interface ExecutionLogStep {
  agent: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  message: string;
  timestamp: string;
}
