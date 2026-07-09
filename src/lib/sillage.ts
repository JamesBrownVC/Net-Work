// Placeholder integration module for Sillage signal enrichment.
// It will later provide buying intent, hiring, and champion-tracking signals.

export async function fetchSignals(accountId: string) {
  return {
    accountId,
    signals: [],
    source: 'Sillage placeholder',
  };
}
