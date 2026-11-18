import { useQuery, useQueryClient } from '@tanstack/react-query';
import { BarChart3, BookOpen, Briefcase, ClipboardList, Code2, House, LogOut, Route as RouteIcon, Settings2, Users } from 'lucide-react';
import { useState } from 'react';
import { Link, NavLink, Navigate, Route, Routes } from 'react-router';
import { Button, Logo, State } from '../components/ui';
import { AdminPage } from '../pages/Admin';
import { AssessmentPage, AssessmentsPage, PracticePage } from '../pages/Assessments';
import { AuthPage } from '../pages/Auth';
import { CodingPage } from '../pages/Coding';
import { PlacementPage, TrainerPage } from '../pages/Staff';
import { CareerPage, RoadmapPage, StudentHome } from '../pages/Student';
import { ApiError, api, getSession, json, setSession } from '../services/api';
import type { User } from '../types/api';

const studentNav = [
  { to: '/', label: 'Overview', icon: House },
  { to: '/career', label: 'Career role', icon: Briefcase },
  { to: '/assessments', label: 'Assessments', icon: ClipboardList },
  { to: '/practice', label: 'Adaptive practice', icon: BookOpen },
  { to: '/coding', label: 'Python coding', icon: Code2 },
  { to: '/roadmap', label: 'Learning roadmap', icon: RouteIcon },
];

export function App() {
  const query = useQueryClient();
  const [authenticated, setAuthenticated] = useState(Boolean(getSession()));
  const [sessionRevision, setSessionRevision] = useState(0);
  const user = useQuery({ queryKey: ['me', sessionRevision], queryFn: () => api<User>('/auth/me'),
    enabled: authenticated, retry: false, staleTime: 15000 });
  const signOut = async () => {
    const session = getSession();
    if (session) {
      void api('/auth/logout', json('POST', { refresh_token: session.refresh_token })).catch(() => undefined);
    }
    setSession(null);
    query.clear();
    setAuthenticated(false);
  };
  if (!authenticated || (user.error instanceof ApiError && user.error.status === 401)) {
    return <AuthPage onSession={() => {
      query.clear(); setSessionRevision(revision => revision + 1); setAuthenticated(true);
    }} />;
  }
  const account = user.data;
  if (!account) return <div className="pending-shell"><Logo /><State loading={user.isLoading} error={user.error} />
    {user.error && <div className="inline-form"><Button onClick={() => void user.refetch()}>Try again</Button>
      <Button variant="outline" onClick={() => void signOut()}>Sign out</Button></div>}</div>;
  const staff = {
    trainer: [{ to: '/', label: 'Assigned students', icon: Users }],
    placement: [{ to: '/', label: 'Placement analytics', icon: BarChart3 }],
    admin: [{ to: '/', label: 'Administration', icon: Settings2 }, { to: '/placement', label: 'Placement analytics', icon: BarChart3 }],
  };
  const nav = account.role === 'student' ? studentNav : staff[account.role];
  return <div className="workspace">
    <aside className="sidebar"><Link to="/" className="brand-link" aria-label="Placement Readiness home"><Logo /></Link>
      <nav aria-label="Workspace navigation">{nav.map(({ to, label, icon: Icon }) =>
        <NavLink to={to} end={to === '/'} key={to}><Icon size={18} /><span>{label}</span></NavLink>)}</nav>
      <div className="sidebar-account">
        <span className="avatar" aria-hidden="true">{account.display_name.slice(0, 1).toUpperCase()}</span>
        <div><strong>{account.display_name}</strong><small>{account.role}</small></div>
        <button type="button" className="icon-button" onClick={() => void signOut()} aria-label="Sign out"><LogOut size={17} /></button>
      </div>
    </aside>
    <main className="workspace-main"><Routes>
      {account.role === 'student' && <>
        <Route path="/" element={<StudentHome user={account} />} />
        <Route path="/career" element={<CareerPage />} />
        <Route path="/assessments" element={<AssessmentsPage />} />
        <Route path="/assessments/:id" element={<AssessmentPage />} />
        <Route path="/practice" element={<PracticePage />} />
        <Route path="/coding" element={<CodingPage />} />
        <Route path="/roadmap" element={<RoadmapPage />} />
      </>}
      {account.role === 'trainer' && <Route path="/" element={<TrainerPage />} />}
      {account.role === 'placement' && <Route path="/" element={<PlacementPage />} />}
      {account.role === 'admin' && <><Route path="/" element={<AdminPage />} /><Route path="/placement" element={<PlacementPage />} /></>}
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes></main>
  </div>;
}
