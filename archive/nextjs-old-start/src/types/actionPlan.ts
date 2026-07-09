// Structured final action plan returned to the sales representative.

export interface UpsellOpportunity {
  name: string;
  description: string;
  whyNow: string;
  estimatedValue: number;
  confidence: number;
}

export interface RelationshipHealth {
  level: 'healthy' | 'at-risk' | 'critical';
  score: number;
  summary: string;
  recommendedAction: string;
  evidence: string[];
}

export interface BuyingCommitteeMember {
  name: string;
  title: string;
  influence: 'high' | 'medium' | 'low';
  motivation: string;
  approach: string;
}

export interface ConquestPathStep {
  step: number;
  person: string;
  objective: string;
  message: string;
  whyThisPerson: string;
  nextTransition: string;
}

export interface FinalActionPlan {
  executiveSummary: string;
  meetingBrief: string[];
  networkReferences: string[];
  relationshipRisk: RelationshipHealth;
  upsellOpportunities: UpsellOpportunity[];
  conquestPath: ConquestPathStep[];
  talkingPoints: string[];
  nextActions: string[];
}
