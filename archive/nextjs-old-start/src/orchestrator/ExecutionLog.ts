// ExecutionLog stores the lifecycle of each run for observability and later debugging.

import type { ExecutionLogStep } from '@/types';

export class ExecutionLog {
  private steps: ExecutionLogStep[] = [];

  addStep(step: ExecutionLogStep) {
    this.steps.push(step);
  }

  getSteps() {
    return this.steps;
  }

  clear() {
    this.steps = [];
  }
}
