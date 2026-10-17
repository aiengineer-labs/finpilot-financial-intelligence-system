export type View = "overview" | "ledger" | "forecast" | "advice" | "audit" | "digests" | "governance" | "system";

export type Tenant = { id: string; name: string; role: string };
export type AccountType = "unknown" | "deposit" | "credit_card";
export type Account = { id: string; name: string; currency: string; account_type: AccountType };
export type Transaction = {
  id: string; account_id: string; transaction_date: string; amount_minor: number; balance_minor: number | null;
  currency: string; merchant_normalized: string; description: string; kind: string;
  category: string; classification_method: string; classification_confidence_bps: number;
  is_excluded_from_cashflow: boolean; source_evidence: Record<string, string | number>;
};
export type UploadResult = {
  id: string; filename: string; status: string; total_rows: number; accepted_rows: number;
  rejected_rows: number; duplicate_rows: number; replayed: boolean;
  row_errors: Array<Record<string, string | number>>;
  source_format: "csv" | "pdf"; detected_content_type: string; parser_name: string;
  parser_version: string; extraction_method: string; page_count: number | null; warnings: string[];
  processing_duration_ms: number; statement_kind: AccountType;
};
export type Pattern = {
  id: string; merchant: string; cadence: string; typical_amount_minor: number;
  confidence_bps: number; explanation?: string;
};
export type Anomaly = { transaction_id: string; severity: string; explanation: string };
export type SpendingCategory = {
  category: string; spend_minor: number; transaction_count: number; share_bps: number;
  monthly_spend_minor: number; monthly_saving_minor: number;
};
export type SpendingMerchant = { merchant: string; spend_minor: number; transaction_count: number; monthly_spend_minor: number };
export type RecurringCharge = { pattern_id: string; merchant: string; cadence: string; amount_minor: number; monthly_equivalent_minor: number };
export type SpendingSummary = {
  account_type: AccountType; period_start: string; period_end: string; period_days: number;
  total_spend_minor: number; inflow_minor: number; refunds_minor: number; net_flow_minor: number;
  savings_rate_bps: number | null; average_daily_spend_minor: number; projected_30_day_spend_minor: number;
  reduction_percent: number; combined_monthly_saving_minor: number;
  categories: SpendingCategory[]; merchants: SpendingMerchant[]; recurring_charges: RecurringCharge[];
};
export type Snapshot = {
  id: string; as_of: string; currency: string; opening_balance_minor: number | null;
  analysis_mode: "cashflow" | "spending"; spending: SpendingSummary | null;
  source_transaction_count: number; recurring_patterns: Pattern[]; anomaly_results: Anomaly[];
};
export type Point = { day: string; balance_minor: number; recurring_flow_minor: number; estimated_variable_spend_minor: number };
export type Forecast = { id: string; horizon_days: number; opening_balance_minor: number; minimum_balance_minor: number; assumptions: string[]; points: Point[] };
export type Scenario = { id: string; name: string; minimum_balance_minor: number; first_shortfall_date: string | null; ending_delta_minor: number; points: Point[] };
export type AgentEvent = {
  id: string; sequence: number; node: string; event_type: string; summary: string;
  details: Record<string, unknown>; model_id: string | null; latency_ms: number | null;
  input_tokens: number | null; output_tokens: number | null;
};
export type Recommendation = {
  id: string; rank: number; title: string; explanation: string; amount_minor: number | null;
  currency: string; evidence_ids: string[]; assumptions: string[]; confidence_bps: number;
  verification_status: string;
};
export type AgentRun = {
  id: string; snapshot_id: string; forecast_id: string | null; scenario_run_id: string | null;
  question: string; intent: string;
  status: string; verification_status: string; final_response: string; model_id: string;
  graph_version: string; prompt_version: string; artifact_lineage: Record<string, string>;
  revision_attempts: number; total_latency_ms: number; total_input_tokens: number;
  total_output_tokens: number; events: AgentEvent[]; recommendations: Recommendation[];
};
export type GovernanceSummary = {
  artifacts: number; risks: number; pending_reviews: number; evaluation_failures: number;
  rejected_recommendations: number; release_ready: boolean; release_blockers: string[];
  drift_alerts: string[]; baseline_version: string;
};
export type GovernanceArtifact = {
  id: string; artifact_type: string; name: string; version: string; content_sha256: string;
  configuration: Record<string, string | number | boolean | string[]>;
  status: string; approval_source: string; approval_reason: string | null; created_at: string;
};
export type GovernanceRisk = {
  id: string; risk_id: string; category: string; likelihood: string; impact: string;
  residual_risk: string; mitigation: string; owner_role: string; review_on: string;
  acceptance_status: string;
};
export type EvaluationRun = {
  id: string; dataset_id: string; dataset_version: string; status: string;
  metrics: Record<string, number | string>; thresholds: Record<string, number | string>;
  model_id: string | null; failures: string[]; duration_ms: number; code_version: string;
};
export type HumanReview = {
  id: string; source: string; reason: string; risk_level: string; status: string;
  evidence_ids: string[]; artifact_lineage: Record<string, string>;
  requested_by_user_id: string | null; created_at: string;
};
export type GovernanceData = {
  summary: GovernanceSummary; artifacts: GovernanceArtifact[]; risks: GovernanceRisk[];
  evaluations: EvaluationRun[]; reviews: HumanReview[];
};
export type DigestPreference = {
  id: string; enabled: boolean; weekday: number; local_time: string; timezone: string;
  next_due_at: string; last_dispatched_at: string | null;
};
export type Notification = {
  id: string; digest_job_id: string; status: string; subject: string; body: string;
  delivered_at: string | null; created_at: string;
};
export type ArchitectureNode = {
  id: string; label: string; detail: string; runtime: string;
  kind: "input" | "guardrail" | "deterministic" | "store" | "mesh" | "verifier" | "output";
  x: number; y: number;
};
export type ArchitectureEdge = {
  source: string; target: string; label: string;
  branch: "normal" | "revise" | "reject" | "audit" | "mesh";
};
export type ArchitectureManifest = {
  graph_version: string; prompt_version: string; verifier_version: string; mesh_model: string | null;
  nodes: ArchitectureNode[]; edges: ArchitectureEdge[];
};
