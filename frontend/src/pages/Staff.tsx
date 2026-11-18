import { useMutation, useQueryClient } from '@tanstack/react-query';
import { BarChart3, CircleGauge, Users } from 'lucide-react';
import { useState } from 'react';
import { ProgressPanels } from '../components/Progress';
import { Button, Card, Empty, Header, State, Status, scoreLabel } from '../components/ui';
import { useAPI } from '../hooks/queries';
import { api, json } from '../services/api';
import type { Progress } from '../types/api';

type Assigned = { id: string; display_name: string; department: string; synthetic: boolean };
type Analytics = Progress & { display_name: string; support_priority: string };
type Review = { id: string; text: string; category: string; difficulty: string; options: { text: string; correct: boolean }[] };

export function TrainerPage() {
  const cache = useQueryClient();
  const [id, setId] = useState('');
  const [reviewTarget, setTarget] = useState('');
  const [detail, setDetail] = useState('');
  const assigned = useAPI<Assigned[]>('/trainers/students');
  const current = useAPI<Analytics>(`/trainers/students/${id}/analytics`, Boolean(id));
  const pending = useAPI<Review[]>('/trainers/questions');
  const submit = useMutation({ mutationFn: () => api(`/trainers/questions/${reviewTarget}/reviews`, json('POST', { detail })),
    onSuccess: () => { setDetail(''); void cache.invalidateQueries({ queryKey: ['/trainers/questions'] }); } });

  return <><Header title="Trainer workspace">Review assigned students and recommend learning support.</Header>
    <Card title="Assigned students"><State loading={assigned.isLoading} error={assigned.error}>
      {assigned.data?.length ? <div className="rows">{assigned.data.map(item => <button className="row" type="button"
        aria-pressed={id === item.id} key={item.id} onClick={() => setId(item.id)}>
        <div><strong>{item.display_name}</strong><small>{item.department}</small></div>{item.synthetic && <Status>Synthetic</Status>}
      </button>)}</div> : <Empty>No students have been assigned.</Empty>}</State></Card>
    {id && <State loading={current.isLoading} error={current.error}>
      {current.data && <><Card title={current.data.display_name} action={<Status>{current.data.support_priority.replaceAll('_', ' ')}</Status>}>
        <p className="muted">{current.data.latest ? `Current readiness ${scoreLabel(current.data.latest.score)}%` : 'No assessments available.'}</p>
      </Card><ProgressPanels history={current.data.history} topics={current.data.topics} /></>}
    </State>}
    <Card title="Question reviews"><State loading={pending.isLoading} error={pending.error}>
      {pending.data?.length ? pending.data.map(row => <details className="review" key={row.id}
        onToggle={e => { if (e.currentTarget.open) { setTarget(row.id); setDetail(''); } }}>
        <summary>{row.text} <Status>{row.category} · {row.difficulty}</Status></summary>
        <ul className="plain-list">{row.options.map(option => <li key={option.text}>{option.text}{option.correct && ' (marked correct)'}</li>)}</ul>
        {reviewTarget === row.id && <form onSubmit={e => { e.preventDefault(); submit.mutate(); }}>
          <label>Review notes<textarea value={detail} minLength={5} maxLength={2500} required onChange={e => setDetail(e.target.value)} /></label>
          <Button disabled={submit.isPending} type="submit">Save review</Button><State error={submit.error} />
          {submit.isSuccess && <p className="feedback" role="status">Review saved.</p>}
        </form>}
      </details>) : <Empty>No pending questions to review.</Empty>}
    </State></Card>
  </>;
}

type Group = { name: string; students: number; mean_score: number; readiness_rate: number };
type Cohort = { status: string; minimum?: number; students?: number; mean_score?: number; support_candidates?: number;
  mean_reassessment_change?: number | null; departments?: Group[]; roles?: Group[];
  trend?: { attempt: number; students: number; mean_score: number }[] };
type Gap = { topic_id: string; topic: string; students: number; weak_percent: number; priority: number; title?: string };

function GroupTable({ data }: { data: Group[] }) {
  return data.length ? <div className="table-scroll"><table><thead><tr>
    <th>Group</th><th>Students</th><th>Mean score</th><th>At threshold</th></tr></thead>
    <tbody>{data.map(row => <tr key={row.name}><td>{row.name}</td><td>{row.students}</td>
      <td>{scoreLabel(row.mean_score)}%</td><td>{scoreLabel(row.readiness_rate * 100)}%</td></tr>)}</tbody></table></div>
    : <Empty>No group meets the minimum cohort size.</Empty>;
}

export function PlacementPage() {
  const [demo, setDemo] = useState(false);
  const suffix = '?synthetic=' + demo;
  const cohort = useAPI<Cohort>('/placement/overview' + suffix);
  const gaps = useAPI<Gap[]>('/placement/skill-gaps' + suffix);
  const proposals = useAPI<Gap[]>('/placement/workshop-recommendations' + suffix);
  const data = cohort.data;
  return <><Header title="Placement analytics" aside={
    <label className="checkbox-label"><input type="checkbox" checked={demo} onChange={e => setDemo(e.target.checked)} />Synthetic cohort</label>}>
    Aggregate standardized scores to prioritize workshops and learning support.</Header>
    <State loading={cohort.isLoading} error={cohort.error}>
      {data?.status === 'cohort_suppressed' ? <Card><Empty>At least {data.minimum} students are required to show this cohort.</Empty></Card>
        : data && <><div className="metric-grid">
          <Card className="metric"><div className="metric-icon violet"><Users size={18} /></div><p>Assessed students</p><strong>{data.students}</strong></Card>
          <Card className="metric"><div className="metric-icon blue"><CircleGauge size={18} /></div><p>Mean readiness</p><strong>{scoreLabel(data.mean_score ?? 0)}%</strong></Card>
          <Card className="metric"><div className="metric-icon amber"><BarChart3 size={18} /></div><p>Below readiness threshold</p><strong>{data.support_candidates}</strong></Card>
          <Card className="metric"><div className="metric-icon mint"><BarChart3 size={18} /></div><p>Mean reassessment change</p>
            <strong>{data.mean_reassessment_change == null ? '—' : scoreLabel(data.mean_reassessment_change) + ' pts'}</strong></Card>
        </div>
          {demo && <Status kind="warn">Synthetic demonstration</Status>}
          <div className="grid-two"><Card title="Department readiness"><GroupTable data={data.departments ?? []} /></Card>
            <Card title="Role readiness"><GroupTable data={data.roles ?? []} /></Card></div>
          <Card title="Readiness by attempt">{data.trend?.length ? <div className="table-scroll"><table>
            <thead><tr><th>Attempt</th><th>Students</th><th>Mean score</th></tr></thead>
            <tbody>{data.trend.map(row => <tr key={row.attempt}><td>{row.attempt}</td><td>{row.students}</td>
              <td>{scoreLabel(row.mean_score)}%</td></tr>)}</tbody></table></div> :
              <Empty>No attempts meet the minimum cohort size.</Empty>}</Card></>}
    </State>
    <div className="grid-two">
      <Card title="Weak topics"><State loading={gaps.isLoading} error={gaps.error}>
        {gaps.data?.length ? <ul className="plain-list">{gaps.data.slice(0, 8).map(row =>
          <li key={row.topic_id}><strong>{row.topic}</strong> · {scoreLabel(row.weak_percent)}% below threshold</li>)}</ul>
          : <Empty>No reportable topics.</Empty>}
      </State></Card>
      <Card title="Recommended workshops"><State loading={proposals.isLoading} error={proposals.error}>
        {proposals.data?.length ? <ul className="plain-list">{proposals.data.map(row =>
          <li key={row.topic_id}><strong>{row.title}</strong> · priority {scoreLabel(row.priority)}</li>)}</ul>
          : <Empty>No recommendations for this cohort.</Empty>}
      </State></Card>
    </div>
  </>;
}
