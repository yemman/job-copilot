import { useEffect, useState } from 'react';
import {
  AlertTriangle,
  Check,
  Copy,
  ExternalLink,
  MessageSquarePlus,
  Send,
  ShieldCheck,
  UserPlus,
  X,
} from 'lucide-react';
import { api } from '../api';
import type {
  Application,
  ApplicationConnections,
  OutreachMessage,
  PipelineStage,
} from '../types';

const STAGES: Array<{ key: PipelineStage; label: string }> = [
  { key: 'connection_search', label: '1. Connection Search' },
  { key: 'outreach_drafted', label: '2. Outreach Drafted' },
  { key: 'outreach_sent', label: '3. Outreach Sent' },
  { key: 'ready_to_apply', label: '4. Ready to Apply' },
  { key: 'applied', label: '5. Applied' },
  { key: 'interviewing', label: '6. Interviewing' },
  { key: 'offer', label: '7. Offer' },
  { key: 'rejected', label: 'Rejected' },
  { key: 'withdrawn', label: 'Withdrawn' },
];

interface Props {
  selectedAppId: number | null;
  onSelectAppId: (id: number | null) => void;
}

export function Pipeline({ selectedAppId, onSelectAppId }: Props) {
  const [apps, setApps] = useState<Application[]>([]);
  const [stageFilter, setStageFilter] = useState<string>('all');
  const [activeApp, setActiveApp] = useState<Application | null>(null);
  const [connections, setConnections] = useState<ApplicationConnections | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');

  // Quick add contact inside drawer
  const [showAddContact, setShowAddContact] = useState(false);
  const [newContactName, setNewContactName] = useState('');
  const [newContactRole, setNewContactRole] = useState('');
  const [newContactLinkedIn, setNewContactLinkedIn] = useState('');
  const [newContactRel, setNewContactRel] = useState('1st_degree');

  // Draft outreach controls
  const [draftChannel, setDraftChannel] = useState<'linkedin_connect_note' | 'linkedin_dm' | 'email'>(
    'linkedin_connect_note'
  );
  const [draftContactId, setDraftContactId] = useState<string>('');
  const [draftCustomName, setDraftCustomName] = useState('');
  const [editingBodies, setEditingBodies] = useState<Record<number, { subject: string; body: string }>>({});

  // Override / outcome modal inputs
  const [overrideReason, setOverrideReason] = useState('');
  const [showOverrideBox, setShowOverrideBox] = useState<PipelineStage | null>(null);
  const [notesDraft, setNotesDraft] = useState('');
  const [copiedId, setCopiedId] = useState<number | null>(null);

  async function loadApps() {
    setLoading(true);
    try {
      const list = await api.listApplications();
      setApps(list);
      if (selectedAppId) {
        await openDrawer(selectedAppId);
      }
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }

  async function openDrawer(appId: number) {
    setError('');
    try {
      const [appDetail, conn] = await Promise.all([
        api.getApplication(appId),
        api.getApplicationConnections(appId),
      ]);
      setActiveApp(appDetail);
      setConnections(conn);
      setNotesDraft(appDetail.notes || '');
      onSelectAppId(appId);
      const editMap: Record<number, { subject: string; body: string }> = {};
      for (const m of appDetail.outreach_messages) {
        editMap[m.id] = { subject: m.subject || '', body: m.body || '' };
      }
      setEditingBodies(editMap);
    } catch (e) {
      setError((e as Error).message);
    }
  }

  useEffect(() => {
    void loadApps();
  }, []);

  useEffect(() => {
    if (selectedAppId && (!activeApp || activeApp.id !== selectedAppId)) {
      void openDrawer(selectedAppId);
    }
  }, [selectedAppId]);

  async function refreshActive() {
    const list = await api.listApplications();
    setApps(list);
    if (activeApp) {
      await openDrawer(activeApp.id);
    }
  }

  async function handleQuickAddContact(e: React.FormEvent) {
    e.preventDefault();
    if (!activeApp || !newContactName.trim()) return;
    setError('');
    try {
      const created = await api.createContact({
        name: newContactName,
        company: activeApp.job.company,
        role: newContactRole,
        linkedin_url: newContactLinkedIn,
        relationship: newContactRel,
      });
      setNewContactName('');
      setNewContactRole('');
      setNewContactLinkedIn('');
      setShowAddContact(false);
      setDraftContactId(String(created.id));
      await refreshActive();
      setNotice(`Added ${created.name} at ${activeApp.job.company}.`);
    } catch (e) {
      setError((e as Error).message);
    }
  }

  async function handleDraftOutreach() {
    if (!activeApp) return;
    setError('');
    setNotice('');
    try {
      await api.draftOutreach(activeApp.id, {
        contact_id: draftContactId ? Number(draftContactId) : null,
        contact_name: draftCustomName,
        channel: draftChannel,
      });
      setNotice('Outreach draft created (status: draft). Review, edit, and approve before sending.');
      await refreshActive();
    } catch (e) {
      setError((e as Error).message);
    }
  }

  async function handleSaveOutreachEdit(msg: OutreachMessage) {
    const edited = editingBodies[msg.id];
    if (!edited) return;
    setError('');
    try {
      await api.updateOutreach(msg.id, { subject: edited.subject, body: edited.body });
      setNotice('Draft saved. Click Approve before sending.');
      await refreshActive();
    } catch (e) {
      setError((e as Error).message);
    }
  }

  async function handleApproveOutreach(msg: OutreachMessage) {
    setError('');
    try {
      const edited = editingBodies[msg.id];
      if (edited && (edited.body !== msg.body || edited.subject !== msg.subject)) {
        await api.updateOutreach(msg.id, { subject: edited.subject, body: edited.body });
      }
      await api.approveOutreach(msg.id);
      setNotice('Outreach approved! Copy & send it manually, then click "Mark as Sent".');
      await refreshActive();
    } catch (e) {
      setError((e as Error).message);
    }
  }

  async function handleMarkSent(msg: OutreachMessage) {
    setError('');
    try {
      await api.markOutreachSent(msg.id);
      setNotice('Marked as sent and set a 3-day follow-up reminder.');
      await refreshActive();
    } catch (e) {
      setError((e as Error).message);
    }
  }

  async function handleLogReply(msg: OutreachMessage, replied: boolean) {
    setError('');
    try {
      await api.logOutreachReply(msg.id, {
        replied,
        reply_notes: replied ? 'Connection responded!' : 'No response after follow-up.',
        advance_to_ready_to_apply: true,
      });
      setNotice(
        replied
          ? 'Reply logged (+learned boost) and application moved to Ready to Apply!'
          : 'No-response logged and application moved to Ready to Apply.'
      );
      await refreshActive();
    } catch (e) {
      setError((e as Error).message);
    }
  }

  async function handleCopy(msg: OutreachMessage) {
    const text = editingBodies[msg.id]?.body ?? msg.body;
    try {
      await navigator.clipboard.writeText(text);
      setCopiedId(msg.id);
      setTimeout(() => setCopiedId(null), 1500);
    } catch {
      setNotice('Copy manually from the text box.');
    }
  }

  async function handleTransition(target: PipelineStage, reason?: string) {
    if (!activeApp) return;
    setError('');
    setNotice('');
    try {
      await api.transitionApplication(activeApp.id, {
        stage: target,
        connection_override_reason: reason,
        outcome_reason: target === 'rejected' ? reason : undefined,
      });
      setShowOverrideBox(null);
      setOverrideReason('');
      setNotice(`Application moved to ${target.replaceAll('_', ' ')}.`);
      await refreshActive();
    } catch (e) {
      const msg = (e as Error).message;
      if (msg.includes('Connection-first gate')) {
        setShowOverrideBox(target);
      }
      setError(msg);
    }
  }

  async function handleSaveNotes() {
    if (!activeApp) return;
    await api.updateApplication(activeApp.id, { notes: notesDraft });
    setNotice('Application notes saved.');
    await refreshActive();
  }

  const filteredApps =
    stageFilter === 'all' ? apps : apps.filter((a) => a.stage === stageFilter);

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">Application Pipeline</h1>
          <p className="page-subtitle">
            Connection-first workflow: find a contact & draft outreach (HITL approved) before applying directly.
          </p>
        </div>
      </div>

      <div className="tabs">
        <button
          className={`tab-btn ${stageFilter === 'all' ? 'active' : ''}`}
          onClick={() => setStageFilter('all')}
        >
          All ({apps.length})
        </button>
        {STAGES.map((st) => {
          const count = apps.filter((a) => a.stage === st.key).length;
          return (
            <button
              key={st.key}
              className={`tab-btn ${stageFilter === st.key ? 'active' : ''}`}
              onClick={() => setStageFilter(st.key)}
            >
              {st.label} ({count})
            </button>
          );
        })}
      </div>

      {error && !activeApp && <div className="banner banner-red">{error}</div>}

      {loading ? (
        <div className="card muted">Loading pipeline...</div>
      ) : filteredApps.length === 0 ? (
        <div className="card muted">
          No applications in this stage yet. Approve jobs from <strong>Today's Picks</strong> to enter the pipeline.
        </div>
      ) : (
        <div className="grid-2">
          {filteredApps.map((app) => (
            <div
              key={app.id}
              className="card"
              style={{ cursor: 'pointer', marginTop: 0 }}
              onClick={() => void openDrawer(app.id)}
            >
              <div className="between">
                <div>
                  <h3 style={{ margin: 0, fontSize: 16 }}>{app.job.title}</h3>
                  <div className="muted">
                    <strong>{app.job.company}</strong> · {app.job.location || app.job.work_mode}
                  </div>
                </div>
                <span className="badge badge-blue" style={{ textTransform: 'capitalize' }}>
                  {app.stage.replaceAll('_', ' ')}
                </span>
              </div>
              <div className="row" style={{ marginTop: 12 }}>
                <span className="badge badge-green">
                  {app.matched_contacts_count} matching contact(s)
                </span>
                <span className="badge">{app.outreach_messages.length} outreach draft(s)</span>
                {app.next_step && <span className="muted">Next: {app.next_step}</span>}
              </div>
            </div>
          ))}
        </div>
      )}

      {activeApp && (
        <div
          className="drawer-backdrop"
          onClick={() => {
            setActiveApp(null);
            onSelectAppId(null);
          }}
        >
          <div className="drawer-panel" onClick={(e) => e.stopPropagation()}>
            <div className="between" style={{ marginBottom: 14 }}>
              <div>
                <h2 style={{ margin: 0 }}>{activeApp.job.title}</h2>
                <div className="muted">
                  <strong>{activeApp.job.company}</strong> · Stage:{' '}
                  <span className="badge badge-blue">{activeApp.stage.replaceAll('_', ' ')}</span>
                </div>
              </div>
              <button
                className="btn btn-sm"
                onClick={() => {
                  setActiveApp(null);
                  onSelectAppId(null);
                }}
              >
                <X size={15} /> Close
              </button>
            </div>

            {error && <div className="banner banner-red">{error}</div>}
            {notice && <div className="banner banner-green">{notice}</div>}

            {['connection_search', 'outreach_drafted', 'outreach_sent'].includes(activeApp.stage) && (
              <div className="banner banner-amber">
                <div className="row">
                  <ShieldCheck size={16} />
                  <strong>Connection-First Gate Active:</strong>
                </div>
                <div style={{ marginTop: 4 }}>
                  Reach out to someone at {activeApp.job.company} first. Nothing is ever sent automatically — you review,
                  approve, copy, and send manually.
                </div>
              </div>
            )}

            {/* Step A: Connections */}
            <div className="card">
              <div className="between" style={{ marginBottom: 10 }}>
                <h3 style={{ margin: 0, fontSize: 15 }}>
                  1. Connections at {activeApp.job.company}
                </h3>
                <div className="row">
                  {connections?.linkedin_search_url && (
                    <a
                      className="btn btn-sm"
                      href={connections.linkedin_search_url}
                      target="_blank"
                      rel="noreferrer"
                    >
                      Search LinkedIn <ExternalLink size={12} />
                    </a>
                  )}
                  <button
                    className="btn btn-sm"
                    onClick={() => setShowAddContact(!showAddContact)}
                  >
                    <UserPlus size={12} /> Add Contact
                  </button>
                </div>
              </div>

              {showAddContact && (
                <form
                  onSubmit={(e) => void handleQuickAddContact(e)}
                  style={{
                    padding: 12,
                    borderRadius: 8,
                    background: 'var(--bg)',
                    marginBottom: 12,
                  }}
                >
                  <div className="grid-2">
                    <div className="field">
                      <label className="label">Name *</label>
                      <input
                        className="input"
                        required
                        value={newContactName}
                        onChange={(e) => setNewContactName(e.target.value)}
                      />
                    </div>
                    <div className="field">
                      <label className="label">Role</label>
                      <input
                        className="input"
                        value={newContactRole}
                        onChange={(e) => setNewContactRole(e.target.value)}
                        placeholder="e.g. Engineering Manager"
                      />
                    </div>
                  </div>
                  <div className="grid-2">
                    <div className="field">
                      <label className="label">LinkedIn URL</label>
                      <input
                        className="input"
                        value={newContactLinkedIn}
                        onChange={(e) => setNewContactLinkedIn(e.target.value)}
                      />
                    </div>
                    <div className="field">
                      <label className="label">Relationship</label>
                      <select
                        className="select"
                        value={newContactRel}
                        onChange={(e) => setNewContactRel(e.target.value)}
                      >
                        <option value="1st_degree">1st-degree connection</option>
                        <option value="former_colleague">Former colleague</option>
                        <option value="alumni">Alumni</option>
                        <option value="recruiter">Recruiter</option>
                        <option value="cold_target">Cold target</option>
                      </select>
                    </div>
                  </div>
                  <button className="btn btn-primary btn-sm" type="submit">
                    Save Contact
                  </button>
                </form>
              )}

              {connections && connections.matched_contacts.length > 0 ? (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                  {connections.matched_contacts.map((c) => (
                    <div
                      key={c.id}
                      className="between"
                      style={{
                        padding: 10,
                        borderRadius: 8,
                        background: 'var(--bg-elevated)',
                        border: '1px solid var(--border)',
                      }}
                    >
                      <div>
                        <strong>{c.name}</strong>{' '}
                        <span className="badge">{c.relationship.replaceAll('_', ' ')}</span>
                        <div className="muted">
                          {c.role || 'Team member'} @ {c.company}
                        </div>
                      </div>
                      <div className="row">
                        {c.linkedin_url && (
                          <a className="btn btn-sm" href={c.linkedin_url} target="_blank" rel="noreferrer">
                            Profile <ExternalLink size={12} />
                          </a>
                        )}
                        <button
                          className="btn btn-primary btn-sm"
                          onClick={() => setDraftContactId(String(c.id))}
                        >
                          Select
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="muted" style={{ margin: 0 }}>
                  No saved contacts matched "{activeApp.job.company}". Search LinkedIn above or add someone you find.
                </p>
              )}
            </div>

            {/* Step B: Draft Outreach */}
            <div className="card">
              <h3 style={{ marginTop: 0, fontSize: 15 }}>2. Draft Outreach (Human-in-the-Loop)</h3>
              <div className="grid-2">
                <div className="field">
                  <label className="label">Recipient</label>
                  <select
                    className="select"
                    value={draftContactId}
                    onChange={(e) => setDraftContactId(e.target.value)}
                  >
                    <option value="">-- Enter name manually below --</option>
                    {(connections?.matched_contacts || []).map((c) => (
                      <option key={c.id} value={c.id}>
                        {c.name} ({c.role || c.relationship})
                      </option>
                    ))}
                  </select>
                </div>
                <div className="field">
                  <label className="label">Channel</label>
                  <select
                    className="select"
                    value={draftChannel}
                    onChange={(e) =>
                      setDraftChannel(
                        e.target.value as 'linkedin_connect_note' | 'linkedin_dm' | 'email'
                      )
                    }
                  >
                    <option value="linkedin_connect_note">LinkedIn Connection Note (≤300 chars)</option>
                    <option value="linkedin_dm">LinkedIn DM</option>
                    <option value="email">Email</option>
                  </select>
                </div>
              </div>
              {!draftContactId && (
                <div className="field">
                  <label className="label">Manual recipient name (optional)</label>
                  <input
                    className="input"
                    value={draftCustomName}
                    onChange={(e) => setDraftCustomName(e.target.value)}
                    placeholder="e.g. Sarah Chen"
                  />
                </div>
              )}
              <button className="btn btn-primary" onClick={() => void handleDraftOutreach()}>
                <MessageSquarePlus size={14} /> Generate Outreach Draft
              </button>

              {activeApp.outreach_messages.map((msg) => {
                const edit = editingBodies[msg.id] || { subject: msg.subject, body: msg.body };
                const tooLong =
                  msg.channel === 'linkedin_connect_note' && edit.body.length > 300;
                return (
                  <div
                    key={msg.id}
                    style={{
                      marginTop: 14,
                      padding: 12,
                      borderRadius: 8,
                      background: 'var(--bg-elevated)',
                      border: '1px solid var(--border)',
                    }}
                  >
                    <div className="between" style={{ marginBottom: 8 }}>
                      <div className="row">
                        <strong>To: {msg.contact_name_snapshot}</strong>
                        <span className="badge">{msg.channel.replaceAll('_', ' ')}</span>
                      </div>
                      <span
                        className={`badge ${
                          msg.status === 'approved' || msg.status === 'sent' || msg.status === 'replied'
                            ? 'badge-green'
                            : 'badge-amber'
                        }`}
                      >
                        Status: {msg.status}
                      </span>
                    </div>

                    {msg.channel === 'email' && (
                      <div className="field">
                        <label className="label">Subject</label>
                        <input
                          className="input"
                          value={edit.subject}
                          onChange={(e) =>
                            setEditingBodies({
                              ...editingBodies,
                              [msg.id]: { ...edit, subject: e.target.value },
                            })
                          }
                        />
                      </div>
                    )}

                    <div className="field">
                      <div className="between">
                        <label className="label">Message</label>
                        <span className={`muted ${tooLong ? 'badge badge-red' : ''}`}>
                          {edit.body.length}
                          {msg.channel === 'linkedin_connect_note' ? ' / 300 chars' : ' chars'}
                        </span>
                      </div>
                      <textarea
                        className="textarea"
                        value={edit.body}
                        onChange={(e) =>
                          setEditingBodies({
                            ...editingBodies,
                            [msg.id]: { ...edit, body: e.target.value },
                          })
                        }
                      />
                    </div>

                    <div className="row">
                      <button
                        className="btn btn-sm"
                        onClick={() => void handleSaveOutreachEdit(msg)}
                      >
                        Save Edits
                      </button>
                      {msg.status === 'draft' && (
                        <button
                          className="btn btn-success btn-sm"
                          disabled={tooLong}
                          onClick={() => void handleApproveOutreach(msg)}
                        >
                          <Check size={13} /> Approve Draft
                        </button>
                      )}
                      <button className="btn btn-sm" onClick={() => void handleCopy(msg)}>
                        <Copy size={13} /> {copiedId === msg.id ? 'Copied!' : 'Copy'}
                      </button>
                      {msg.status === 'approved' && (
                        <button
                          className="btn btn-primary btn-sm"
                          onClick={() => void handleMarkSent(msg)}
                        >
                          <Send size={13} /> Mark as Sent (Manual)
                        </button>
                      )}
                      {msg.status === 'sent' && (
                        <>
                          <button
                            className="btn btn-success btn-sm"
                            onClick={() => void handleLogReply(msg, true)}
                          >
                            Log Reply (Advance)
                          </button>
                          <button
                            className="btn btn-sm"
                            onClick={() => void handleLogReply(msg, false)}
                          >
                            No Reply (Proceed to Apply)
                          </button>
                        </>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>

            {/* Step C: Stage Actions & Override Gate */}
            <div className="card">
              <h3 style={{ marginTop: 0, fontSize: 15 }}>3. Pipeline Stage & Outcomes</h3>
              <div className="row">
                {activeApp.job.url && (
                  <a
                    className="btn btn-sm"
                    href={activeApp.job.url}
                    target="_blank"
                    rel="noreferrer"
                  >
                    Open Job Application <ExternalLink size={12} />
                  </a>
                )}
                <button
                  className="btn btn-sm"
                  onClick={() => void handleTransition('ready_to_apply')}
                >
                  Move to Ready to Apply
                </button>
                <button
                  className="btn btn-primary btn-sm"
                  onClick={() => void handleTransition('applied')}
                >
                  Mark Applied
                </button>
                <button
                  className="btn btn-success btn-sm"
                  onClick={() => void handleTransition('interviewing')}
                >
                  Interviewing (+Learn)
                </button>
                <button
                  className="btn btn-success btn-sm"
                  onClick={() => void handleTransition('offer')}
                >
                  Offer (+Learn)
                </button>
                <button
                  className="btn btn-danger btn-sm"
                  onClick={() => void handleTransition('rejected', 'Application rejected')}
                >
                  Rejected (-Learn)
                </button>
              </div>

              {showOverrideBox && (
                <div
                  style={{
                    marginTop: 12,
                    padding: 12,
                    borderRadius: 8,
                    background: 'var(--amber-soft)',
                    border: '1px solid rgba(245,158,11,0.4)',
                  }}
                >
                  <div className="row" style={{ marginBottom: 6 }}>
                    <AlertTriangle size={15} />
                    <strong>Connection-First Override Required</strong>
                  </div>
                  <p className="muted" style={{ marginTop: 0 }}>
                    No outreach has been marked sent yet. Provide a quick reason to proceed directly:
                  </p>
                  <div className="row">
                    <input
                      className="input"
                      style={{ flex: 1 }}
                      value={overrideReason}
                      onChange={(e) => setOverrideReason(e.target.value)}
                      placeholder="e.g., No connections found / Role closes tonight"
                    />
                    <button
                      className="btn btn-primary btn-sm"
                      disabled={!overrideReason.trim()}
                      onClick={() => void handleTransition(showOverrideBox, overrideReason)}
                    >
                      Confirm Override
                    </button>
                  </div>
                </div>
              )}

              <div className="field" style={{ marginTop: 14 }}>
                <label className="label">Notes</label>
                <textarea
                  className="textarea"
                  value={notesDraft}
                  onChange={(e) => setNotesDraft(e.target.value)}
                  placeholder="Interview notes, referral details, follow-up plan..."
                />
                <button
                  className="btn btn-sm"
                  style={{ marginTop: 8 }}
                  onClick={() => void handleSaveNotes()}
                >
                  Save Notes
                </button>
              </div>

              {activeApp.activity_logs.length > 0 && (
                <div style={{ marginTop: 14 }}>
                  <label className="label">Activity Log</label>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                    {activeApp.activity_logs.map((log) => (
                      <div key={log.id} className="muted" style={{ fontSize: 12 }}>
                        <strong>[{log.action}]</strong> {log.details}
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
