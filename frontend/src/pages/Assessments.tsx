import { useMutation, useQueryClient } from '@tanstack/react-query';
import { ArrowRight, CalendarClock, ClipboardList } from 'lucide-react';
import { useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router';
import { SkillScores } from '../components/Progress';
import { Button, Card, Empty, Header, State, Status, dateLabel, scoreLabel } from '../components/ui';
import { useAPI } from '../hooks/queries';
import { api, json } from '../services/api';
import type { AssessmentListItem, Exam, Item, Question, Result } from '../types/api';

export function QuestionChoices({ question, selected, onSelect, disabled = false }:
  { question: Question; selected?: string | null; onSelect: (value: string) => void; disabled?: boolean }) {
  return <fieldset className="question"><legend>{question.text}</legend>
    {question.options.map(option => <label key={option.label} className={selected === option.label ? 'picked' : ''}>
      <input type="radio" name={question.id} value={option.label} checked={selected === option.label}
        disabled={disabled} onChange={() => onSelect(option.label)} /><span>{option.label}</span><b>{option.text}</b>
    </label>)}</fieldset>;
}

export function AssessmentsPage() {
  const navigate = useNavigate();
  const cache = useQueryClient();
  const history = useAPI<AssessmentListItem[]>('/assessments');
  const [date, setDate] = useState('');
  const start = useMutation({ mutationFn: (value: string | null) =>
    api<Exam>('/assessments', json('POST', value ? { scheduled_at: new Date(value).toISOString() } : {})),
  onSuccess: item => {
    void cache.invalidateQueries({ queryKey: ['/assessments'] });
    void navigate(`/assessments/${item.id}`);
  } });

  return <><Header title="Assessments">Compare your readiness across standardized attempts.</Header>
    <div className="grid-two">
      <Card title="Standardized assessment"><p className="muted">Questions follow a fixed topic and difficulty blueprint for your target role.</p>
        <Button disabled={start.isPending} onClick={() => start.mutate(null)}><ClipboardList size={16} />Start assessment</Button></Card>
      <Card title="Schedule a reassessment"><form className="inline-form" onSubmit={e => { e.preventDefault(); start.mutate(date); }}>
        <label>Date and time<input type="datetime-local" required value={date} onChange={e => setDate(e.target.value)} /></label>
        <Button disabled={start.isPending} type="submit" variant="outline"><CalendarClock size={16} />Schedule</Button>
      </form></Card>
    </div>
    <State error={start.error} />
    <Card title="Your assessments"><State loading={history.isLoading} error={history.error}>
      {!history.data?.length ? <Empty>No assessments available.</Empty> :
        <div className="rows">{history.data.map((item) => <Link key={item.id} to={`/assessments/${item.id}`} className="row">
          <div><strong>Assessment {item.attempt}</strong><small>{item.taken_at || item.scheduled_at ? dateLabel((item.taken_at ?? item.scheduled_at)!) : 'Started'}</small></div>
          <div className="row-action"><Status kind={item.status === 'submitted' ? 'good' : 'neutral'}>{item.status}</Status><ArrowRight size={16} /></div>
        </Link>)}</div>}</State></Card>
  </>;
}

export function AssessmentPage() {
  const id = useParams().id!;
  const path = `/assessments/${id}`;
  const cache = useQueryClient();
  const current = useAPI<Exam>(path);
  const [pendingAnswer, setPendingAnswer] = useState<{ question_id: string; option: string } | null>(null);
  const result = useAPI<Result>(path + '/results', current.data?.status === 'submitted');
  const setExam = (value: Exam) => cache.setQueryData([path], value);
  const activate = useMutation({ mutationFn: () => api<Exam>(path + '/activate', json('POST')), onSuccess: setExam });
  const answer = useMutation({
    mutationFn: (input: { question_id: string; option: string }) => api(path + '/responses', json('POST', input)),
    onSuccess: (_, data) => cache.setQueryData<Exam>([path], old => old && ({
      ...old, questions: old.questions.map(q => q.id === data.question_id ? { ...q, selected: data.option } : q),
    })),
    onSettled: () => setPendingAnswer(null),
  });
  const submit = useMutation({ mutationFn: () => api<Result>(path + '/submit', json('POST')),
    onSuccess: data => {
      cache.setQueryData([path + '/results'], data);
      if (current.data) setExam({ ...current.data, status: 'submitted' });
      for (const key of ['/assessments', '/students/me/progress', '/students/me/predictions', '/students/me/roadmap']) {
        void cache.invalidateQueries({ queryKey: [key] });
      }
    } });
  return <><Header title={current.data ? `Assessment ${current.data.attempt}` : 'Standardized assessment'}
    aside={<Button asChild variant="outline"><Link to="/assessments">All assessments</Link></Button>}>
    Your responses are saved as you answer.</Header>
    <State loading={current.isLoading} error={current.error}>
      {current.data?.status === 'scheduled' && <Card title="Scheduled reassessment">
        <p className="muted">Available {current.data.scheduled_at && dateLabel(current.data.scheduled_at)}.</p>
        <Button onClick={() => activate.mutate()} disabled={activate.isPending}>Open reassessment</Button>
      </Card>}
      {current.data?.status === 'open' && <Card title="Questions" action={<Status>
        {current.data.questions.filter(q => q.selected).length} / {current.data.questions.length} answered</Status>}>
        {current.data.questions.map(q => <QuestionChoices key={q.id} question={q} selected={pendingAnswer?.question_id === q.id ? pendingAnswer.option : q.selected}
          disabled={answer.isPending || submit.isPending}
          onSelect={option => {
            const choice = { question_id: q.id, option };
            setPendingAnswer(choice);
            answer.mutate(choice);
          }} />)}
        <Button onClick={() => submit.mutate()} disabled={answer.isPending || submit.isPending || !current.data.questions.some(q => q.selected)}>
          Submit assessment<ArrowRight size={16} /></Button>
        <p className="muted">Unanswered questions receive zero points.</p>
      </Card>}
      {current.data?.status === 'submitted' && <State loading={result.isLoading} error={result.error}>
        {result.data && <><Card title="Readiness result"><div className="result-score">
          {result.data.readiness === null ? '—' : scoreLabel(result.data.readiness) + '%'}</div>
          <p className="muted">The readiness threshold is {result.data.threshold}%. {result.data.coverage?.answered_questions} of{' '}
            {result.data.coverage?.assigned_questions} questions answered. {result.data.coverage?.unassessed.length} topics were outside this blueprint.</p>
          <Button asChild><Link to="/roadmap">View learning roadmap<ArrowRight size={16} /></Link></Button>
        </Card><Card title="Topic results"><SkillScores topics={result.data.topics} /></Card></>}
      </State>}
    </State>
    <State error={activate.error ?? answer.error ?? submit.error} />
  </>;
}

type NextQuestion = { status: string; question: Question | null };

export function PracticePage() {
  const [session, setSession] = useState<Exam | null>(null);
  const [company, setCompany] = useState('');
  const [selected, setSelected] = useState<string>();
  const [feedback, setFeedback] = useState<{ correct: boolean; status: string } | null>(null);
  const cache = useQueryClient();
  const companies = useAPI<Item[]>('/companies');
  const path = `/practice/${session?.id ?? ''}/next-question`;
  const question = useAPI<NextQuestion>(path, Boolean(session));
  const start = useMutation({ mutationFn: () => api<Exam>('/practice/start', json('POST', {
    company_id: company || null, max_questions: 5,
  })), onSuccess: value => { setSession(value); setFeedback(null); setSelected(undefined); } });
  const answer = useMutation({ mutationFn: () => api<{ correct: boolean; status: string }>(
    `/practice/${session?.id}/responses`, json('POST', { question_id: question.data?.question?.id, option: selected })
  ), onSuccess: value => setFeedback(value) });
  return <><Header title="Adaptive practice">Practice weak skills at an appropriate difficulty. These results stay separate from standardized readiness.</Header>
    {!session && <Card title="Start a practice session"><form className="inline-form" onSubmit={e => { e.preventDefault(); start.mutate(); }}>
      <label>Company focus<select value={company} onChange={e => setCompany(e.target.value)}>
        <option value="">All practice questions</option>{companies.data?.map(c => <option value={c.id} key={c.id}>{c.name}</option>)}
      </select></label><Button disabled={start.isPending} type="submit">Start practice<ArrowRight size={16} /></Button>
    </form><State error={companies.error} /></Card>}
    {session && <Card title="Practice questions">
      {(feedback?.status === 'complete' || question.data?.status === 'complete') ?
        <><Empty>Practice complete.</Empty><Button onClick={() => { setSession(null); setFeedback(null); }}>Start another session</Button></> :
        <State loading={question.isLoading || question.isFetching} error={question.error}>
          {question.data?.question && <>
            <QuestionChoices question={question.data.question} selected={selected} onSelect={setSelected}
              disabled={Boolean(feedback) || answer.isPending} />
            {feedback ? <div className="inline-form">
              <Status kind={feedback.correct ? 'good' : 'warn'}>{feedback.correct ? 'Correct' : 'Incorrect'}</Status>
              <Button onClick={() => {
                setSelected(undefined); setFeedback(null); void cache.invalidateQueries({ queryKey: [path] });
              }}>Next question <ArrowRight size={16} /></Button>
            </div> : <Button disabled={!selected || answer.isPending} onClick={() => answer.mutate()}>Check answer</Button>}
          </>}
        </State>}
    </Card>}
    <State error={start.error ?? answer.error} />
  </>;
}
