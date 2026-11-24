import type {
  Application,
  ApplicationConnections,
  Contact,
  DailyDigest,
  DigestTodayResponse,
  FeedbackEvent,
  HealthStatus,
  Job,
  JobSource,
  LearnedRule,
  OutreachMessage,
  PipelineStage,
  Profile,
} from './types';

async function request<T>(url: string, options?: RequestInit): Promise<T> {
  const res = await fetch(url, {
    headers: options?.body instanceof FormData ? undefined : { 'Content-Type': 'application/json' },
    ...options,
  });
  if (!res.ok) {
    let msg = `Request failed (${res.status})`;
    try {
      const err = await res.json();
      if (err?.detail) msg = String(err.detail);
    } catch {
      // ignore json parse failure
    }
    throw new Error(msg);
  }
  return res.json() as Promise<T>;
}

export const api = {
  health: () => request<HealthStatus>('/api/health'),
  seedDemo: () => request<{ jobs_added: number; contacts_added: number; rules_added: number }>('/api/demo/seed', { method: 'POST' }),

  // Profile
  getProfile: () => request<Profile>('/api/profile'),
  updateProfile: (data: Partial<Profile>) =>
    request<Profile>('/api/profile', { method: 'PUT', body: JSON.stringify(data) }),
  uploadResume: (file: File) => {
    const fd = new FormData();
    fd.append('file', file);
    return request<{ filename: string; resume_text: string; extracted_skills: string[]; profile: Profile }>(
      '/api/profile/resume',
      { method: 'POST', body: fd }
    );
  },

  // Digest
  getTodayDigest: () => request<DigestTodayResponse>('/api/digests/today'),
  listDigests: () => request<DailyDigest[]>('/api/digests'),
  generateDigest: (force: boolean, sync_sources: boolean) =>
    request<{ skipped: boolean; already_existed: boolean; reason: string; digest: DailyDigest | null }>(
      '/api/digests/generate',
      { method: 'POST', body: JSON.stringify({ force, sync_sources }) }
    ),
  decideDigestItem: (
    itemId: number,
    decision: 'approved' | 'skipped',
    reason_code?: string,
    note?: string
  ) =>
    request<{ item_id: number; decision: string; application_id: number | null; learned_rules_updated: number }>(
      `/api/digests/items/${itemId}/decide`,
      { method: 'POST', body: JSON.stringify({ decision, reason_code, note }) }
    ),

  // Jobs & Sources
  listJobs: (params?: { status?: string; search?: string }) => {
    const qs = new URLSearchParams();
    if (params?.status) qs.set('status', params.status);
    if (params?.search) qs.set('search', params.search);
    const suffix = qs.toString() ? `?${qs.toString()}` : '';
    return request<Job[]>(`/api/jobs${suffix}`);
  },
  importJob: (data: {
    url?: string;
    title?: string;
    company?: string;
    location?: string;
    work_mode?: string;
    description?: string;
  }) => request<Job>('/api/jobs/import', { method: 'POST', body: JSON.stringify(data) }),
  rescoreJobs: () => request<{ rescored: number }>('/api/jobs/rescore', { method: 'POST' }),

  listSources: () => request<JobSource[]>('/api/sources'),
  createSource: (data: { name: string; source_type: string; config: Record<string, unknown>; enabled: boolean }) =>
    request<JobSource>('/api/sources', { method: 'POST', body: JSON.stringify(data) }),
  updateSource: (id: number, data: Partial<JobSource>) =>
    request<JobSource>(`/api/sources/${id}`, { method: 'PATCH', body: JSON.stringify(data) }),
  deleteSource: (id: number) => request<{ deleted: boolean }>(`/api/sources/${id}`, { method: 'DELETE' }),
  syncSource: (id: number) =>
    request<{ source_name: string; status: string; fetched_count: number; inserted_count: number; error: string | null }>(
      `/api/sources/${id}/sync`,
      { method: 'POST' }
    ),
  syncAllSources: () =>
    request<Array<{ source_name: string; status: string; fetched_count: number; inserted_count: number; error: string | null }>>(
      '/api/sources/sync-all',
      { method: 'POST' }
    ),

  // Pipeline & Outreach
  listApplications: (stage?: string) =>
    request<Application[]>(stage ? `/api/applications?stage=${encodeURIComponent(stage)}` : '/api/applications'),
  getApplication: (id: number) => request<Application>(`/api/applications/${id}`),
  updateApplication: (id: number, data: { notes?: string; next_step?: string }) =>
    request<Application>(`/api/applications/${id}`, { method: 'PATCH', body: JSON.stringify(data) }),
  transitionApplication: (
    id: number,
    data: { stage: PipelineStage; connection_override_reason?: string; outcome_reason?: string; note?: string }
  ) => request<Application>(`/api/applications/${id}/transition`, { method: 'POST', body: JSON.stringify(data) }),
  getApplicationConnections: (id: number) =>
    request<ApplicationConnections>(`/api/applications/${id}/connections`),

  draftOutreach: (
    appId: number,
    data: { contact_id?: number | null; contact_name?: string; channel: 'linkedin_connect_note' | 'linkedin_dm' | 'email' }
  ) => request<OutreachMessage>(`/api/applications/${appId}/outreach/draft`, { method: 'POST', body: JSON.stringify(data) }),
  updateOutreach: (id: number, data: { subject?: string; body?: string; channel?: string }) =>
    request<OutreachMessage>(`/api/outreach/${id}`, { method: 'PATCH', body: JSON.stringify(data) }),
  approveOutreach: (id: number) =>
    request<OutreachMessage>(`/api/outreach/${id}/approve`, { method: 'POST' }),
  markOutreachSent: (id: number) =>
    request<OutreachMessage>(`/api/outreach/${id}/mark-sent`, { method: 'POST' }),
  logOutreachReply: (id: number, data: { replied: boolean; reply_notes: string; advance_to_ready_to_apply: boolean }) =>
    request<OutreachMessage>(`/api/outreach/${id}/log-reply`, { method: 'POST', body: JSON.stringify(data) }),

  // Contacts
  listContacts: (search?: string) =>
    request<Contact[]>(search ? `/api/contacts?search=${encodeURIComponent(search)}` : '/api/contacts'),
  createContact: (data: Partial<Contact>) =>
    request<Contact>('/api/contacts', { method: 'POST', body: JSON.stringify(data) }),
  deleteContact: (id: number) => request<{ deleted: boolean }>(`/api/contacts/${id}`, { method: 'DELETE' }),
  importLinkedInCsv: (file: File) => {
    const fd = new FormData();
    fd.append('file', file);
    return request<{ parsed: number; inserted: number; skipped_duplicates: number }>(
      '/api/contacts/import-linkedin-csv',
      { method: 'POST', body: fd }
    );
  },

  // Learning
  listRules: () => request<LearnedRule[]>('/api/learning/rules'),
  createRule: (data: { category: string; term: string; weight: number; locked: boolean; enabled: boolean }) =>
    request<LearnedRule>('/api/learning/rules', { method: 'POST', body: JSON.stringify(data) }),
  updateRule: (id: number, data: Partial<LearnedRule>) =>
    request<LearnedRule>(`/api/learning/rules/${id}`, { method: 'PATCH', body: JSON.stringify(data) }),
  deleteRule: (id: number) => request<{ deleted: boolean }>(`/api/learning/rules/${id}`, { method: 'DELETE' }),
  listFeedback: () => request<FeedbackEvent[]>('/api/learning/feedback'),
};
