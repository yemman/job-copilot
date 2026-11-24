import { useEffect, useState } from 'react';
import { Lock, Plus, Trash2, Unlock } from 'lucide-react';
import { api } from '../api';
import type { FeedbackEvent, LearnedRule } from '../types';

const CATEGORIES: Array<LearnedRule['category']> = [
  'skill',
  'title_keyword',
  'company',
  'work_mode',
  'location',
  'red_flag',
];

export function Learning() {
  const [rules, setRules] = useState<LearnedRule[]>([]);
  const [feedback, setFeedback] = useState<FeedbackEvent[]>([]);
  const [catFilter, setCatFilter] = useState<string>('all');
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');

  // Manual rule form
  const [newCat, setNewCat] = useState<LearnedRule['category']>('skill');
  const [newTerm, setNewTerm] = useState('');
  const [newWeight, setNewWeight] = useState(5);

  async function loadAll() {
    setError('');
    try {
      const [r, fb] = await Promise.all([api.listRules(), api.listFeedback()]);
      setRules(r);
      setFeedback(fb);
    } catch (e) {
      setError((e as Error).message);
    }
  }

  useEffect(() => {
    void loadAll();
  }, []);

  async function handleAddRule(e: React.FormEvent) {
    e.preventDefault();
    if (!newTerm.trim()) return;
    setError('');
    try {
      await api.createRule({
        category: newCat,
        term: newTerm.trim(),
        weight: newWeight,
        locked: true,
        enabled: true,
      });
      setNewTerm('');
      setNotice('Manual rule saved and locked.');
      await loadAll();
    } catch (e) {
      setError((e as Error).message);
    }
  }

  async function handleUpdateRule(rule: LearnedRule, patch: Partial<LearnedRule>) {
    setError('');
    try {
      await api.updateRule(rule.id, patch);
      await loadAll();
    } catch (e) {
      setError((e as Error).message);
    }
  }

  const visibleRules =
    catFilter === 'all' ? rules : rules.filter((r) => r.category === catFilter);

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">What the App Learned (HITL Memory)</h1>
          <p className="page-subtitle">
            Every approve, skip, reply, interview, or rejection updates these transparent weights. Lock any rule to
            prevent automatic drift.
          </p>
        </div>
      </div>

      {error && <div className="banner banner-red">{error}</div>}
      {notice && <div className="banner banner-green">{notice}</div>}

      <form className="card" onSubmit={(e) => void handleAddRule(e)} style={{ marginBottom: 16 }}>
        <h3 style={{ marginTop: 0 }}>Add Explicit Preference Rule</h3>
        <div className="grid-3">
          <div className="field">
            <label className="label">Category</label>
            <select
              className="select"
              value={newCat}
              onChange={(e) => setNewCat(e.target.value as LearnedRule['category'])}
            >
              {CATEGORIES.map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
            </select>
          </div>
          <div className="field">
            <label className="label">Term (e.g. FastAPI, Staff, remote, Crypto)</label>
            <input
              className="input"
              required
              value={newTerm}
              onChange={(e) => setNewTerm(e.target.value)}
            />
          </div>
          <div className="field">
            <label className="label">Weight (-20 to +20): {newWeight > 0 ? `+${newWeight}` : newWeight}</label>
            <input
              type="range"
              min={-20}
              max={20}
              step={1}
              value={newWeight}
              onChange={(e) => setNewWeight(Number(e.target.value))}
              style={{ width: '100%' }}
            />
          </div>
        </div>
        <button className="btn btn-primary" type="submit">
          <Plus size={14} /> Save & Lock Rule
        </button>
      </form>

      <div className="tabs">
        <button
          className={`tab-btn ${catFilter === 'all' ? 'active' : ''}`}
          onClick={() => setCatFilter('all')}
        >
          All ({rules.length})
        </button>
        {CATEGORIES.map((c) => (
          <button
            key={c}
            className={`tab-btn ${catFilter === c ? 'active' : ''}`}
            onClick={() => setCatFilter(c)}
          >
            {c} ({rules.filter((r) => r.category === c).length})
          </button>
        ))}
      </div>

      <div className="card" style={{ marginBottom: 16 }}>
        <h3 style={{ marginTop: 0 }}>Learned & Manual Scoring Rules</h3>
        {visibleRules.length === 0 ? (
          <p className="muted">No rules yet. Approve or skip daily picks to start teaching the app.</p>
        ) : (
          <table className="table">
            <thead>
              <tr>
                <th>Enabled</th>
                <th>Category & Term</th>
                <th>Weight (-20..+20)</th>
                <th>Evidence</th>
                <th>Lock</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {visibleRules.map((r) => (
                <tr key={r.id}>
                  <td>
                    <input
                      type="checkbox"
                      checked={r.enabled}
                      onChange={(e) => void handleUpdateRule(r, { enabled: e.target.checked })}
                    />
                  </td>
                  <td>
                    <span className="badge">{r.category}</span> <strong>{r.term}</strong>
                    <div className="muted">source: {r.source}</div>
                  </td>
                  <td style={{ minWidth: 180 }}>
                    <div className="row">
                      <input
                        type="range"
                        min={-20}
                        max={20}
                        step={0.5}
                        value={r.weight}
                        onChange={(e) =>
                          void handleUpdateRule(r, { weight: Number(e.target.value) })
                        }
                      />
                      <span
                        className={`badge ${
                          r.weight > 0 ? 'badge-green' : r.weight < 0 ? 'badge-red' : ''
                        }`}
                      >
                        {r.weight > 0 ? `+${r.weight}` : r.weight}
                      </span>
                    </div>
                  </td>
                  <td>{r.evidence_count}x</td>
                  <td>
                    <button
                      className={`btn btn-sm ${r.locked ? 'btn-primary' : ''}`}
                      onClick={() => void handleUpdateRule(r, { locked: !r.locked })}
                      title="Locked rules won't be modified automatically by feedback"
                    >
                      {r.locked ? <Lock size={12} /> : <Unlock size={12} />}
                      {r.locked ? 'Locked' : 'Unlocked'}
                    </button>
                  </td>
                  <td>
                    <button
                      className="btn btn-danger btn-sm"
                      onClick={() => void api.deleteRule(r.id).then(loadAll)}
                    >
                      <Trash2 size={12} />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <div className="card">
        <h3 style={{ marginTop: 0 }}>Recent Feedback Signals</h3>
        {feedback.length === 0 ? (
          <p className="muted">No feedback events logged yet.</p>
        ) : (
          <table className="table">
            <thead>
              <tr>
                <th>Event</th>
                <th>Job Snapshot</th>
                <th>Reason / Note</th>
              </tr>
            </thead>
            <tbody>
              {feedback.map((fb) => (
                <tr key={fb.id}>
                  <td>
                    <span
                      className={`badge ${
                        fb.event_type.includes('skip') || fb.event_type.includes('reject')
                          ? 'badge-red'
                          : 'badge-green'
                      }`}
                    >
                      {fb.event_type}
                    </span>
                  </td>
                  <td>
                    <strong>{fb.job_snapshot.title || '—'}</strong>
                    <div className="muted">{fb.job_snapshot.company || ''}</div>
                  </td>
                  <td className="muted">
                    {fb.reason_code || '—'} {fb.note ? `· ${fb.note}` : ''}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
