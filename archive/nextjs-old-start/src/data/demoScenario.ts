// Demo scenario for the hackathon experience: Qonto as target account and PayFit as an existing customer.

import type { Account, Customer, Meeting, CRMInteraction, CustomerReference, UpsellOpportunity, BuyingCommitteeMember, ContactEnrichment } from '@/types';

export interface DemoScenario {
  targetAccount: Account;
  currentCustomer: Customer;
  meeting: Meeting;
  crmHistory: CRMInteraction[];
  references: CustomerReference[];
  upsellOpportunities: UpsellOpportunity[];
  buyingCommittee: BuyingCommitteeMember[];
  warmIntroductions: Array<{ from: string; to: string; context: string }>;
  buyingIntentSignals: Array<{ signal: string; source: string; confidence: number }>;
  enrichedContacts: ContactEnrichment[];
}

export const demoScenario: DemoScenario = {
  targetAccount: {
    id: 'acct-qonto',
    name: 'Qonto',
    industry: 'Fintech',
    website: 'https://qonto.com',
    employeeCount: 1200,
    region: 'Europe',
    currentProducts: ['Expense Management', 'Corporate Cards'],
    contractValue: 240000,
    renewalDate: '2027-03-01',
    lastContactDate: '2026-06-28',
    relationshipRisk: 'medium',
    notes: [
      'Expanding finance operations across Europe',
      'Strong interest in treasury automation',
    ],
  },
  currentCustomer: {
    id: 'cust-payfit',
    name: 'PayFit',
    industry: 'HR Tech',
    size: '2,000+ employees',
    currentProducts: ['Payroll Automation', 'Pension Management'],
    contractValue: 320000,
    lastContactDate: '2026-06-05',
    relationshipRisk: 'high',
    revenueAtRisk: 320000,
    primaryContact: 'Camille Laurent',
    meetingContext: 'Upcoming renewal and expansion discussion',
  },
  meeting: {
    id: 'mtg-payfit-01',
    accountId: 'cust-payfit',
    accountName: 'PayFit',
    scheduledAt: '2026-07-10T14:00:00Z',
    objective: 'Re-engage the account before renewal and anchor an expansion conversation',
    location: 'Virtual',
    attendees: ['Camille Laurent', 'Alex Dubois', 'Nora Kim'],
  },
  crmHistory: [
    {
      id: 'crm-1',
      accountId: 'cust-payfit',
      relatedAccount: 'PayFit',
      summary: 'Executive sponsor call confirmed renewed interest in AP automation after last quarter’s onboarding delays.',
      date: '2026-06-20',
      channel: 'call',
      outcome: 'Warm follow-up requested',
      source: 'Salesforce',
    },
    {
      id: 'crm-2',
      accountId: 'cust-payfit',
      relatedAccount: 'PayFit',
      summary: 'Customer success flagged onboarding friction and requested a strategic review before the renewal conversation.',
      date: '2026-06-12',
      channel: 'note',
      outcome: 'Relationship risk elevated',
      source: 'Customer Success',
    },
  ],
  references: [
    {
      id: 'ref-1',
      name: 'Luko',
      industry: 'Insurtech',
      story: 'Implemented treasury automation across 14 markets and reduced month-end close time by 38%.',
      relevantProduct: 'Treasury Automation',
      outcome: 'Expanded from 1 module to 3 within 9 months',
      source: 'Customer case study',
    },
    {
      id: 'ref-2',
      name: 'Malt',
      industry: 'HR Tech',
      story: 'Adopted spend controls and finance workflow automation ahead of a rapid hiring cycle.',
      relevantProduct: 'Spend Controls',
      outcome: 'Achieved 22% faster approval throughput',
      source: 'Reference call',
    },
  ],
  upsellOpportunities: [
    {
      name: 'Treasury Automation',
      description: 'Multi-entity cash visibility and approval workflows for scaling finance teams.',
      whyNow: 'PayFit is already operating at scale and has flagged finance process friction.',
      estimatedValue: 95000,
      confidence: 0.87,
    },
    {
      name: 'Advanced AP Automation',
      description: 'Invoice ingestion and approval routing for high-volume operations.',
      whyNow: 'The customer has recently increased operational complexity and needs more automation.',
      estimatedValue: 72000,
      confidence: 0.81,
    },
  ],
  buyingCommittee: [
    {
      name: 'Claire Martin',
      title: 'VP Finance',
      influence: 'high',
      motivation: 'Reduce month-end close complexity and improve controls',
      approach: 'Lead with tangible process savings and implementation readiness',
    },
    {
      name: 'Julien Petit',
      title: 'Head of Procurement',
      influence: 'medium',
      motivation: 'Consolidate vendors and rationalize tool sprawl',
      approach: 'Frame the solution around efficiency and governance',
    },
    {
      name: 'Sophie Leroux',
      title: 'Director of Operations',
      influence: 'medium',
      motivation: 'Create more predictable finance operations',
      approach: 'Use a pilot-led story and implementation confidence',
    },
  ],
  warmIntroductions: [
    {
      from: 'Nicolas Bell',
      to: 'Claire Martin',
      context: 'Former operator at a fintech scale-up now advising Qonto on finance tooling',
    },
    {
      from: 'Mina Rahal',
      to: 'Julien Petit',
      context: 'Shared investor network and prior procurement transformation work',
    },
  ],
  buyingIntentSignals: [
    {
      signal: 'Qonto recently hired a Head of Treasury Operations',
      source: 'Sillage',
      confidence: 0.92,
    },
    {
      signal: 'Finance leadership is evaluating multi-entity controls and automation',
      source: 'Sillage',
      confidence: 0.88,
    },
  ],
  enrichedContacts: [
    {
      name: 'Claire Martin',
      title: 'VP Finance',
      email: 'claire.martin@qonto.com',
      phone: '+33 6 12 34 56 78',
      linkedin: 'https://linkedin.com/in/clairemartin',
      confidence: 0.95,
    },
    {
      name: 'Julien Petit',
      title: 'Head of Procurement',
      email: 'julien.petit@qonto.com',
      phone: '+33 6 98 76 54 32',
      linkedin: 'https://linkedin.com/in/julienpetit',
      confidence: 0.91,
    },
  ],
};
