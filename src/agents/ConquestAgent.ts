// ConquestAgent builds the best path to win a strategic target account.

import type { AgentEvidence, AgentResult, BuyingCommitteeMember, ConquestPathStep } from '@/types';
import type { DemoScenario } from '@/data/demoScenario';

export interface ConquestAgentOutput {
  targetAccount: string;
  committee: BuyingCommitteeMember[];
  path: ConquestPathStep[];
  warmIntros: string[];
}

export class ConquestAgent {
  async run(scenario: DemoScenario): Promise<AgentResult<ConquestAgentOutput>> {
    const path: ConquestPathStep[] = [
      {
        step: 1,
        person: 'Claire Martin',
        objective: 'Earn a direct conversation around finance efficiency and controls',
        message: 'We can help reduce month-end complexity with a focused pilot and measurable ROI.',
        whyThisPerson: 'She is the highest-influence stakeholder and owns the operational pain point.',
        nextTransition: 'Move to an executive sponsor conversation after a positive reply.',
      },
      {
        step: 2,
        person: 'Julien Petit',
        objective: 'Address procurement consolidation and vendor rationalization',
        message: 'We can help simplify tooling and reduce implementation overhead across the team.',
        whyThisPerson: 'He can influence vendor selection and governance priorities.',
        nextTransition: 'Bring in a solution-focused follow-up after the procurement discussion.',
      },
      {
        step: 3,
        person: 'Sophie Leroux',
        objective: 'Create implementation confidence and pilot buy-in',
        message: 'A small pilot can validate the workflow changes before a broader rollout.',
        whyThisPerson: 'She is most likely to sponsor a pragmatic implementation plan.',
        nextTransition: 'Close with an executive recap and a proposed next-step meeting.',
      },
    ];

    const evidence: AgentEvidence[] = [
      {
        source: 'Buying intent signals',
        summary: 'The account is hiring in treasury and evaluating controls automation.',
        confidence: 0.92,
      },
      {
        source: 'Contact enrichment',
        summary: 'The core buying committee members have been identified with strong contact confidence.',
        confidence: 0.95,
      },
    ];

    return {
      agent: 'ConquestAgent',
      status: 'success',
      summary: 'Built a targeted path to win the account through the right stakeholders and warm intros.',
      reasoning: [
        'The buying committee is concentrated around finance and operations, which fits the product narrative.',
        'Warm introductions can materially improve the chances of a meeting with the right decision-makers.',
      ],
      evidence,
      data: {
        targetAccount: scenario.targetAccount.name,
        committee: scenario.buyingCommittee,
        path,
        warmIntros: scenario.warmIntroductions.map((intro) => `${intro.from} → ${intro.to}`),
      },
    };
  }
}
