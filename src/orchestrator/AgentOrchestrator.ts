// AgentOrchestrator coordinates the multi-agent workflow and collects outputs into one plan.

import { ClaudeStrategyAgent } from '@/agents/ClaudeStrategyAgent';
import { ConquestAgent } from '@/agents/ConquestAgent';
import { NetworkAgent } from '@/agents/NetworkAgent';
import { RelationshipAgent } from '@/agents/RelationshipAgent';
import { demoScenario } from '@/data/demoScenario';
import type { FinalActionPlan, AgentResult, ExecutionLogStep } from '@/types';
import { ExecutionLog } from './ExecutionLog';

export interface OrchestratorResult {
  scenario: typeof demoScenario;
  networkAgentResult: AgentResult<Awaited<ReturnType<NetworkAgent['run']>>['data']>;
  relationshipAgentResult: AgentResult<Awaited<ReturnType<RelationshipAgent['run']>>['data']>;
  conquestAgentResult: AgentResult<Awaited<ReturnType<ConquestAgent['run']>>['data']>;
  finalActionPlan: FinalActionPlan;
  executionLog: ExecutionLogStep[];
}

export class AgentOrchestrator {
  private log = new ExecutionLog();

  async run(): Promise<OrchestratorResult> {
    const scenario = demoScenario;

    this.log.addStep({ agent: 'network', status: 'running', message: 'Collecting references and expansion signals', timestamp: new Date().toISOString() });
    const networkAgentResult = await new NetworkAgent().run(scenario);
    this.log.addStep({ agent: 'network', status: 'completed', message: 'Reference and proof points gathered', timestamp: new Date().toISOString() });

    this.log.addStep({ agent: 'relationship', status: 'running', message: 'Assessing relationship health', timestamp: new Date().toISOString() });
    const relationshipAgentResult = await new RelationshipAgent().run(scenario);
    this.log.addStep({ agent: 'relationship', status: 'completed', message: 'Relationship health scored', timestamp: new Date().toISOString() });

    this.log.addStep({ agent: 'conquest', status: 'running', message: 'Designing the account conquest path', timestamp: new Date().toISOString() });
    const conquestAgentResult = await new ConquestAgent().run(scenario);
    this.log.addStep({ agent: 'conquest', status: 'completed', message: 'Buying committee and path prepared', timestamp: new Date().toISOString() });

    this.log.addStep({ agent: 'strategy', status: 'running', message: 'Synthesizing the unified action plan', timestamp: new Date().toISOString() });
    const strategyResult = await new ClaudeStrategyAgent().run(scenario, networkAgentResult, relationshipAgentResult, conquestAgentResult);
    this.log.addStep({ agent: 'strategy', status: 'completed', message: 'Final action plan generated', timestamp: new Date().toISOString() });

    return {
      scenario,
      networkAgentResult,
      relationshipAgentResult,
      conquestAgentResult,
      finalActionPlan: strategyResult.data,
      executionLog: this.log.getSteps(),
    };
  }

  getLog() {
    return this.log.getSteps();
  }
}
