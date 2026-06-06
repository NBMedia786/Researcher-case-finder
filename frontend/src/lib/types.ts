export type CaseStatus =
  | "new" | "reviewing" | "approved" | "rejected"
  | "foia_filed" | "records_received" | "archived";

export const TEAM_MEMBERS = [
  "Gagandeep",
  "Rudransh",
  "Piyush",
  "Cyrus",
  "Shivanshi",
  "Vandana",
] as const;
export type TeamMember = (typeof TEAM_MEMBERS)[number];

export interface CaseListItem {
  id: string;
  defendant_name: string;
  defendant_age: number | null;
  defendant_hometown: string | null;
  sentencing_date: string;
  state: string;
  county: string | null;
  sentence_text: string | null;
  sentence_type: string | null;
  content_score: number;
  status: CaseStatus;
  assigned_to: string | null;
  summary: string | null;
  created_at: string;
  topic_id: string | null;
  topic_name: string | null;
}

export interface CaseArticle {
  id: string;
  url: string;
  title: string | null;
  source_name: string;
  source_type: string;
  published_at: string | null;
}

export interface CaseDetail extends CaseListItem {
  victims: { name: string | null; age: number | null }[];
  charges: { statute: string | null; degree: string | null; description: string }[];
  docket_number: string | null;
  judge_name: string | null;
  court_name: string | null;
  prosecuting_office: string | null;
  investigating_agency: string | null;
  sentence_years: number | null;
  assigned_to: string | null;
  notes: string | null;
  articles: CaseArticle[];
}

export interface User {
  id: string;
  email: string;
  full_name: string | null;
  role: "admin" | "researcher";
  is_active: boolean;
  last_login_at: string | null;
}

export interface SourceItem {
  id: string;
  name: string;
  type: string;
  is_active: boolean;
  last_run_at: string | null;
  last_success_at: string | null;
  items_fetched_24h: number;
  items_extracted_24h: number;
  consecutive_failures: number;
  // Credential admin fields (null when source doesn't need a key).
  key_field: string | null;          // "api_key" | "api_token"
  key_preview: string | null;        // e.g. "••••abcd", null if not set
  key_source: "config" | "env" | null;
  // Vendor dashboard URL — shown as an external link next to the source
  // name so admins can jump out to manage keys / check quotas.
  homepage_url: string | null;
}

export interface Topic {
  id: string;
  name: string;
  queries: string[];
  extraction_criteria: string;
  recency_days: number;
  is_active: boolean;
  is_default: boolean;
  case_count: number;
  created_at: string;
  updated_at: string;
}

export type ExtractionStatus = "pending" | "extracted" | "no_match" | "failed";

export interface ArticleListItem {
  id: string;
  url: string;
  title: string | null;
  source_name: string;
  source_type: string;
  published_at: string | null;
  created_at: string;
  extraction_status: ExtractionStatus;
  extraction_error: string | null;
  case_id: string | null;
  topic_id: string | null;
  topic_name: string | null;
  rejection_reason: string | null;
  extracted_defendant_name: string | null;
  extracted_state: string | null;
  extracted_sentencing_date: string | null;
}
