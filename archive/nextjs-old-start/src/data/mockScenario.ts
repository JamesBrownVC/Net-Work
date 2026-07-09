// Mock scenario payload representing the incoming user request for the workflow engine.
// This is the shape the orchestrator can consume before real data providers are wired up.

export const mockScenario = {
  accountId: 'acct-001',
  context: 'Prepare for upcoming strategic account meeting',
  mode: 'expansion',
};
