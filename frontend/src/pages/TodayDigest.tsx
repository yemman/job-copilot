import { useEffect, useState } from 'react';
import {
  AlertCircle,
  Calendar,
  CheckCircle2,
  ExternalLink,
  RefreshCw,
  Sparkles,
  ThumbsDown,
  ThumbsUp,
} from 'lucide-react';
import { api } from '../api';
import type { DailyDigest, DailyDigestItem, DigestTodayResponse } from '../types';

const SKIP_REASONS = [
  { value: 'wrong_stack', label: 'Wrong tech stack' },
  { value: 'too_senior', label: 'Too senior' },
  { value: 'too_junior', label: 'Too junior' },
  { value: 'location_mismatch', label: 'Location / work mode mismatch' },
  { value: 'company_not_interesting', label: 'Company not interesting' },
  { value: 'compensation_dealbreaker', label: 'Dealbreaker / compensation' },
  { value: 'other', label: 'Other' },
];

interface Props {
  onOpenApplication: (appId: number) => void;
  onRefreshHealth?: () => void;
}

export function TodayDigest({ onOpenApplication }: Props) {
  const [todayInfo, setTodayInfo] = useState<DigestTodayResponse | null>(null);
  const [pastDigests, setPastDigests] = useState<DailyDigest[]>([]);
  const [selectedDate, setSelectedDate] = useState<string>('');
  const [syncBeforeGen, setSyncBeforeGen] = useState(false);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [skippingItemId, setSkippingItemId] = useState<number | null>(null);
  const [skipReason, setSkipReason] = useState('wrong_stack');
  const [skipNote, setSkipNote] = useState('');

  async function loadData() {
    setLoading(true);
    setError('');
    try {
      const [todayRes, history] = await Promise.all([api.getTodayDigest(), api.listDigests()]);
      setTodayInfo(todayRes);
      setPastDigests(history);
      if (!selectedDate) {
        setSelectedDate(todayRes.digest?.digest_date || todayRes.today_date);
      }
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void loadData();
  }, []);

  async function handleGenerate() {
    setGenerating(true);
    setError('');
    setNotice('');
    try {
      const res = await api.generateDigest(true, syncBeforeGen);
      setNotice(res.reason);
      await loadData();
      if (res.digest) {
        setSelectedDate(res.digest.digest_date);
      }
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setGenerating(false);
    }
  }

  async function handleApprove(item: DailyDigestItem) {
    setError('');
    try {
      const res = await api.decideDigestItem(item.id, 'approved');
      setNotice(`Approved "${item.job.title}" — moved to Connection Search first.`);
      await loadData();
      if (res.application_id) {
        onOpenApplication(res.application_id);
      }
    } catch (e) {
      setError((e as Error).message);
    }
  }

  async function handleConfirmSkip(item: DailyDigestItem) {
    setError('');
    try {
      const res = await api.decideDigestItem(item.id, 'skipped', skipReason, skipNote);
      setSkippingItemId(null);
      setSkipNote('');
      setNotice(
        `Skipped "${item.job.title}". Updated ${res.learned_rules_updated} learned preference rule(s).`
      );
      await loadData();
    } catch (e) {
      setError((e as Error).message);
    }
  }

  const activeDigest: DailyDigest | null =
    pastDigests.find((d) => d.digest_date === selectedDate) || todayInfo?.digest || null;

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">Today's Job Picks (3–5 / Day)</h1>
          <p className="page-subtitle">
            Scheduled Sunday–Wednesday. Approve a role to start connection-first outreach, or skip to teach the scorer.
          </p>
        </div>
        <div className="row">
          <label className="row muted" style={{ cursor: 'pointer' }}>
            <input
              type="checkbox"
              checked={syncBeforeGen}
              onChange={(e) => setSyncBeforeGen(e.target.checked)}
            />
            Sync enabled ATS sources first
          </label>
          <button className="btn btn-primary" onClick={handleGenerate} disabled={generating}>
            <Sparkles size={15} />
            {generating ? 'Generating Picks...' : "Generate Today's Picks"}
          </button>
        </div>
      </div>

      {todayInfo && (
        <div className={`banner ${todayInfo.is_scheduled_day ? 'banner-green' : 'banner-amber'}`}>
          <div className="between">
            <div className="row">
              <Calendar size={16} />
              <span>
                <strong>{todayInfo.today_date}</strong> ({todayInfo.day_of_week.toUpperCase()}) —{' '}
                {todayInfo.is_scheduled_day
                  ? 'Active digest day (Sun–Wed schedule).'
                  : `Off-schedule day (Sun–Wed active; next scheduled day: ${todayInfo.next_digest_day}). You can still generate picks manually anytime.`}
              </span>
            </div>
            {pastDigests.length > 0 && (
              <select
                className="select"
                style={{ width: 'auto', padding: '4px 10px' }}
                value={selectedDate}
                onChange={(e) => setSelectedDate(e.target.value)}
              >
                {pastDigests.map((d) => (
                  <option key={d.id} value={d.digest_date}>
                    {d.digest_date} ({d.day_of_week.toUpperCase()}) — {d.items.length} picks
                  </option>
                ))}
              </select>
            )}
          </div>
        </div>
      )}

      {error && (
        <div className="banner banner-red row">
          <AlertCircle size={16} />
          <span>{error}</span>
        </div>
      )}
      {notice && (
        <div className="banner banner-blue row">
          <CheckCircle2 size={16} />
          <span>{notice}</span>
        </div>
      )}

      {loading ? (
        <div className="card muted">Loading today's picks...</div>
      ) : !activeDigest || activeDigest.items.length === 0 ? (
        <div className="card">
          <h3 style={{ marginTop: 0 }}>No picks generated yet for {selectedDate || 'today'}</h3>
          <p className="muted">
            Click <strong>Generate Today's Picks</strong> above, or use <strong>Load Demo Data</strong> in the top bar
            if you haven't synced job boards yet.
          </p>
          <button className="btn" onClick={() => void loadData()}>
            <RefreshCw size={14} /> Refresh
          </button>
        </div>
      ) : (
        activeDigest.items.map((item) => {
          const job = item.job;
          const bd = job.score_breakdown || {};
          const scoreVal = Math.round(item.score_snapshot);
          const scoreCls = scoreVal >= 70 ? 'score-high' : scoreVal >= 45 ? 'score-mid' : 'score-low';

          return (
            <div key={item.id} className="card">
              <div className="between" style={{ alignItems: 'flex-start' }}>
                <div className="row" style={{ alignItems: 'flex-start', flex: 1 }}>
                  <div className={`score-pill ${scoreCls}`}>
                    <span style={{ fontSize: 19 }}>{scoreVal}</span>
                    <span style={{ fontSize: 10, opacity: 0.8 }}>FIT</span>
                  </div>
                  <div style={{ flex: 1, minWidth: 240 }}>
                    <div className="row">
                      <span className="badge">#{item.rank}</span>
                      <h3 style={{ margin: 0, fontSize: 17 }}>{job.title}</h3>
                      {item.decision === 'approved' && <span className="badge badge-green">Approved</span>}
                      {item.decision === 'skipped' && <span className="badge badge-red">Skipped</span>}
                      <span className="badge badge-blue">
                        {bd.scorer_mode === 'gemini' ? 'Gemini AI' : 'Heuristic'}
                      </span>
                    </div>
                    <div className="muted" style={{ marginTop: 4 }}>
                      <strong>{job.company}</strong> · {job.location || 'Unspecified location'} ·{' '}
                      <span style={{ textTransform: 'capitalize' }}>{job.work_mode}</span>
                      {job.salary_text ? ` · ${job.salary_text}` : ''}
                      {' · '}
                      <span>via {job.source_type}</span>
                    </div>
                  </div>
                </div>
                {job.url && (
                  <a className="btn btn-sm" href={job.url} target="_blank" rel="noreferrer">
                    View Posting <ExternalLink size={13} />
                  </a>
                )}
              </div>

              <p style={{ marginTop: 12, marginBottom: 10, fontSize: 14 }}>{item.rationale_snapshot}</p>

              <div className="chips" style={{ marginBottom: 12 }}>
                {(bd.matched_skills || []).map((s) => (
                  <span key={`m-${s}`} className="badge badge-green">
                    ✓ {s}
                  </span>
                ))}
                {(bd.missing_skills || []).slice(0, 4).map((s) => (
                  <span key={`g-${s}`} className="badge">
                    Gap: {s}
                  </span>
                ))}
                {(bd.applied_rules || []).map((r) => (
                  <span key={`r-${r.id}`} className="badge badge-purple">
                    Rule: {r.term} ({r.weight > 0 ? `+${r.weight}` : r.weight})
                  </span>
                ))}
              </div>

              {job.description && (
                <details style={{ marginBottom: 12 }}>
                  <summary className="muted" style={{ cursor: 'pointer' }}>
                    Read job description excerpt
                  </summary>
                  <p className="muted" style={{ whiteSpace: 'pre-wrap', marginTop: 8 }}>
                    {job.description.slice(0, 1200)}
                    {job.description.length > 1200 ? '...' : ''}
                  </p>
                </details>
              )}

              {item.decision === 'pending' && (
                <div>
                  <div className="row">
                    <button className="btn btn-success" onClick={() => void handleApprove(item)}>
                      <ThumbsUp size={14} /> Approve & Find Connection First
                    </button>
                    <button
                      className="btn btn-danger"
                      onClick={() => {
                        setSkippingItemId(skippingItemId === item.id ? null : item.id);
                        setSkipReason('wrong_stack');
                      }}
                    >
                      <ThumbsDown size={14} /> Skip (Teach App)
                    </button>
                  </div>

                  {skippingItemId === item.id && (
                    <div
                      style={{
                        marginTop: 12,
                        padding: 12,
                        borderRadius: 8,
                        background: 'var(--bg-elevated)',
                        border: '1px solid var(--border)',
                      }}
                    >
                      <div className="grid-2">
                        <div className="field">
                          <label className="label">Why skip this job?</label>
                          <select
                            className="select"
                            value={skipReason}
                            onChange={(e) => setSkipReason(e.target.value)}
                          >
                            {SKIP_REASONS.map((r) => (
                              <option key={r.value} value={r.value}>
                                {r.label}
                              </option>
                            ))}
                          </select>
                        </div>
                        <div className="field">
                          <label className="label">Optional note (e.g., "avoid crypto")</label>
                          <input
                            className="input"
                            value={skipNote}
                            onChange={(e) => setSkipNote(e.target.value)}
                            placeholder="Helps refine learned rules..."
                          />
                        </div>
                      </div>
                      <div className="row">
                        <button className="btn btn-danger btn-sm" onClick={() => void handleConfirmSkip(item)}>
                          Confirm Skip & Update Weights
                        </button>
                        <button className="btn btn-sm" onClick={() => setSkippingItemId(null)}>
                          Cancel
                        </button>
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>
          );
        })
      )}
    </div>
  );
}
