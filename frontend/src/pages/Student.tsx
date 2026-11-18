import { useMutation, useQueryClient } from '@tanstack/react-query';
import { ArrowRight, Briefcase, CalendarDays, ClipboardCheck, Sparkles } from 'lucide-react';
import { useState } from 'react';
import { Link } from 'react-router';
import { Metrics, ProgressPanels } from '../components/Progress';
import { Button, Card, Empty, Header, State, Status, dateLabel, scoreLabel } from '../components/ui';
import { useAPI } from '../hooks/queries';
import { api, json } from '../services/api';
import type { Item, Predictions, Progress, RoadmapResult, Student, User } from '../types/api';

export function StudentHome({ user }: { user: User }) {
  const student = useAPI<Student>('/students/me');
  const progress = useAPI<Progress>('/students/me/progress');
  const predictions = useAPI<Predictions>('/students/me/predictions');
  const roadmap = useAPI<RoadmapResult>('/students/me/roadmap');
  return <><Header title={`Hi, ${user.display_name.split(' ')[0]}`} aside={
    <Button asChild variant="outline"><Link to="/career"><Briefcase size={16} />Career role</Link></Button>}>
    Track your progress and plan your next assessment.</Header>
    <State loading={student.isLoading || progress.isLoading} error={student.error ?? progress.error}>
      {student.data && progress.data && <>
        <div className="student-hero">
          <div className="hero-content"><div className="hero-context"><ClipboardCheck size={17} /> Readiness check-in</div>
            <h2>{student.data.career_role?.name ?? 'Choose your target role'}</h2>
            <p>{student.data.career_role ? 'Take a standardized assessment to measure the skills that matter for your role.'
              : 'A target role gives your assessments and study roadmap a clear focus.'}</p>
            <Button asChild><Link to={student.data.career_role ? '/assessments' : '/career'}>
              {student.data.career_role ? 'Go to assessments' : 'Choose a role'}<ArrowRight size={16} /></Link></Button>
          </div><div className="hero-decoration" aria-hidden="true"><i /><i /><i /></div>
        </div>
        {student.data.synthetic && <div className="demo-notice"><Status kind="warn">Synthetic demonstration</Status></div>}
        <Metrics latest={progress.data.latest} predictions={predictions.data} count={progress.data.history.length} />
        <State error={predictions.error} />
        <ProgressPanels history={progress.data.history} topics={progress.data.topics} />
        <div className="grid-two">
          <Card title="Learning roadmap" action={<Sparkles size={18} className="accent" />}>
            <p className="muted">{roadmap.data?.roadmap
              ? `${roadmap.data.roadmap.duration_weeks} weeks · ${roadmap.data.roadmap.tasks.filter(t => t.completed).length} tasks complete`
              : 'A roadmap becomes available after your first assessment.'}</p>
            <Button asChild variant="ghost"><Link to="/roadmap">View roadmap <ArrowRight size={15} /></Link></Button>
          </Card>
          <Card title="Latest assessment" action={<CalendarDays className="accent" size={18} />}>
            <p className="muted">{progress.data.latest
              ? `${dateLabel(progress.data.latest.date)} · ${scoreLabel(progress.data.latest.score)}% readiness`
              : 'No assessments available.'}</p>
            <Button asChild variant="ghost"><Link to="/assessments">Assessment history <ArrowRight size={15} /></Link></Button>
          </Card>
        </div>
      </>}
    </State>
  </>;
}

export function CareerPage() {
  const query = useQueryClient();
  const roles = useAPI<Item[]>('/roles');
  const profile = useAPI<Student>('/students/me');
  const [role, setRole] = useState<string | null>(null);
  const selected = role ?? profile.data?.career_role?.id ?? '';
  const skills = useAPI<(Item & { weight: number; version: string })[]>(`/roles/${selected}/skills`, Boolean(selected));
  const save = useMutation({ mutationFn: () => api<Student>('/students/me/role', json('PUT', { role_id: selected })),
    onSuccess: data => query.setQueryData(['/students/me'], data) });
  return <><Header title="Career role">Choose the role you’re preparing for.</Header>
    <State loading={roles.isLoading || profile.isLoading} error={roles.error ?? profile.error}>
      <Card title="Target role"><form className="inline-form" onSubmit={e => { e.preventDefault(); save.mutate(); }}>
        <label>Career role<select aria-label="Career role" value={selected} onChange={e => setRole(e.target.value)}>
          <option value="">Choose a role</option>
          {roles.data?.map(item => <option value={item.id} key={item.id}>{item.name}</option>)}
        </select></label>
        <Button disabled={!selected || save.isPending} type="submit">Save role</Button></form>
        <State error={save.error} />{save.isSuccess && <p className="feedback" role="status">Career role saved.</p>}
      </Card>
    </State>
    {selected && <Card title="Role skill relevance"><State loading={skills.isLoading} error={skills.error}>
      <div className="tag-list">{skills.data?.map(skill => <Status key={skill.id} kind={skill.weight === 1 ? 'good' : 'neutral'}>
        {skill.name} · {skill.weight === 1 ? 'High' : skill.weight === .6 ? 'Medium' : 'Low'}
      </Status>)}</div>
    </State></Card>}
  </>;
}

export function RoadmapPage() {
  const cache = useQueryClient();
  const plan = useAPI<RoadmapResult>('/students/me/roadmap');
  const [hours, setHours] = useState(5);
  const generate = useMutation({
    mutationFn: () => api<RoadmapResult>('/students/me/roadmap', json('POST', { weekly_hours: hours })),
    onSuccess: result => cache.setQueryData(['/students/me/roadmap'], result),
  });
  const check = useMutation({
    mutationFn: ({ id, completed }: { id: string; completed: boolean }) =>
      api(`/students/me/roadmap/tasks/${id}`, json('PATCH', { completed })),
    onSuccess: () => cache.invalidateQueries({ queryKey: ['/students/me/roadmap'] }),
  });
  const roadmap = plan.data?.roadmap;
  return <><Header title="Learning roadmap">Work through your highest-priority skills and prepare for reassessment.</Header>
    <Card><form className="inline-form" onSubmit={e => { e.preventDefault(); generate.mutate(); }}>
      <label>Study hours per week<input type="number" min="1" max="40" value={hours} onChange={e => setHours(e.target.valueAsNumber)} required /></label>
      <Button disabled={generate.isPending} type="submit"><Sparkles size={16} />
        {generate.isPending ? 'Generating…' : roadmap ? 'Update roadmap' : 'Generate roadmap'}</Button>
    </form><State error={generate.error ?? check.error} />
      {generate.data?.status === 'fallback' && <p role="status" className="muted">OpenAI roadmap unavailable. Your rule-based plan is ready.</p>}
    </Card>
    <State loading={plan.isLoading} error={plan.error}>
      {!roadmap ? <Card><Empty>No roadmap yet. Complete a standardized assessment to get a study plan.</Empty></Card> : <>
        <Card title={roadmap.target_role} action={<Status kind={plan.data?.status === 'openai' ? 'good' : 'neutral'}>
          {plan.data?.status === 'openai' ? 'OpenAI roadmap' : 'Rule-based roadmap'}</Status>}>
          <p>{roadmap.explanation}</p><div className="tag-list">{roadmap.priority_skills.map(skill => <Status key={skill}>{skill}</Status>)}</div>
        </Card>
        {roadmap.weekly_plan.map(week => <Card key={week.week} title={`Week ${week.week} · ${week.focus}`} action={<Status>{week.hours} hours</Status>}>
          <div className="check-list">{roadmap.tasks.filter(task => task.week === week.week).map(task =>
            <label key={task.id}><input type="checkbox" checked={task.completed} disabled={check.isPending}
              onChange={e => check.mutate({ id: task.id, completed: e.target.checked })} />{task.title}</label>)}</div>
        </Card>)}
        <div className="grid-two"><Card title="Learning resources"><ul className="plain-list">{roadmap.resources.map(resource =>
          <li key={resource.id}><a href={resource.url} target="_blank" rel="noreferrer">{resource.title}</a></li>)}</ul></Card>
          <Card title="Practice & reassessment"><ul className="plain-list">
            {[...roadmap.practice_tasks, ...roadmap.reassessment_milestones].map((message, i) => <li key={i}>{message}</li>)}
          </ul><Button asChild variant="outline"><Link to="/assessments">Schedule a reassessment</Link></Button></Card></div>
      </>}
    </State>
  </>;
}
