Read PRD.md carefully.



This file is the source of truth for the project.



Now create the project architecture for Account Conquest Room.



Use:

\- Next.js App Router

\- TypeScript

\- TailwindCSS

\- Framer Motion

\- shadcn/ui

\- clean modular architecture



Create this folder structure:



src/

&#x20; app/

&#x20;   page.tsx

&#x20;   layout.tsx

&#x20;   api/

&#x20;     run-agents/

&#x20;       route.ts

&#x20;     generate-plan/

&#x20;       route.ts



&#x20; agents/

&#x20;   NetworkAgent.ts

&#x20;   RelationshipAgent.ts

&#x20;   ConquestAgent.ts

&#x20;   ClaudeStrategyAgent.ts

&#x20;   index.ts



&#x20; orchestrator/

&#x20;   AgentOrchestrator.ts

&#x20;   ExecutionLog.ts



&#x20; data/

&#x20;   mockAccounts.ts

&#x20;   mockCustomers.ts

&#x20;   mockCRM.ts

&#x20;   mockSignals.ts

&#x20;   mockContacts.ts

&#x20;   mockScenario.ts



&#x20; types/

&#x20;   account.ts

&#x20;   customer.ts

&#x20;   meeting.ts

&#x20;   crm.ts

&#x20;   agents.ts

&#x20;   actionPlan.ts

&#x20;   index.ts



&#x20; lib/

&#x20;   anthropic.ts

&#x20;   fullenrich.ts

&#x20;   sillage.ts

&#x20;   utils.ts



&#x20; components/

&#x20;   layout/

&#x20;   agents/

&#x20;   action-plan/

&#x20;   timeline/

&#x20;   ui/



Do not implement UI animations yet.

Do not build the final dashboard yet.

Focus only on the foundation, types, clean architecture, and placeholder files.



Each file should include comments explaining its responsibility so that multiple team members can work in parallel.



Also create:

\- .env.example

\- .gitignore

\- README.md



Make sure .gitignore excludes:

\- node\_modules

\- .next

\- .env

\- .env.local

\- .env.\*.local

