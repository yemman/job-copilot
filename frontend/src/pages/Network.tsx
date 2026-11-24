import { useEffect, useState } from 'react';
import { ExternalLink, Search, Trash2, Upload, UserPlus } from 'lucide-react';
import { api } from '../api';
import type { Contact } from '../types';

export function Network() {
  const [contacts, setContacts] = useState<Contact[]>([]);
  const [search, setSearch] = useState('');
  const [notice, setNotice] = useState('');
  const [error, setError] = useState('');

  const [name, setName] = useState('');
  const [company, setCompany] = useState('');
  const [role, setRole] = useState('');
  const [linkedinUrl, setLinkedinUrl] = useState('');
  const [email, setEmail] = useState('');
  const [relationship, setRelationship] = useState('1st_degree');
  const [notes, setNotes] = useState('');

  async function loadContacts() {
    setError('');
    try {
      setContacts(await api.listContacts(search || undefined));
    } catch (e) {
      setError((e as Error).message);
    }
  }

  useEffect(() => {
    void loadContacts();
  }, []);

  async function handleAdd(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim()) return;
    setError('');
    try {
      await api.createContact({
        name,
        company,
        role,
        linkedin_url: linkedinUrl,
        email,
        relationship,
        notes,
      });
      setName('');
      setCompany('');
      setRole('');
      setLinkedinUrl('');
      setEmail('');
      setNotes('');
      setNotice('Contact added.');
      await loadContacts();
    } catch (e) {
      setError((e as Error).message);
    }
  }

  async function handleCsvUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setError('');
    setNotice('');
    try {
      const res = await api.importLinkedInCsv(file);
      setNotice(
        `Imported ${res.inserted} contact(s) from ${res.parsed} row(s) (${res.skipped_duplicates} duplicate(s) skipped).`
      );
      await loadContacts();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      e.target.value = '';
    }
  }

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">Network & Connections</h1>
          <p className="page-subtitle">
            Contacts here are automatically matched to companies in your pipeline so you reach out before applying.
          </p>
        </div>
        <label className="btn btn-primary" style={{ cursor: 'pointer' }}>
          <Upload size={14} /> Import LinkedIn Connections CSV
          <input
            type="file"
            accept=".csv,text/csv"
            style={{ display: 'none' }}
            onChange={(e) => void handleCsvUpload(e)}
          />
        </label>
      </div>

      <div className="banner banner-blue">
        <strong>Tip — Export your LinkedIn Connections:</strong> On LinkedIn go to{' '}
        <em>Settings & Privacy → Data Privacy → Get a copy of your data → Connections</em>, then upload{' '}
        <code>Connections.csv</code> here.
      </div>

      {error && <div className="banner banner-red">{error}</div>}
      {notice && <div className="banner banner-green">{notice}</div>}

      <div className="grid-2" style={{ alignItems: 'start' }}>
        <form className="card" onSubmit={(e) => void handleAdd(e)}>
          <h3 style={{ marginTop: 0 }}>Add Contact Manually</h3>
          <div className="grid-2">
            <div className="field">
              <label className="label">Full Name *</label>
              <input className="input" required value={name} onChange={(e) => setName(e.target.value)} />
            </div>
            <div className="field">
              <label className="label">Company</label>
              <input className="input" value={company} onChange={(e) => setCompany(e.target.value)} />
            </div>
          </div>
          <div className="grid-2">
            <div className="field">
              <label className="label">Role / Title</label>
              <input className="input" value={role} onChange={(e) => setRole(e.target.value)} />
            </div>
            <div className="field">
              <label className="label">Relationship</label>
              <select
                className="select"
                value={relationship}
                onChange={(e) => setRelationship(e.target.value)}
              >
                <option value="1st_degree">1st-degree LinkedIn</option>
                <option value="former_colleague">Former colleague</option>
                <option value="alumni">Alumni</option>
                <option value="recruiter">Recruiter</option>
                <option value="cold_target">Cold target</option>
              </select>
            </div>
          </div>
          <div className="grid-2">
            <div className="field">
              <label className="label">LinkedIn URL</label>
              <input className="input" value={linkedinUrl} onChange={(e) => setLinkedinUrl(e.target.value)} />
            </div>
            <div className="field">
              <label className="label">Email</label>
              <input className="input" value={email} onChange={(e) => setEmail(e.target.value)} />
            </div>
          </div>
          <div className="field">
            <label className="label">Notes</label>
            <input className="input" value={notes} onChange={(e) => setNotes(e.target.value)} />
          </div>
          <button className="btn btn-primary" type="submit">
            <UserPlus size={14} /> Add Contact
          </button>
        </form>

        <div className="card">
          <div className="between" style={{ marginBottom: 12 }}>
            <h3 style={{ margin: 0 }}>Saved Contacts ({contacts.length})</h3>
            <div className="row">
              <input
                className="input"
                style={{ width: 200 }}
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Filter name or company..."
              />
              <button className="btn btn-sm" onClick={() => void loadContacts()}>
                <Search size={13} />
              </button>
            </div>
          </div>
          <table className="table">
            <thead>
              <tr>
                <th>Name</th>
                <th>Company & Role</th>
                <th>Source</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {contacts.map((c) => (
                <tr key={c.id}>
                  <td>
                    <strong>{c.name}</strong>
                    <div className="muted">{c.relationship.replaceAll('_', ' ')}</div>
                  </td>
                  <td>
                    <div>{c.company || '—'}</div>
                    <div className="muted">{c.role}</div>
                  </td>
                  <td>
                    <span className="badge">{c.source}</span>
                  </td>
                  <td className="row">
                    {c.linkedin_url && (
                      <a href={c.linkedin_url} target="_blank" rel="noreferrer">
                        <ExternalLink size={13} />
                      </a>
                    )}
                    <button
                      className="btn btn-danger btn-sm"
                      onClick={() => void api.deleteContact(c.id).then(loadContacts)}
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
    </div>
  );
}
