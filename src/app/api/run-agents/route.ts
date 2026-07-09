// API route for running the demo multi-agent workflow and returning the final plan.

import { NextResponse } from 'next/server';
import { AgentOrchestrator } from '@/orchestrator/AgentOrchestrator';

export async function POST() {
  const orchestrator = new AgentOrchestrator();
  const result = await orchestrator.run();

  return NextResponse.json(result);
}
