import { useEffect, useState } from 'react';
import {
  Brain,
  Briefcase,
  Cpu,
  Database,
  Kanban,
  Sparkles,
  UserCheck,
  Users,
} from 'lucide-react';
import { api } from './api';
import { JobsExplorer } from './pages/JobsExplorer';
import { Learning } from './pages/Learning';
import { Network } from './pages/Network';
import { Pipeline } from './pages/Pipeline';
import { ProfilePage } from './pages/ProfilePage';
import { TodayDigest } from './pages/TodayDigest';
import type { HealthStatus } from './types';

type NavKey = 'digest' | 'pipeline' | 'jobs' | 'network' | 'learning' | 'profile';

export default function App() {
  const [nav, setNav] = useState<NavKey>('digest');
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [selectedAppId, setSelectedAppId] = useState<number | null>(null);
  const [demoNotice, setDemoNotice] = useState('');
  const [refreshTick, setRefreshTick] = useState(0);

  async function refreshHealth() {
    try {
      setHealth(await api.health());
    } catch {
      // backend might be starting
    }
  }

  useEffect(() => {
    void refreshHealth();
  }, []);

  async function handleLoadDemo() {
    try {
      const res = await api.seedDemo();
      setDemoNotice(
        `Loaded demo data: +${res.jobs_added} jobs, +${res.contacts_added} contacts, +${res.rules_added} learned rules. Click "Generate Today's Picks"!`
      );
      setRefreshTick((t) => t + 1);
      setTimeout(() => setDemoNotice(''), 6000);
    } catch (e) {
      setDemoNotice((e as Error).message);
    }
  }

  function openApplicationFromDigest(appId: number) {
    setSelectedAppId(appId);
    setNav('pipeline');
  }

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <Briefcase size={22} color="#60a5fa" />
          <div>
            <div className="brand-title">Job Copilot</div>
            <div className="brand-sub">Sun–Wed · Connection-First HITL</div>
          </div>
        </div>

        <button
          className={`nav-btn ${nav === 'digest' ? 'active' : ''}`}
          onClick={() => setNav('digest')}
        >
          <Sparkles size={16} /> Today's Picks
        </button>
        <button
          className={`nav-btn ${nav === 'pipeline' ? 'active' : ''}`}
          onClick={() => setNav('pipeline')}
        >
          <Kanban size={16} /> Pipeline & Outreach
        </button>
        <button
          className={`nav-btn ${nav === 'jobs' ? 'active' : ''}`}
          onClick={() => setNav('jobs')}
        >
          <Database size={16} /> Jobs & ATS Sources
        </button>
        <button
          className={`nav-btn ${nav === 'network' ? 'active' : ''}`}
          onClick={() => setNav('network')}
        >
          <Users size={16} /> Network & CSV
        </button>
        <button
          className={`nav-btn ${nav === 'learning' ? 'active' : ''}`}
          onClick={() => setNav('learning')}
        >
          <Brain size={16} /> What It Learned
        </button>
        <button
          className={`nav-btn ${nav === 'profile' ? 'active' : ''}`}
          onClick={() => setNav('profile')}
        >
          <UserCheck size={16} /> Profile & Resume
        </button>

        <div className="sidebar-footer">
          <div className="muted" style={{ fontSize: 12 }}>
            Human-in-the-loop guaranteed: no auto-apply, no auto-DM.
          </div>
        </div>
      </aside>

      <div className="main-area">
        <header className="topbar">
          <div className="row">
            <span className={`badge ${health?.ai_mode === 'gemini' ? 'badge-green' : 'badge-amber'}`}>
              <Cpu size={12} />
              {health?.ai_mode === 'gemini'
                ? `Gemini Active (${health.gemini_model})`
                : 'Offline Heuristic Mode (No GEMINI_API_KEY)'}
            </span>
            <span className="badge badge-blue">
              Schedule: Sun–Wed {health?.scheduler_running ? '· Auto-Cron On' : ''}
            </span>
          </div>
          <div className="row">
            <button className="btn btn-sm" onClick={() => void handleLoadDemo()}>
              Load Demo Data
            </button>
          </div>
        </header>

        <main className="content">
          {demoNotice && <div className="banner banner-green">{demoNotice}</div>}

          {nav === 'digest' && (
            <TodayDigest
              key={`digest-${refreshTick}`}
              onOpenApplication={openApplicationFromDigest}
            />
          )}
          {nav === 'pipeline' && (
            <Pipeline
              key={`pipe-${refreshTick}`}
              selectedAppId={selectedAppId}
              onSelectAppId={setSelectedAppId}
            />
          )}
          {nav === 'jobs' && <JobsExplorer key={`jobs-${refreshTick}`} />}
          {nav === 'network' && <Network key={`net-${refreshTick}`} />}
          {nav === 'learning' && <Learning key={`learn-${refreshTick}`} />}
          {nav === 'profile' && <ProfilePage key={`prof-${refreshTick}`} />}
        </main>
      </div>
    </div>
  );
}
