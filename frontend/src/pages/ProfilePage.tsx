import { useEffect, useState } from 'react';
import { Plus, Save, Upload, X } from 'lucide-react';
import { api } from '../api';
import type { Profile } from '../types';

const ALL_DAYS = ['sun', 'mon', 'tue', 'wed', 'thu', 'fri', 'sat'];

function TagEditor({
  label,
  items,
  onChange,
  placeholder,
}: {
  label: string;
  items: string[];
  onChange: (next: string[]) => void;
  placeholder: string;
}) {
  const [draft, setDraft] = useState('');
  function add() {
    const val = draft.trim();
    if (!val || items.includes(val)) return;
    onChange([...items, val]);
    setDraft('');
  }
  return (
    <div className="field">
      <label className="label">{label}</label>
      <div className="chips" style={{ marginBottom: 8 }}>
        {items.map((item) => (
          <span key={item} className="chip">
            {item}
            <button
              type="button"
              style={{
                background: 'none',
                border: 'none',
                color: 'var(--text-muted)',
                cursor: 'pointer',
                padding: 0,
                display: 'inline-flex',
              }}
              onClick={() => onChange(items.filter((x) => x !== item))}
            >
              <X size={12} />
            </button>
          </span>
        ))}
      </div>
      <div className="row">
        <input
          className="input"
          style={{ flex: 1 }}
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          placeholder={placeholder}
          onKeyDown={(e) => {
            if (e.key === 'Enter') {
              e.preventDefault();
              add();
            }
          }}
        />
        <button className="btn btn-sm" type="button" onClick={add}>
          <Plus size={13} /> Add
        </button>
      </div>
    </div>
  );
}

export function ProfilePage() {
  const [profile, setProfile] = useState<Profile | null>(null);
  const [suggestedSkills, setSuggestedSkills] = useState<string[]>([]);
  const [saving, setSaving] = useState(false);
  const [notice, setNotice] = useState('');
  const [error, setError] = useState('');

  useEffect(() => {
    void api.getProfile().then(setProfile).catch((e: Error) => setError(e.message));
  }, []);

  async function handleSave(e: React.FormEvent) {
    e.preventDefault();
    if (!profile) return;
    setSaving(true);
    setError('');
    setNotice('');
    try {
      const updated = await api.updateProfile(profile);
      setProfile(updated);
      setNotice('Profile, resume, and Sun–Wed schedule saved.');
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setSaving(false);
    }
  }

  async function handleResumeUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setError('');
    setNotice('');
    try {
      const res = await api.uploadResume(file);
      setProfile(res.profile);
      setSuggestedSkills(
        res.extracted_skills.filter((s) => !res.profile.skills.includes(s))
      );
      setNotice(`Uploaded "${res.filename}" and extracted ${res.extracted_skills.length} skill(s).`);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      e.target.value = '';
    }
  }

  if (!profile) {
    return <div className="card muted">Loading profile...</div>;
  }

  return (
    <form onSubmit={(e) => void handleSave(e)}>
      <div className="page-header">
        <div>
          <h1 className="page-title">Profile, Resume & Schedule</h1>
          <p className="page-subtitle">
            Powers job fit scoring, Gemini explanations, outreach drafting, and your Sun–Wed daily picks.
          </p>
        </div>
        <div className="row">
          <label className="btn" style={{ cursor: 'pointer' }}>
            <Upload size={14} /> Upload Resume (.pdf / .txt / .md)
            <input
              type="file"
              accept=".pdf,.txt,.md"
              style={{ display: 'none' }}
              onChange={(e) => void handleResumeUpload(e)}
            />
          </label>
          <button className="btn btn-primary" type="submit" disabled={saving}>
            <Save size={14} /> {saving ? 'Saving...' : 'Save Profile'}
          </button>
        </div>
      </div>

      {error && <div className="banner banner-red">{error}</div>}
      {notice && <div className="banner banner-green">{notice}</div>}

      {suggestedSkills.length > 0 && (
        <div className="banner banner-blue">
          <div style={{ marginBottom: 6 }}>
            <strong>Skills detected in your resume:</strong> Click any skill to add it:
          </div>
          <div className="chips">
            {suggestedSkills.map((sk) => (
              <button
                key={sk}
                type="button"
                className="btn btn-sm"
                onClick={() => {
                  setProfile({ ...profile, skills: [...profile.skills, sk] });
                  setSuggestedSkills(suggestedSkills.filter((x) => x !== sk));
                }}
              >
                + {sk}
              </button>
            ))}
          </div>
        </div>
      )}

      <div className="grid-2">
        <div className="card">
          <h3 style={{ marginTop: 0 }}>Candidate Identity & Preferences</h3>
          <div className="grid-2">
            <div className="field">
              <label className="label">Full Name</label>
              <input
                className="input"
                value={profile.full_name}
                onChange={(e) => setProfile({ ...profile, full_name: e.target.value })}
              />
            </div>
            <div className="field">
              <label className="label">Years of Experience</label>
              <input
                type="number"
                min={0}
                max={60}
                className="input"
                value={profile.experience_years}
                onChange={(e) =>
                  setProfile({ ...profile, experience_years: Number(e.target.value) })
                }
              />
            </div>
          </div>
          <div className="field">
            <label className="label">Headline</label>
            <input
              className="input"
              value={profile.headline}
              onChange={(e) => setProfile({ ...profile, headline: e.target.value })}
              placeholder="e.g., Senior Backend Engineer (Python / Cloud)"
            />
          </div>
          <div className="field">
            <label className="label">Preferred Work Mode</label>
            <select
              className="select"
              value={profile.work_mode}
              onChange={(e) =>
                setProfile({
                  ...profile,
                  work_mode: e.target.value as Profile['work_mode'],
                })
              }
            >
              <option value="any">Any</option>
              <option value="remote">Remote</option>
              <option value="hybrid">Hybrid</option>
              <option value="onsite">Onsite</option>
            </select>
          </div>

          <TagEditor
            label="Core Skills"
            items={profile.skills}
            onChange={(skills) => setProfile({ ...profile, skills })}
            placeholder="Add skill (e.g., Python, React, GCP)"
          />
          <TagEditor
            label="Target Roles"
            items={profile.target_roles}
            onChange={(target_roles) => setProfile({ ...profile, target_roles })}
            placeholder="Add role (e.g., Backend Engineer)"
          />
          <TagEditor
            label="Preferred Locations"
            items={profile.preferred_locations}
            onChange={(preferred_locations) =>
              setProfile({ ...profile, preferred_locations })
            }
            placeholder="Add location (e.g., Tel Aviv, Remote)"
          />
          <TagEditor
            label="Dealbreakers (-25 score penalty)"
            items={profile.dealbreakers}
            onChange={(dealbreakers) => setProfile({ ...profile, dealbreakers })}
            placeholder="Add dealbreaker (e.g., PHP, Unpaid)"
          />
        </div>

        <div>
          <div className="card">
            <h3 style={{ marginTop: 0 }}>Resume Text {profile.resume_filename ? `(${profile.resume_filename})` : ''}</h3>
            <div className="field">
              <textarea
                className="textarea"
                style={{ minHeight: 240 }}
                value={profile.resume_text}
                onChange={(e) => setProfile({ ...profile, resume_text: e.target.value })}
                placeholder="Paste your resume text here or upload a PDF/TXT/MD file above..."
              />
            </div>
            <div className="field">
              <label className="label">Extra Notes for AI Matcher & Outreach</label>
              <textarea
                className="textarea"
                value={profile.notes_for_ai}
                onChange={(e) => setProfile({ ...profile, notes_for_ai: e.target.value })}
                placeholder="e.g., Prefer Series B+ or AI devtools companies; looking for product impact."
              />
            </div>
          </div>

          <div className="card">
            <h3 style={{ marginTop: 0 }}>Sun–Wed Digest Schedule</h3>
            <div className="grid-2">
              <div className="field">
                <label className="label">Jobs per Day (3–5)</label>
                <input
                  type="number"
                  min={3}
                  max={5}
                  className="input"
                  value={profile.daily_pick_count}
                  onChange={(e) =>
                    setProfile({
                      ...profile,
                      daily_pick_count: Math.max(3, Math.min(5, Number(e.target.value))),
                    })
                  }
                />
              </div>
              <div className="field">
                <label className="label">Run Hour (0–23)</label>
                <input
                  type="number"
                  min={0}
                  max={23}
                  className="input"
                  value={profile.digest_hour}
                  onChange={(e) =>
                    setProfile({ ...profile, digest_hour: Number(e.target.value) })
                  }
                />
              </div>
            </div>
            <div className="field">
              <label className="label">Active Digest Days (default Sun–Wed)</label>
              <div className="row">
                {ALL_DAYS.map((day) => {
                  const active = profile.digest_days.includes(day);
                  return (
                    <label key={day} className="chip" style={{ cursor: 'pointer' }}>
                      <input
                        type="checkbox"
                        checked={active}
                        onChange={(e) => {
                          const next = e.target.checked
                            ? [...profile.digest_days, day]
                            : profile.digest_days.filter((d) => d !== day);
                          setProfile({ ...profile, digest_days: next });
                        }}
                      />
                      <span style={{ textTransform: 'uppercase' }}>{day}</span>
                    </label>
                  );
                })}
              </div>
            </div>
            <div className="field">
              <label className="label">Timezone</label>
              <input
                className="input"
                value={profile.timezone}
                onChange={(e) => setProfile({ ...profile, timezone: e.target.value })}
              />
            </div>
          </div>
        </div>
      </div>
    </form>
  );
}
