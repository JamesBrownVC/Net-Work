// Types for customer relationships and reference stories used by the network agent.

export interface Customer {
  id: string;
  name: string;
  industry: string;
  size: string;
  currentProducts: string[];
  contractValue: number;
  lastContactDate: string;
  relationshipRisk: 'low' | 'medium' | 'high';
  revenueAtRisk: number;
  primaryContact: string;
  meetingContext: string;
}

export interface CustomerReference {
  id: string;
  name: string;
  industry: string;
  story: string;
  relevantProduct: string;
  outcome: string;
  source: string;
}
