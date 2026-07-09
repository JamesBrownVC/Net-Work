// RelationshipAgent monitors customer health and flags relationship risks or opportunities.

import type { AgentEvidence, AgentResult, RelationshipHealth } from '@/types';
import type { DemoScenario } from '@/data/demoScenario';

export interface RelationshipAgentOutput {
  health: RelationshipHealth;
  recommendation: string;
  evidence: string[];
}

export class RelationshipAgent {
  async run(scenario: DemoScenario): Promise<AgentResult<RelationshipAgentOutput>> {
    const health: RelationshipHealth = {
      level: 'critical',
      score: 28,
      summary: `${scenario.currentCustomer.name} is a high-value account, but it has gone quiet and is now at risk before renewal.`,
      recommendedAction: 'Re-engage with an executive-led check-in and delay any broad upsell conversation until trust is restored.',
      evidence: [
        `Last contact was ${scenario.currentCustomer.lastContactDate}`,
        `Annual contract value is ${scenario.currentCustomer.contractValue.toLocaleString()} EUR`,
        'Customer success flagged onboarding friction and requested a strategic review',
      ],
    };

    const evidence: AgentEvidence[] = [
      {
        source: 'CRM timeline',
        summary: 'The account has had a recent lapse in engagement despite strong revenue value.',
        confidence: 0.95,
      },
      {
        source: 'Customer success notes',
        summary: 'Operational friction and renewal timing are creating relationship risk.',
        confidence: 0.91,
      },
    ];

    return {
      agent: 'RelationshipAgent',
      status: 'success',
      summary: 'Detected a high-value but neglected account that needs immediate relationship repair.',
      reasoning: [
        'The account has high annual value but a gap in recent engagement.',
        'The combination of renewal timing and recent friction makes the relationship vulnerable.',
      ],
      evidence,
      data: {
        health,
        recommendation: 'Schedule a leadership outreach this week and focus on trust restoration before upselling.',
        evidence: health.evidence,
      },
    };
  }
}
