import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { Metrics } from '../components/Progress';
import { setSession } from '../services/api';
import { QuestionChoices } from './Assessments';
import { AuthPage } from './Auth';
import { RoadmapPage } from './Student';

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  setSession(null);
});

describe('placement workflow components', () => {
  it('shows absent predictions without a fabricated value', () => {
    render(<Metrics latest={null} count={0}
      predictions={{ status: 'synthetic_validation_only', classification: null, regression: null }} />);
    expect(screen.getByText('No assessments available')).toBeInTheDocument();
    expect(screen.getAllByText('Model validated on synthetic data only')).toHaveLength(2);
    expect(screen.getAllByText('—')).toHaveLength(3);
  });

  it('keeps answer keys outside the question choices', () => {
    const onSelect = vi.fn();
    render(<QuestionChoices question={{ id: 'q1', position: 1, text: 'Pick a number', difficulty: 'easy',
      options: [{ label: 'A', text: 'One' }, { label: 'B', text: 'Two' }] }} onSelect={onSelect} selected="A" />);
    expect(screen.getByRole('radio', { name: 'A One' })).toBeChecked();
    fireEvent.click(screen.getByRole('radio', { name: 'B Two' }));
    expect(onSelect).toHaveBeenCalledWith('B');
    expect(screen.queryByText(/correct answer/i)).not.toBeInTheDocument();
  });

  it('registers a student through the versioned HTTP API', async () => {
    const session = vi.fn();
    const server = vi.fn(async () => new Response(JSON.stringify({
      access_token: 'access', refresh_token: 'refresh', token_type: 'bearer',
    }), { status: 201 }));
    vi.stubGlobal('fetch', server);
    render(<AuthPage onSession={session} />);
    fireEvent.click(screen.getByRole('button', { name: 'Create an account' }));
    fireEvent.change(screen.getByLabelText('Full name'), { target: { value: 'Student Test' } });
    fireEvent.change(screen.getByLabelText('Department'), { target: { value: 'Computing' } });
    fireEvent.change(screen.getByLabelText('Email'), { target: { value: 'new@example.org' } });
    fireEvent.change(screen.getByLabelText('Password'), { target: { value: 'a-testing-password' } });
    fireEvent.click(screen.getByRole('button', { name: 'Create account' }));
    await screen.findByRole('button', { name: 'Create account' });
    expect(server).toHaveBeenCalledWith('/api/v1/auth/register',
      expect.objectContaining({ method: 'POST' }));
    expect(session).toHaveBeenCalledTimes(1);
  });

  it('shows a usable rule-based roadmap with curated resources', async () => {
    vi.stubGlobal('fetch', async () => new Response(JSON.stringify({ status: 'fallback', roadmap: {
      id: 'r1', assessment_id: 'a1', current_readiness: 65, target_role: 'Data Analyst', duration_weeks: 1,
      priority_skills: ['SQL'], weekly_hours: 5, explanation: 'Start with SQL.',
      resources: [{ id: 'postgres', title: 'PostgreSQL tutorial', url: 'https://www.postgresql.org/docs/' }],
      weekly_plan: [{ week: 1, focus: 'SQL', hours: 5, tasks: ['Practice JOINs'] }],
      tasks: [{ id: 't1', title: 'Practice JOINs', week: 1, completed: false }],
      practice_tasks: [], reassessment_milestones: ['Reassess after one week.'],
    } })));
    render(<QueryClientProvider client={new QueryClient()}><MemoryRouter><RoadmapPage /></MemoryRouter></QueryClientProvider>);
    expect(await screen.findByText('Rule-based roadmap')).toBeInTheDocument();
    expect(screen.getByRole('checkbox', { name: 'Practice JOINs' })).not.toBeChecked();
    expect(screen.getByRole('link', { name: 'PostgreSQL tutorial' })).toHaveAttribute('href', 'https://www.postgresql.org/docs/');
  });
});
