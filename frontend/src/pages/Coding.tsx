import { useMutation, useQueryClient } from '@tanstack/react-query';
import { Code2, Play } from 'lucide-react';
import { useState } from 'react';
import { Button, Card, Empty, Header, State, Status, dateLabel } from '../components/ui';
import { useAPI } from '../hooks/queries';
import { api, json } from '../services/api';

type CodingProblem = { id: string; text: string; kind: string;
  settings: { seconds: number; memory_mb: number; function?: string; partial: boolean };
  samples: { inputs: Record<string, unknown>; expected: Record<string, unknown> }[] };
type Submission = { id: string; question_id: string; language: string; status: string; score: number | null; created_at: string; code?: string };

export function CodingPage() {
  const cache = useQueryClient();
  const [selected, setSelected] = useState('');
  const [code, setCode] = useState('');
  const problems = useAPI<CodingProblem[]>('/coding/questions');
  const history = useAPI<Submission[]>('/coding/submissions');
  const problem = problems.data?.find(q => q.id === selected) ?? problems.data?.[0];
  const save = useMutation({
    mutationFn: async (run: boolean) => {
      const result = await api<Submission>('/coding/submissions', json('POST', {
        question_id: problem?.id, language: 'python3', code,
      }));
      void cache.invalidateQueries({ queryKey: ['/coding/submissions'] });
      if (run) await api(`/coding/submissions/${result.id}/run-samples`, json('POST'));
      return result;
    },
  });
  const restore = useMutation({ mutationFn: (id: string) => api<Submission>(`/coding/submissions/${id}`),
    onSuccess: value => { setSelected(value.question_id); setCode(value.code ?? ''); } });
  return <><Header title="Python coding">Review public examples, write a solution, and save your submission.</Header>
    <State loading={problems.isLoading} error={problems.error}>
      {problem ? <div className="grid-two"><Card title="Problem">
        <label>Choose problem<select value={problem.id} onChange={e => { setSelected(e.target.value); setCode(''); }}>
          {problems.data?.map(q => <option key={q.id} value={q.id}>{q.text}</option>)}
        </select></label>
        <p>{problem.text}</p><div className="tag-list">
          <Status>{problem.kind === 'python_function' ? 'Function' : 'Standard input/output'}</Status>
          <Status>{problem.settings.seconds}s · {problem.settings.memory_mb} MB</Status>
          {problem.settings.partial && <Status>Partial scoring</Status>}
        </div>
        {problem.samples.map((sample, i) => <div className="code-example" key={i}><h3>Sample {i + 1}</h3>
          <pre>{JSON.stringify(sample.inputs, null, 2)}</pre><h3>Expected result</h3><pre>{JSON.stringify(sample.expected, null, 2)}</pre>
        </div>)}
      </Card><Card title="Editor" action={<Status><Code2 size={14} />Python 3</Status>}>
        <label>Solution<textarea className="code-editor" value={code} spellCheck={false}
          placeholder="# Write your Python 3 solution" rows={13} onChange={e => setCode(e.target.value)} maxLength={20000} /></label>
        <p className="muted">Execution is unavailable until a verified isolated worker is configured.</p>
        <div className="inline-form"><Button variant="outline" disabled={!code.trim() || save.isPending}
          onClick={() => save.mutate(true)}><Play size={15} />Run samples</Button>
          <Button disabled={!code.trim() || save.isPending} onClick={() => save.mutate(false)}>Submit solution</Button></div>
        {save.isSuccess && <p className="feedback" role="status">Submission saved. Evaluation is disabled.</p>}
        <State error={save.error ?? restore.error} />
      </Card></div> : <Card><Empty>No approved Python problems are available.</Empty></Card>}
    </State>
    <Card title="Submission history"><State loading={history.isLoading} error={history.error}>
      {!history.data?.length ? <Empty>No submissions yet.</Empty> : <div className="rows">{history.data.map(item =>
        <button className="row" key={item.id} type="button" onClick={() => restore.mutate(item.id)}>
          <div><strong>{item.question_id}</strong><small>{dateLabel(item.created_at)}</small></div>
          <Status>{item.status.replaceAll('_', ' ')}</Status>
        </button>)}</div>}
    </State></Card>
  </>;
}
