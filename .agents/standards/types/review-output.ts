export const REVIEW_OUTPUT_SCHEMA_VERSION = 2

export const REVIEWER_TYPES = [
  'stream',
  'work-order-readiness',
  'work-order-review',
  'verification',
  'wave-pre-dispatch',
] as const

export const FINDING_SEVERITIES = [
  'blocking',
  'advisory',
  'observation',
] as const

export const FINDING_CATEGORIES = [
  'ig-drift',
  'metadata-drift',
  'dead-code',
  'sync-gap',
  'anti-pattern-propagation',
  'scope-creep',
  'test-quality',
  'adr-compliance',
  'acceptance-drift',
  'premise-verification',
  'duplicate-detection',
  'empty-spec',
  'cross-repo-placement',
  'seed-data-drift',
  'ac-incomplete',
  'verification-claim-mismatch',
] as const

export const FINDING_DISPOSITIONS = [
  'keep',
  'fold',
  'weed',
  'move-to-sibling',
  'cluster-into-epic',
] as const

export const EVIDENCE_TYPES = [
  'file',
  'git',
  'registry',
  'work-order-field',
  'shell',
] as const

export const SUGGESTED_ACTION_TYPES = [
  'file_work_order',
  'fix_code',
  'update_close_reason',
  'sync_standard',
  'add_dependency',
  'delete_dead_code',
  'save_feedback_memory',
  'fold_into_work_order',
  'move_to_sibling_repo',
  'weed_with_reason',
  'no_action',
] as const

export const COHORT_SELECTOR_TYPES = [
  'epic',
  'wave',
  'label',
  'time-window',
] as const

export type ReviewOutputSchemaVersion = typeof REVIEW_OUTPUT_SCHEMA_VERSION

export type ReviewerType = typeof REVIEWER_TYPES[number]

export type FindingSeverity = typeof FINDING_SEVERITIES[number]

export type KnownFindingCategory = typeof FINDING_CATEGORIES[number]

export type FindingCategory = KnownFindingCategory | (string & {})

export type FindingDisposition = typeof FINDING_DISPOSITIONS[number]

export type EvidenceType = typeof EVIDENCE_TYPES[number]

export type SuggestedActionType = typeof SUGGESTED_ACTION_TYPES[number]

export type CohortSelectorType = typeof COHORT_SELECTOR_TYPES[number]

export type ReviewOutput = {
  schema_version: ReviewOutputSchemaVersion
  review: Review
  verdict: ReviewVerdict
  findings: Finding[]
  stamps?: PerWorkOrderStamp[]
}

export type Review = {
  run_id: string
  reviewer_type: ReviewerType
  reviewer_agent_sha?: string
  cohort: CohortSelector | SingleWorkOrderCohort
  started_at: string
  completed_at: string
  member_count: number
  cohort_age_days?: number
}

export type ReviewVerdict = 'clean' | 'findings' | 'dispute' | 'partial'

export type Finding = {
  id: string
  severity: FindingSeverity
  category: FindingCategory
  disposition: FindingDisposition
  title: string
  touches_work_orders: string[]
  evidence: Evidence[]
  suggested_action: SuggestedAction
  confidence: number
  context_from_prior_reviews?: PriorReviewContext[]
}

export type Evidence =
  | FileEvidence
  | GitEvidence
  | RegistryEvidence
  | WorkOrderFieldEvidence
  | ShellEvidence

export type FileEvidence = {
  type: 'file'
  path: string
  lines?: string
}

export type GitEvidence = {
  type: 'git'
  commit_sha: string
  note?: string
}

export type RegistryEvidence = {
  type: 'registry'
  source: string
  note?: string
}

export type WorkOrderFieldEvidence = {
  type: 'work-order-field'
  work_order_id: string
  field: string
  value: unknown
}

export type ShellEvidence = {
  type: 'shell'
  command: string
  output_excerpt: string
}

export type SuggestedAction =
  | FileWorkOrderAction
  | FixCodeAction
  | UpdateCloseReasonAction
  | SyncStandardAction
  | AddDependencyAction
  | DeleteDeadCodeAction
  | SaveFeedbackMemoryAction
  | FoldIntoWorkOrderAction
  | MoveToSiblingRepoAction
  | WeedWithReasonAction
  | NoAction

export type FileWorkOrderAction = {
  type: 'file_work_order'
  draft: {
    title: string
    description: string
    type: string
    priority: number
    labels: string[]
    dependencies?: string[]
  }
}

export type FixCodeAction = {
  type: 'fix_code'
  diff: string
  verify: string[]
}

export type UpdateCloseReasonAction = {
  type: 'update_close_reason'
  work_order_id: string
  new_reason: string
}

export type SyncStandardAction = {
  type: 'sync_standard'
  from: string
  to: string
  new_source_commit: string
}

export type AddDependencyAction = {
  type: 'add_dependency'
  from_work_order: string
  to_work_order: string
  dep_type: 'blocks' | 'related'
}

export type DeleteDeadCodeAction = {
  type: 'delete_dead_code'
  paths: string[]
  rationale: string
}

export type SaveFeedbackMemoryAction = {
  type: 'save_feedback_memory'
  name: string
  content: string
}

export type FoldIntoWorkOrderAction = {
  type: 'fold_into_work_order'
  sources: string[]
  target: string
}

export type MoveToSiblingRepoAction = {
  type: 'move_to_sibling_repo'
  work_order_id: string
  target_repo: string
}

export type WeedWithReasonAction = {
  type: 'weed_with_reason'
  work_order_id: string
  reason: string
  cited_evidence: Evidence[]
}

export type NoAction = {
  type: 'no_action'
  rationale: string
}

export type PerWorkOrderStamp = {
  work_order_id: string
  stamp: Record<string, unknown>
}

export type CohortSelector = {
  type: CohortSelectorType
  value: string
}

export type SingleWorkOrderCohort = {
  type: 'single-work-order'
  id: string
}

export type PriorReviewContext = {
  run_id: string
  reviewed_at: string
  verdict: string
}
