# Account Conquest Room

AI-native GTM agent platform for account intelligence, relationship management, and conquest planning.

## Tech Stack
- Next.js App Router
- TypeScript
- Tailwind CSS
- Framer Motion
- shadcn/ui
- Node.js

## Folder Structure
```text
src/
  app/
    page.tsx
    layout.tsx
    api/
      run-agents/
        route.ts
      generate-plan/
        route.ts
  agents/
    NetworkAgent.ts
    RelationshipAgent.ts
    ConquestAgent.ts
    ClaudeStrategyAgent.ts
    index.ts
  orchestrator/
    AgentOrchestrator.ts
    ExecutionLog.ts
  data/
    demoScenario.ts
  types/
  lib/
  components/
```

## Install
```bash
npm install
```

## Run Locally
```bash
npm run dev
```
Then open http://localhost:3000.

## Environment Variables
Copy .env.example to .env.local and fill in the required values:

```bash
cp .env.example .env.local
```

Required keys:
- ANTHROPIC_API_KEY
- SILLAGE_API_KEY
- FULLENRICH_API_KEY

## Team Task Split
- Frontend & experience: UI components, layout, and demo views
- Agents & orchestration: agent logic, orchestration flow, and planning output
- Data & integrations: mock data, CRM enrichment hooks, and future provider adapters
- Product & demos: PRD alignment, demo script, and stakeholder storytelling

## Build Check
```bash
npm run build
```
