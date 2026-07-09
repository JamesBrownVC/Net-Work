// Shared utility helpers for the application foundation.
// Keep lightweight helpers here so components and modules can reuse them cleanly.

export function cn(...classes: Array<string | undefined | false | null>) {
  return classes.filter(Boolean).join(' ');
}
