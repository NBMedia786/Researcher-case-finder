export type CaseStatus =
  | "new" | "reviewing" | "approved" | "rejected"
  | "foia_filed" | "records_received" | "archived";

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
  summary: string | null;
  created_at: string;
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
}
