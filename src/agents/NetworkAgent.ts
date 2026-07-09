// NetworkAgent prepares the rep before the meeting by gathering references, social proof, and expansion signals.

import type { AgentEvidence, AgentResult } from '@/types';
import type { DemoScenario } from '@/data/demoScenario';

export interface NetworkAgentOutput {
  references: string[];
  warmConnections: string[];
  upsellOpportunities: string[];
  socialProof: string[];
  meetingBrief: string[];
}

export class NetworkAgent {
  async run(scenario: DemoScenario): Promise<AgentResult<NetworkAgentOutput>> {
    const references = scenario.references.map((item) => `${item.name} — ${item.story}`);
    const warmConnections = scenario.warmIntroductions.map((intro) => `${intro.from} → ${intro.to}: ${intro.context}`);
    const upsellOpportunities = scenario.upsellOpportunities.map((item) => `${item.name}: ${item.description}`);
    const socialProof = [
      `A similar customer reduced month-end close time by 38% using ${scenario.upsellOpportunities[0].name}.`,
      'Another customer expanded from one module to three within nine months.',
    ];

    const evidence: AgentEvidence[] = [
      {
        source: 'CRM history',
        summary: `Observed recent engagement with ${scenario.currentCustomer.name} and strong expansion signals.`,
        confidence: 0.9,
      },
      {
        source: 'Reference portfolio',
        summary: 'Matched similar customers in the same growth stage and product category.',
        confidence: 0.88,
      },
    ];

    return {
      agent: 'NetworkAgent',
      status: 'success',
      summary: 'Gathered relevant customer references and expansion opportunities for the upcoming meeting.',
      reasoning: [
        'The current customer has a strong revenue base and clear expansion signals.',
        'Reference stories from adjacent companies help create credible social proof.',
      ],
      evidence,
      data: {
        references,
        warmConnections,
        upsellOpportunities,
        socialProof,
        meetingBrief: [
          `Review the ${scenario.currentCustomer.name} relationship before the renewal discussion`,
          'Lead with the strongest customer proof points around automation and controls',
        ],
      },
    };
  }
}
