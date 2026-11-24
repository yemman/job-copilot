export interface HealthStatus {
  status: string;
  ai_mode: 'gemini' | 'heuristic';
  gemini_model: string;
  scheduler_running: boolean;
}

export interface Profile {
  id: number;
  full_name: string;
  headline: string;
  resume_text: string;
  resume_filename: string;
  skills: string[];
  target_roles: string[];
  preferred_locations: string[];
  work_mode: 'remote' | 'hybrid' | 'onsite' | 'any';
  experience_years: number;
  dealbreakers: string[];
  notes_for_ai: string;
  daily_pick_count: number;
  digest_days: string[];
  digest_hour: number;
  timezone: string;
  updated_at?: string;
}

export interface JobSource {
  id: number;
  name: string;
  source_type: 'greenhouse' | 'lever' | 'ashby' | 'remotive' | 'arbeitnow';
  config: Record<string, unknown>;
  enabled: boolean;
  last_synced_at?: string | null;
  last_sync_status: string;
  last_sync_count: number;
  created_at: string;
}

export interface ScoreBreakdown {
  base_score?: number;
  learned_adjustment?: number;
  ai_adjustment?: number;
  matched_skills?: string[];
  missing_skills?: string[];
  dealbreakers_hit?: string[];
  applied_rules?: Array<{
    id: number;
    category: string;
    term: string;
    weight: number;
  }>;
  rationale?: string;
  scorer_mode?: 'gemini' | 'heuristic';
}

export interface Job {
  id: number;
  source_id?: number | null;
  source_type: string;
  external_id?: string | null;
  title: string;
  company: string;
  location: string;
  work_mode: string;
  url: string;
  description: string;
  tags: string[];
  salary_text: string;
  posted_at: string;
  ingested_at: string;
  score?: number | null;
  score_breakdown: ScoreBreakdown;
  status: string;
}

export interface DailyDigestItem {
  id: number;
  digest_id: number;
  job_id: number;
  rank: number;
  score_snapshot: number;
  rationale_snapshot: string;
  decision: 'pending' | 'approved' | 'skipped';
  decided_at?: string | null;
  job: Job;
}

export interface DailyDigest {
  id: number;
  digest_date: string;
  day_of_week: string;
  scheduled: boolean;
  created_at: string;
  notes: string;
  items: DailyDigestItem[];
}

export interface DigestTodayResponse {
  today_date: string;
  day_of_week: string;
  is_scheduled_day: boolean;
  digest_days: string[];
  next_digest_day: string;
  digest: DailyDigest | null;
}

export interface Contact {
  id: number;
  name: string;
  company: string;
  normalized_company: string;
  role: string;
  linkedin_url: string;
  email: string;
  relationship: string;
  notes: string;
  source: string;
  created_at: string;
}

export interface OutreachMessage {
  id: number;
  application_id: number;
  contact_id?: number | null;
  contact_name_snapshot: string;
  channel: 'linkedin_connect_note' | 'linkedin_dm' | 'email';
  subject: string;
  body: string;
  status: 'draft' | 'approved' | 'sent' | 'replied' | 'no_response';
  approved_at?: string | null;
  sent_at?: string | null;
  follow_up_at?: string | null;
  reply_notes: string;
  created_at: string;
  updated_at: string;
}

export interface ActivityLog {
  id: number;
  application_id?: number | null;
  action: string;
  details: string;
  created_at: string;
}

export type PipelineStage =
  | 'connection_search'
  | 'outreach_drafted'
  | 'outreach_sent'
  | 'ready_to_apply'
  | 'applied'
  | 'interviewing'
  | 'offer'
  | 'rejected'
  | 'withdrawn';

export interface Application {
  id: number;
  job_id: number;
  stage: PipelineStage;
  connection_override_reason?: string | null;
  applied_at?: string | null;
  next_step: string;
  next_step_at?: string | null;
  outcome_reason: string;
  notes: string;
  created_at: string;
  updated_at: string;
  job: Job;
  outreach_messages: OutreachMessage[];
  activity_logs: ActivityLog[];
  matched_contacts_count: number;
}

export interface ApplicationConnections {
  application_id: number;
  company: string;
  normalized_company: string;
  linkedin_search_url: string;
  matched_contacts: Contact[];
}

export interface LearnedRule {
  id: number;
  category: 'skill' | 'title_keyword' | 'company' | 'work_mode' | 'location' | 'red_flag';
  term: string;
  weight: number;
  evidence_count: number;
  source: string;
  locked: boolean;
  enabled: boolean;
  updated_at: string;
}

export interface FeedbackEvent {
  id: number;
  job_id?: number | null;
  application_id?: number | null;
  event_type: string;
  reason_code?: string | null;
  note?: string | null;
  job_snapshot: {
    title?: string;
    company?: string;
    work_mode?: string;
    location?: string;
    tags?: string[];
  };
  created_at: string;
}
