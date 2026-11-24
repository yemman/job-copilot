import { useEffect, useState } from 'react';
import { ExternalLink, Plus, RefreshCw, Search, Trash2 } from 'lucide-react';
import { api } from '../api';
import type { Job, JobSource } from '../types';

export function JobsExplorer() {
  const [tab, setTab] = useState<'jobs' | 'sources'>('jobs');
  const [jobs, setJobs] = useState<Job[]>([]);
  const [sources, setSources] = useState<JobSource[]>([]);
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [notice, setNotice] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  // Import Job form
  const [showImport, setShowImport] = useState(false);
  const [impUrl, setImpUrl] = useState('');
  const [impTitle, setImpTitle] = useState('');
  const [impCompany, setImpCompany] = useState('');
  const [impLocation, setImpLocation] = useState('');
  const [impWorkMode, setImpWorkMode] = useState('unknown');
  const [impDesc, setImpDesc] = useState('');

  // Add Source form
  const [srcName, setSrcName] = useState('');
  const [srcType, setSrcType] = useState<'greenhouse' | 'lever' | 'ashby' | 'remotive' | 'arbeitnow'>('greenhouse');
  const [srcToken, setSrcToken] = useState('');

  async function loadAll() {
    setError('');
    try {
      const [j, s] = await Promise.all([
        api.listJobs({ status: statusFilter || undefined, search: search || undefined }),
        api.listSources(),
      ]);
      setJobs(j);
      setSources(s);
    } catch (e) {
      setError((e as Error).message);
    }
  }

  useEffect(() => {
    void loadAll();
  }, [statusFilter]);

  async function handleImportJob(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError('');
    setNotice('');
    try {
      const created = await api.importJob({
        url: impUrl,
        title: impTitle,
        company: impCompany,
        location: impLocation,
        work_mode: impWorkMode,
        description: impDesc,
      });
      setNotice(`Imported "${created.title}" (score: ${created.score ?? '—'}).`);
      setImpUrl('');
      setImpTitle('');
      setImpCompany('');
      setImpLocation('');
      setImpDesc('');
      setShowImport(false);
      await loadAll();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function handleRescore() {
    setBusy(true);
    setError('');
    try {
      const res = await api.rescoreJobs();
      setNotice(`Re-scored ${res.rescored} job(s) using your latest profile and learned rules.`);
      await loadAll();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function handleAddSource(e: React.FormEvent) {
    e.preventDefault();
    if (!srcName.trim()) return;
    setError('');
    const config: Record<string, unknown> = {};
    if (srcType === 'greenhouse') {
      config.board_token = srcToken.trim();
      config.company_name = srcName.trim();
    } else if (srcType === 'lever' || srcType === 'ashby') {
      config.company_slug = srcToken.trim();
      config.company_name = srcName.trim();
    } else if (srcToken.trim()) {
      config.search = srcToken.trim();
    }
    try {
      await api.createSource({
        name: srcName.trim(),
        source_type: srcType,
        config,
        enabled: true,
      });
      setSrcName('');
      setSrcToken('');
      setNotice('Job source added.');
      await loadAll();
    } catch (e) {
      setError((e as Error).message);
    }
  }

  async function handleSyncSource(id: number) {
    setBusy(true);
    setError('');
    try {
      const res = await api.syncSource(id);
      if (res.status === 'ok') {
        setNotice(`${res.source_name}: fetched ${res.fetched_count}, added ${res.inserted_count} new jobs.`);
      } else {
        setError(`${res.source_name} sync failed: ${res.error}`);
      }
      await loadAll();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function handleSyncAll() {
    setBusy(true);
    setError('');
    try {
      const results = await api.syncAllSources();
      const totalNew = results.reduce((acc, r) => acc + r.inserted_count, 0);
      setNotice(`Synced ${results.length} enabled source(s), added ${totalNew} new jobs.`);
      await loadAll();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">Jobs & ATS Sources</h1>
          <p className="page-subtitle">
            Manage Greenhouse, Lever, Ashby, Remotive, and Arbeitnow feeds or paste a job URL/description manually.
          </p>
        </div>
        <div className="row">
          <button className="btn" onClick={() => setShowImport(!showImport)}>
            <Plus size={14} /> Paste Job URL / Text
          </button>
          <button className="btn" onClick={() => void handleRescore()} disabled={busy}>
            <RefreshCw size={14} /> Re-score Jobs
          </button>
          <button className="btn btn-primary" onClick={() => void handleSyncAll()} disabled={busy}>
            <RefreshCw size={14} /> Sync Enabled Sources
          </button>
        </div>
      </div>

      {error && <div className="banner banner-red">{error}</div>}
      {notice && <div className="banner banner-blue">{notice}</div>}

      {showImport && (
        <form className="card" onSubmit={(e) => void handleImportJob(e)} style={{ marginBottom: 16 }}>
          <h3 style={{ marginTop: 0 }}>Import a Specific Job</h3>
          <div className="grid-2">
            <div className="field">
              <label className="label">Job URL (optional — auto-parses public pages)</label>
              <input
                className="input"
                value={impUrl}
                onChange={(e) => setImpUrl(e.target.value)}
                placeholder="https://boards.greenhouse.io/..."
              />
            </div>
            <div className="field">
              <label className="label">Job Title (required if URL blocks auto-fetch)</label>
              <input
                className="input"
                value={impTitle}
                onChange={(e) => setImpTitle(e.target.value)}
                placeholder="Senior Backend Engineer"
              />
            </div>
          </div>
          <div className="grid-3">
            <div className="field">
              <label className="label">Company</label>
              <input
                className="input"
                value={impCompany}
                onChange={(e) => setImpCompany(e.target.value)}
                placeholder="Stripe"
              />
            </div>
            <div className="field">
              <label className="label">Location</label>
              <input
                className="input"
                value={impLocation}
                onChange={(e) => setImpLocation(e.target.value)}
                placeholder="Remote / Tel Aviv"
              />
            </div>
            <div className="field">
              <label className="label">Work Mode</label>
              <select
                className="select"
                value={impWorkMode}
                onChange={(e) => setImpWorkMode(e.target.value)}
              >
                <option value="unknown">Auto-detect</option>
                <option value="remote">Remote</option>
                <option value="hybrid">Hybrid</option>
                <option value="onsite">Onsite</option>
              </select>
            </div>
          </div>
          <div className="field">
            <label className="label">Job Description</label>
            <textarea
              className="textarea"
              value={impDesc}
              onChange={(e) => setImpDesc(e.target.value)}
              placeholder="Paste description if URL is private or JS-rendered..."
            />
          </div>
          <div className="row">
            <button className="btn btn-primary" type="submit" disabled={busy}>
              Save & Score Job
            </button>
            <button className="btn" type="button" onClick={() => setShowImport(false)}>
              Cancel
            </button>
          </div>
        </form>
      )}

      <div className="tabs">
        <button
          className={`tab-btn ${tab === 'jobs' ? 'active' : ''}`}
          onClick={() => setTab('jobs')}
        >
          Jobs Pool ({jobs.length})
        </button>
        <button
          className={`tab-btn ${tab === 'sources' ? 'active' : ''}`}
          onClick={() => setTab('sources')}
        >
          ATS & API Sources ({sources.length})
        </button>
      </div>

      {tab === 'jobs' ? (
        <div className="card">
          <div className="row" style={{ marginBottom: 14 }}>
            <input
              className="input"
              style={{ maxWidth: 320 }}
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search title, company, description..."
            />
            <button className="btn btn-sm" onClick={() => void loadAll()}>
              <Search size={13} /> Search
            </button>
            <select
              className="select"
              style={{ width: 'auto' }}
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
            >
              <option value="">All statuses</option>
              <option value="new">New (Eligible for Digest)</option>
              <option value="suggested">Suggested</option>
              <option value="approved">Approved</option>
              <option value="skipped">Skipped</option>
            </select>
          </div>
          <table className="table">
            <thead>
              <tr>
                <th>Score</th>
                <th>Role & Company</th>
                <th>Mode / Location</th>
                <th>Source</th>
                <th>Status</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {jobs.map((j) => (
                <tr key={j.id}>
                  <td>
                    <span className="badge badge-blue">
                      {j.score !== null && j.score !== undefined ? Math.round(j.score) : '—'}
                    </span>
                  </td>
                  <td>
                    <strong>{j.title}</strong>
                    <div className="muted">{j.company}</div>
                  </td>
                  <td>
                    <span style={{ textTransform: 'capitalize' }}>{j.work_mode}</span>
                    <div className="muted">{j.location || '—'}</div>
                  </td>
                  <td>{j.source_type}</td>
                  <td>
                    <span className="badge">{j.status}</span>
                  </td>
                  <td>
                    {j.url && (
                      <a href={j.url} target="_blank" rel="noreferrer">
                        <ExternalLink size={14} />
                      </a>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div>
          <form className="card" onSubmit={(e) => void handleAddSource(e)} style={{ marginBottom: 16 }}>
            <h3 style={{ marginTop: 0 }}>Add Public ATS / Job API Source</h3>
            <div className="grid-3">
              <div className="field">
                <label className="label">Source Type</label>
                <select
                  className="select"
                  value={srcType}
                  onChange={(e) =>
                    setSrcType(
                      e.target.value as 'greenhouse' | 'lever' | 'ashby' | 'remotive' | 'arbeitnow'
                    )
                  }
                >
                  <option value="greenhouse">Greenhouse (company board token)</option>
                  <option value="lever">Lever (company slug)</option>
                  <option value="ashby">Ashby (company slug)</option>
                  <option value="remotive">Remotive (remote search)</option>
                  <option value="arbeitnow">Arbeitnow (tech board)</option>
                </select>
              </div>
              <div className="field">
                <label className="label">Display / Company Name</label>
                <input
                  className="input"
                  required
                  value={srcName}
                  onChange={(e) => setSrcName(e.target.value)}
                  placeholder="e.g., Anthropic"
                />
              </div>
              <div className="field">
                <label className="label">
                  {srcType === 'remotive' || srcType === 'arbeitnow'
                    ? 'Optional Search Keyword'
                    : 'Board Token / Slug'}
                </label>
                <input
                  className="input"
                  required={srcType === 'greenhouse' || srcType === 'lever' || srcType === 'ashby'}
                  value={srcToken}
                  onChange={(e) => setSrcToken(e.target.value)}
                  placeholder={srcType === 'greenhouse' ? 'e.g., stripe' : 'e.g., notion'}
                />
              </div>
            </div>
            <button className="btn btn-primary" type="submit">
              <Plus size={14} /> Add Source
            </button>
          </form>

          <div className="card">
            <table className="table">
              <thead>
                <tr>
                  <th>Enabled</th>
                  <th>Source</th>
                  <th>Type & Config</th>
                  <th>Last Sync</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {sources.map((s) => (
                  <tr key={s.id}>
                    <td>
                      <input
                        type="checkbox"
                        checked={s.enabled}
                        onChange={(e) =>
                          void api.updateSource(s.id, { enabled: e.target.checked }).then(loadAll)
                        }
                      />
                    </td>
                    <td>
                      <strong>{s.name}</strong>
                    </td>
                    <td>
                      <span className="badge">{s.source_type}</span>{' '}
                      <span className="muted">{JSON.stringify(s.config)}</span>
                    </td>
                    <td className="muted">
                      {s.last_sync_status || 'Never synced'}
                      {s.last_sync_status === 'ok' ? ` (+${s.last_sync_count})` : ''}
                    </td>
                    <td className="row">
                      <button
                        className="btn btn-sm"
                        disabled={busy}
                        onClick={() => void handleSyncSource(s.id)}
                      >
                        <RefreshCw size={12} /> Sync
                      </button>
                      <button
                        className="btn btn-danger btn-sm"
                        onClick={() => void api.deleteSource(s.id).then(loadAll)}
                      >
                        <Trash2 size={12} />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
