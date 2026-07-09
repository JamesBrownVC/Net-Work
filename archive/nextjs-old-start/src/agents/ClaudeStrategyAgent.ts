// ClaudeStrategyAgent is the synthesis layer that turns multi-agent insights into an action plan.
// The real orchestration flow will use this to create the final reusable plan output.

import type { FinalActionPlan } from '@/types';
import type { DemoScenario } from '@/data/demoScenario';
import type { AgentResult } from '@/types';
import type { NetworkAgentOutput } from './NetworkAgent';
import type { RelationshipAgentOutput } from './RelationshipAgent';
import type { ConquestAgentOutput } from './ConquestAgent';

export interface ClaudeStrategyAgentOutput extends FinalActionPlan {}

export class ClaudeStrategyAgent {
  async run(
    scenario: DemoScenario,
    networkResult: AgentResult<NetworkAgentOutput>,
    relationshipResult: AgentResult<RelationshipAgentOutput>,
    conquestResult: AgentResult<ConquestAgentOutput>,
  ): Promise<AgentResult<ClaudeStrategyAgentOutput>> {
    const plan: FinalActionPlan = {
      executiveSummary: `Re-engage ${scenario.currentCustomer.name} around renewal risk while opening a credible expansion story for ${scenario.targetAccount.name}.`,
      meetingBrief: [
        'Lead with relationship repair and renewed executive attention',
        'Use the strongest reference stories from similar growth-stage companies',
      ],
      networkReferences: networkResult.data.references,
      relationshipRisk: relationshipResult.data.health,
      upsellOpportunities: scenario.upsellOpportunities,
      conquestPath: conquestResult.data.path,
      talkingPoints: [
        'Focus on operational efficiency and measurable finance outcomes',
        'Position the conversation around trust restoration before broad upsell expansion',
      ],
      nextActions: [
        'Send a leadership outreach note before the next meeting',
        'Book a follow-up conversation with the buying committee after the first touch',
      ],
    };

    return {
      agent: 'ClaudeStrategyAgent',
      status: 'success',
      summary: 'Synthesized multi-agent insights into a unified action plan for the sales rep.',
      reasoning: [
        'The meeting should start with relationship repair and renewed executive attention.',
        'The path to expansion is strongest when it is tied to clear operational outcomes and credible social proof.',
      ],
      evidence: [
        {
          source: 'Agent synthesis',
          summary: 'Combined network, relationship, and conquest inputs into a single plan.',
          confidence: 0.93,
        },
      ],
      data: plan,
    };
  }
}
