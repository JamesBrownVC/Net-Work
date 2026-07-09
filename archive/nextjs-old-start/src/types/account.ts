// Core business type for the target account or existing customer being analyzed.

export interface Account {
  id: string;
  name: string;
  industry: string;
  website: string;
  employeeCount: number;
  region: string;
  currentProducts: string[];
  contractValue: number;
  renewalDate: string;
  lastContactDate: string;
  relationshipRisk: 'low' | 'medium' | 'high';
  notes: string[];
}

export interface ContactEnrichment {
  name: string;
  title: string;
  email: string;
  phone: string;
  linkedin: string;
  confidence: number;
}
