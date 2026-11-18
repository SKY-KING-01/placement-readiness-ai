import { useMutation, useQueryClient } from '@tanstack/react-query';
import { ArrowRight, FileUp, Plus } from 'lucide-react';
import { useState, type FormEvent } from 'react';
import { Button, Card, Empty, Header, State, Status } from '../components/ui';
import { useAPI } from '../hooks/queries';
import { api, json } from '../services/api';
import type { Item, User } from '../types/api';

type Case = { public: boolean; inputs: Record<string, unknown>; expected: Record<string, unknown>; weight: number };
type RecordQuestion = {
  id: string; text: string; kind: string; category: string; difficulty: string; topic_id: string;
  subtopic_id: string | null; skill_id: string | null; role_id: string | null; company_ids: string[];
  year: number | null; placement_round: string | null; source_url: string | null; verification: string;
  explanation: string | null; status: string; active: boolean; options: string[]; answer: number | null; cases: Case[];
  function?: string; seconds?: number; memory_mb?: number; partial?: boolean;
};
type ImportReport = { valid: number; invalid: number; issues: { row: number; issues: string[] }[]; preview: boolean };
type Taxonomy = { topics: Item[]; subtopics: (Item & { topic_id: string })[]; skills: (Item & { topic_id: string })[] };
type Account = User & { active: boolean; student_id?: string };
type Model = { model_id: string; task: string; algorithm: string; feature_version: string; held_out: number };
const categories = ['aptitude', 'sql', 'technical', 'python', 'reasoning', 'soft skills'];

function inputs(event: FormEvent<HTMLFormElement>) {
  event.preventDefault();
  return new FormData(event.currentTarget);
}

function QuestionEditor({ current, onClose }: { current?: RecordQuestion; onClose: () => void }) {
  const cache = useQueryClient();
  const [topic, setTopic] = useState(current?.topic_id ?? '');
  const [kind, setKind] = useState(current?.kind ?? 'mcq');
  const catalog = useAPI<Taxonomy>('/admin/catalog');
  const roles = useAPI<Item[]>('/roles');
  const companies = useAPI<Item[]>('/companies');
  const save = useMutation({
    mutationFn: (form: FormData) => {
      const value = (key: string) => String(form.get(key) ?? '').trim();
      const optional = (key: string) => value(key) || null;
      const options = [value('a'), value('b'), value('c'), value('d')];
      while (options.length && !options.at(-1)) options.pop();
      let cases: unknown = [];
      if (kind !== 'mcq') {
        try { cases = JSON.parse(value('cases')); }
        catch { throw new Error('Coding test cases must be valid JSON.'); }
      }
      const payload = {
        text: value('text'), kind, category: value('category'), difficulty: value('difficulty'), topic_id: topic,
        subtopic_id: optional('subtopic_id'), skill_id: optional('skill_id'), role_id: optional('role_id'),
        company_ids: form.getAll('company_ids'), year: value('year') ? Number(value('year')) : null,
        placement_round: optional('placement_round'), source_url: optional('source_url'),
        verification: value('verification'), explanation: optional('explanation'), active: form.has('active'),
        options: kind === 'mcq' ? options : [], answer: kind === 'mcq' ? Number(value('answer')) : null,
        cases, function: kind === 'python_function' ? optional('function') : null,
        seconds: Number(value('seconds')) || 2, memory_mb: Number(value('memory_mb')) || 128,
        partial: form.has('partial'),
      };
      return api(current ? `/admin/questions/${current.id}` : '/admin/questions', json(current ? 'PATCH' : 'POST', payload));
    },
    onSuccess: () => { void cache.invalidateQueries({ predicate: q => String(q.queryKey[0]).startsWith('/admin/questions?') }); onClose(); },
  });
  return <Card title={current ? 'Edit question' : 'Add question'} action={<Button variant="ghost" onClick={onClose}>Close</Button>}>
    <form className="editor-form" onSubmit={event => save.mutate(inputs(event))}>
      <label className="wide">Question text<textarea name="text" required maxLength={10000} defaultValue={current?.text} /></label>
      <label>Type<select value={kind} onChange={e => setKind(e.target.value)}>
        <option value="mcq">Multiple choice</option><option value="python_io">Python input/output</option>
        <option value="python_function">Python function</option></select></label>
      <label>Category<select name="category" required defaultValue={current?.category ?? 'technical'}>
        {categories.map(item => <option key={item}>{item}</option>)}</select></label>
      <label>Difficulty<select name="difficulty" defaultValue={current?.difficulty ?? 'easy'}>
        {['easy', 'medium', 'hard'].map(item => <option key={item}>{item}</option>)}</select></label>
      <label>Topic<select required value={topic} onChange={e => setTopic(e.target.value)}>
        <option value="">Pick a topic</option>{catalog.data?.topics.map(item => <option value={item.id} key={item.id}>{item.name}</option>)}
      </select></label>
      <label>Subtopic<select name="subtopic_id" required={kind === 'mcq'} key={topic} defaultValue={current?.subtopic_id ?? ''}>
        <option value="">Pick a subtopic</option>{catalog.data?.subtopics.filter(item => item.topic_id === topic)
          .map(item => <option value={item.id} key={item.id}>{item.name}</option>)}</select></label>
      <label>Skill<select name="skill_id" key={'skill-' + topic} defaultValue={current?.skill_id ?? ''}>
        <option value="">Any skill</option>{catalog.data?.skills.filter(item => item.topic_id === topic)
          .map(item => <option value={item.id} key={item.id}>{item.name}</option>)}</select></label>
      <label>Target role<select name="role_id" defaultValue={current?.role_id ?? ''}>
        <option value="">Any role</option>{roles.data?.map(item => <option value={item.id} key={item.id}>{item.name}</option>)}</select></label>
      <label>Companies<select name="company_ids" multiple defaultValue={current?.company_ids ?? []}>
        {companies.data?.map(item => <option value={item.id} key={item.id}>{item.name}</option>)}</select></label>
      <label>Reported year<input name="year" type="number" min="1900" max="2100" defaultValue={current?.year ?? ''} /></label>
      <label>Placement round<input name="placement_round" maxLength={100} defaultValue={current?.placement_round ?? ''} /></label>
      <label>Verification<select name="verification" defaultValue={current?.verification ?? 'practice'}>
        <option value="practice">Company-style practice</option><option value="verified">Source verified by reviewer</option></select></label>
      <label>Source URL<input name="source_url" type="url" defaultValue={current?.source_url ?? ''} /></label>
      {kind === 'mcq' ? <>
        {['a', 'b', 'c', 'd'].map((letter, index) => <label key={letter}>Option {letter.toUpperCase()}
          <input name={letter} required={index < 2} defaultValue={current?.options[index]} maxLength={3000} /></label>)}
        <label>Correct option<select name="answer" defaultValue={current?.answer ?? 0}>
          {['A', 'B', 'C', 'D'].map((letter, index) => <option value={index} key={letter}>{letter}</option>)}</select></label>
      </> : <>
        {kind === 'python_function' && <label>Function name<input name="function" required defaultValue={current?.function} /></label>}
        <label>Time limit in seconds<input name="seconds" type="number" min="1" max="10" defaultValue={current?.seconds ?? 2} /></label>
        <label>Memory limit in MB<input name="memory_mb" type="number" min="32" max="512" defaultValue={current?.memory_mb ?? 128} /></label>
        <label className="checkbox-label"><input type="checkbox" name="partial" defaultChecked={current?.partial} />Allow partial credit</label>
        <label className="wide">Cases as JSON <small>Include at least one public and one hidden test case.</small>
          <textarea name="cases" className="code-editor" required rows={6} defaultValue={JSON.stringify(current?.cases ?? [], null, 2)} /></label>
      </>}
      <label className="wide">Explanation<textarea name="explanation" defaultValue={current?.explanation ?? ''} /></label>
      <label className="checkbox-label"><input type="checkbox" name="active" defaultChecked={current?.active ?? true} />Active</label>
      <div className="wide"><Button disabled={save.isPending} type="submit">Save for review</Button>
        <State error={save.error ?? catalog.error ?? roles.error ?? companies.error} /></div>
    </form>
  </Card>;
}

function QuestionsAdmin() {
  const cache = useQueryClient();
  const [page, setPage] = useState(0);
  const [search, setSearch] = useState('');
  const [status, setStatus] = useState('');
  const [editing, setEditing] = useState<RecordQuestion | 'new' | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const query = `/admin/questions?limit=20&offset=${page * 20}&q=${encodeURIComponent(search)}&status=${status}`;
  const questions = useAPI<RecordQuestion[]>(query);
  const refresh = () => cache.invalidateQueries({ predicate: key => String(key.queryKey[0]).startsWith('/admin/questions?') });
  const mutate = useMutation({ mutationFn: ({ id, action }: { id: string; action: string }) =>
    api(`/admin/questions/${id}/${action}`, json('POST')), onSuccess: refresh });
  const upload = useMutation({ mutationFn: (preview: boolean) => {
    const body = new FormData(); if (file) body.append('file', file);
    return api<ImportReport>('/admin/questions/import?preview=' + preview, { method: 'POST', body });
  }, onSuccess: refresh });
  return <>
    <Card title="Question bank" action={<Button onClick={() => setEditing('new')}><Plus size={16} />Add question</Button>}>
      <div className="inline-form"><label>Search<input value={search} onChange={e => { setSearch(e.target.value); setPage(0); }} /></label>
        <label>Status<select value={status} onChange={e => { setStatus(e.target.value); setPage(0); }}>
          <option value="">All statuses</option>{['pending', 'approved', 'quarantined'].map(item => <option key={item}>{item}</option>)}</select></label></div>
      <State loading={questions.isLoading} error={questions.error ?? mutate.error}>
        {questions.data?.length ? <div className="rows">{questions.data.map(item => <div className="row" key={item.id}>
          <div><strong>{item.text}</strong><small>{item.category} · {item.difficulty} · {item.verification}</small></div>
          <div className="row-action">
            <Status kind={item.status === 'approved' && item.active ? 'good' : 'neutral'}>{item.active ? item.status : 'inactive'}</Status>
            <Button variant="ghost" onClick={() => setEditing(item)}>Edit</Button>
            {item.active && item.status === 'pending' && <Button variant="outline" disabled={mutate.isPending}
              onClick={() => mutate.mutate({ id: item.id, action: 'approve' })}>Approve</Button>}
            {item.active && <Button variant="danger" disabled={mutate.isPending}
              onClick={() => mutate.mutate({ id: item.id, action: 'deactivate' })}>Deactivate</Button>}
          </div></div>)}</div> : <Empty>No matching questions.</Empty>}
        <div className="inline-form"><Button variant="outline" disabled={!page} onClick={() => setPage(p => p - 1)}>Previous</Button>
          <Button variant="outline" disabled={(questions.data?.length ?? 0) < 20} onClick={() => setPage(p => p + 1)}>Next<ArrowRight size={15} /></Button></div>
      </State>
    </Card>
    {editing && <QuestionEditor key={editing === 'new' ? 'new' : editing.id} current={editing === 'new' ? undefined : editing}
      onClose={() => { setEditing(null); void refresh(); }} />}
    <Card title="Import CSV or Excel">
      <p className="muted">Use the documented MCQ headers with topic and subtopic IDs. Rows require approval after import.</p>
      <div className="inline-form"><label>Question file<input type="file" accept=".csv,.xlsx"
        onChange={e => { setFile(e.target.files?.[0] ?? null); upload.reset(); }} /></label>
        <Button disabled={!file || upload.isPending} variant="outline" onClick={() => upload.mutate(true)}><FileUp size={16} />Preview</Button>
        <Button disabled={!file || upload.isPending || !upload.data?.preview || !upload.data.valid} onClick={() => upload.mutate(false)}>Import valid rows</Button>
      </div><State error={upload.error} />{upload.data && <>
        <p role="status">{upload.data.valid} valid · {upload.data.invalid} invalid{upload.data.preview ? ' · Preview' : ' · Saved for approval'}</p>
        {upload.data.issues.length > 0 && <ul className="plain-list">{upload.data.issues.map(row =>
          <li key={row.row}>Row {row.row} — {row.issues.join(' ')}</li>)}</ul>}
      </>}
    </Card>
  </>;
}

function AccountsAdmin() {
  const cache = useQueryClient();
  const [page, setPage] = useState(0);
  const accounts = useAPI<Account[]>(`/admin/users?limit=15&offset=${page * 15}`);
  const save = useMutation({ mutationFn: (values: { id: string; role: string; active: boolean }) =>
    api(`/admin/users/${values.id}`, json('PATCH', { role: values.role, active: values.active })),
  onSuccess: () => cache.invalidateQueries({ predicate: q => String(q.queryKey[0]).startsWith('/admin/users?') }) });
  const assign = useMutation({ mutationFn: (values: FormData) =>
    api('/admin/trainer-assignments', json('POST', Object.fromEntries(values))) });
  return <><Card title="Accounts"><State loading={accounts.isLoading} error={accounts.error ?? save.error}>
    <div className="rows">{accounts.data?.map(item => <form key={item.id} className="row" onSubmit={e => {
      const values = inputs(e); save.mutate({ id: item.id, role: String(values.get('role')), active: values.has('active') });
    }}>
      <div><strong>{item.display_name}</strong><small>{item.email} · {item.student_id ? 'Student ID ' + item.student_id : 'User ID ' + item.id}</small></div>
      <div className="row-action"><label>Role<select name="role" defaultValue={item.role}>
        {['student', 'trainer', 'placement', 'admin'].map(value => <option key={value}>{value}</option>)}</select></label>
        <label className="checkbox-label"><input type="checkbox" name="active" defaultChecked={item.active} />Active</label>
        <Button type="submit" variant="outline" disabled={save.isPending}>Save</Button></div>
    </form>)}</div>
    <div className="inline-form"><Button variant="outline" disabled={!page} onClick={() => setPage(n => n - 1)}>Previous</Button>
      <Button variant="outline" disabled={(accounts.data?.length ?? 0) < 15} onClick={() => setPage(n => n + 1)}>Next</Button></div>
  </State></Card>
  <Card title="Trainer assignments"><form className="inline-form" onSubmit={e => assign.mutate(inputs(e))}>
    <label>Trainer user ID<input name="user_id" required /></label><label>Student ID<input name="student_id" required /></label>
    <Button type="submit" disabled={assign.isPending}>Assign</Button>
  </form><State error={assign.error} />{assign.isSuccess && <p role="status">Assignment saved.</p>}</Card></>;
}

function CatalogAdmin() {
  const cache = useQueryClient();
  const companies = useAPI<Item[]>('/companies');
  const roles = useAPI<(Item & { active: boolean })[]>('/admin/roles');
  const models = useAPI<Model[]>('/admin/model-versions');
  const [role, setRole] = useState('');
  const skills = useAPI<(Item & { weight: number; version: string })[]>(`/roles/${role}/skills`, Boolean(role));
  const create = useMutation({ mutationFn: ({ path, form }: { path: string; form: FormData }) =>
    api('/admin' + path, json('POST', Object.fromEntries(form))),
  onSuccess: (_, values) => cache.invalidateQueries({ queryKey: [values.path === '/roles' ? '/admin/roles' : values.path] }) });
  const edit = useMutation({ mutationFn: ({ path, body }: { path: string; body: unknown }) =>
    api(path, json('PATCH', body)),
  onSuccess: () => cache.invalidateQueries({ predicate: q => ['/companies', '/roles', '/admin/roles'].includes(String(q.queryKey[0])) }) });
  const weights = useMutation({ mutationFn: (form: FormData) => api(`/admin/roles/${role}/weights`, json('PATCH', {
    skill_id: form.get('skill_id'), weight: Number(form.get('weight')),
  })), onSuccess: () => cache.invalidateQueries({ queryKey: [`/roles/${role}/skills`] }) });
  return <>
    <div className="grid-two">
      <Card title="Career roles"><form className="inline-form" onSubmit={e => create.mutate({ path: '/roles', form: inputs(e) })}>
        <label>Name<input name="name" required minLength={2} maxLength={120} /></label>
        <Button type="submit" variant="outline" disabled={create.isPending}>Add role</Button>
      </form><div className="rows">{roles.data?.map(item => <div className="row" key={item.id}>
        <div><strong>{item.name}</strong><small>{item.active ? 'Active' : 'Inactive'}</small></div>
        <Button variant="outline" disabled={edit.isPending} onClick={() => edit.mutate({
          path: `/admin/roles/${item.id}`, body: { active: !item.active },
        })}>{item.active ? 'Deactivate' : 'Activate'}</Button>
      </div>)}</div></Card>
      <Card title="Companies"><form className="inline-form" onSubmit={e => create.mutate({ path: '/companies', form: inputs(e) })}>
        <label>Name<input name="name" required minLength={2} maxLength={120} /></label>
        <Button type="submit" variant="outline" disabled={create.isPending}>Add company</Button>
      </form><div className="rows">{companies.data?.map(item => <form className="row" key={item.id}
        onSubmit={e => edit.mutate({ path: `/admin/companies/${item.id}`, body: Object.fromEntries(inputs(e)) })}>
        <label>Company name<input name="name" required minLength={2} maxLength={120} defaultValue={item.name} /></label>
        <Button type="submit" variant="outline" disabled={edit.isPending}>Rename</Button>
      </form>)}</div></Card>
    </div>
    <State error={create.error ?? edit.error ?? companies.error ?? roles.error} />
    <Card title="Version a skill weight"><form className="inline-form" onSubmit={e => weights.mutate(inputs(e))}>
      <label>Role<select value={role} onChange={e => setRole(e.target.value)} required>
        <option value="">Choose role</option>{roles.data?.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
      <label>Skill<select name="skill_id" required><option value="">Choose skill</option>{skills.data?.map(item =>
        <option key={item.id} value={item.id}>{item.name} ({item.weight})</option>)}</select></label>
      <label>Weight<select name="weight" defaultValue=".6"><option value=".3">Low · 0.3</option>
        <option value=".6">Medium · 0.6</option><option value="1">High · 1.0</option></select></label>
      <Button type="submit" disabled={!role || weights.isPending}>Save new version</Button>
    </form><State error={weights.error ?? skills.error} />{weights.isSuccess && <p role="status">Role weight version saved.</p>}</Card>
    <Card title="Model versions"><State loading={models.isLoading} error={models.error}>
      {models.data?.length ? <div className="rows">{models.data.map(model => <div className="row" key={model.model_id}>
        <div><strong>{model.algorithm} · {model.task}</strong><small>{model.model_id.slice(0, 12)} · {model.feature_version}</small></div>
        <Status kind="warn">Synthetic · {model.held_out} test rows</Status>
      </div>)}</div> : <Empty>No compatible trained artifacts are available.</Empty>}
    </State></Card>
  </>;
}

export function AdminPage() {
  const [tab, setTab] = useState<'questions' | 'accounts' | 'catalog'>('questions');
  return <><Header title="Administration">Manage the question bank, accounts, career catalog and model versions.</Header>
    <div className="tabs" aria-label="Administration sections">
      {([{ key: 'questions', title: 'Question bank' }, { key: 'accounts', title: 'Accounts' },
         { key: 'catalog', title: 'Catalog & models' }] as const).map(item =>
        <Button key={item.key} variant={tab === item.key ? 'primary' : 'outline'} aria-pressed={tab === item.key}
          onClick={() => setTab(item.key)}>{item.title}</Button>)}
    </div>
    {tab === 'questions' ? <QuestionsAdmin /> : tab === 'accounts' ? <AccountsAdmin /> : <CatalogAdmin />}
  </>;
}
