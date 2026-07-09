// Types describing the meeting context that the orchestration flow will prepare for.

export interface Meeting {
  id: string;
  accountId: string;
  accountName: string;
  scheduledAt: string;
  objective: string;
  location: string;
  attendees: string[];
}
