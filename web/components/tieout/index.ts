// The five DESIGN.md primitives, and only those five. Every downstream surface
// imports them from here so the design system has exactly one implementation.
export { DispositionBadge, type Disposition } from "./disposition-badge";
export { MoneyCell } from "./money-cell";
export { StatTile } from "./stat-tile";
export { AgingBuckets, AGING_BUCKETS, type AgingBucket } from "./aging-buckets";
export { CloseBanner, type CloseState } from "./close-banner";
