import { Activity, AlignLeft as Bars3BottomLeft, Brain, TrendingUp } from 'lucide-react';
import { Area, AreaChart, CartesianGrid, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { Card, Empty, Status, dateLabel, scoreLabel } from './ui';
import type { History, Predictions, Topic } from '../types/api';

export function HistoryChart({ history }: { history: History[] }) {
  if (!history.length) return <Empty>Complete a standardized assessment to start your progress chart.</Empty>;
  const data = history.map(item => ({ attempt: item.attempt, date: dateLabel(item.date), score: item.score }));
  return <div className="chart" aria-label="Standardized assessment readiness trend">
    <ResponsiveContainer width="100%" height={245}>
      <AreaChart data={data} margin={{ top: 12, left: -20, right: 20, bottom: 0 }}>
        <defs><linearGradient id="score-gradient" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#7454dd" stopOpacity={0.23} /><stop offset="100%" stopColor="#7454dd" stopOpacity={0.02} />
        </linearGradient></defs>
        <CartesianGrid stroke="#edf0f5" vertical={false} />
        <XAxis dataKey="date" fontSize={11} tickLine={false} axisLine={false} minTickGap={24} />
        <YAxis domain={[0, 100]} fontSize={11} tickLine={false} axisLine={false} tickCount={5} />
        <ReferenceLine y={75} stroke="#a49bc6" strokeDasharray="5 5" />
        <Tooltip formatter={value => [`${scoreLabel(Number(value))}%`, 'Readiness']} />
        <Area type="monotone" dataKey="score" stroke="#6c4bdd" strokeWidth={2.5} fill="url(#score-gradient)"
          dot={{ r: 3, strokeWidth: 2, fill: 'white' }} isAnimationActive={false} />
      </AreaChart>
    </ResponsiveContainer>
  </div>;
}

export function SkillScores({ topics }: { topics: Topic[] }) {
  if (!topics.length) return <Empty>No topic or subtopic scores are available yet.</Empty>;
  return <div className="skill-list">{[...topics].sort((a, b) => a.score - b.score).map(topic =>
    <details key={topic.id} className="skill"><summary>
      <span>{topic.name}</span><span className="skill-meter"><i style={{ width: topic.score + '%' }} /></span>
      <strong>{scoreLabel(topic.score)}%</strong>
    </summary><div className="subskills">{topic.subtopics.map(sub =>
      <p key={sub.name}><span>{sub.name}</span><strong>{scoreLabel(sub.score)}%</strong></p>)}</div></details>)}</div>;
}

export function predictionText(status?: string) {
  switch (status) {
    case 'synthetic_demo': return 'Synthetic demonstration';
    case 'synthetic_validation_only': return 'Model validated on synthetic data only';
    case 'model_unavailable': return 'Model unavailable';
    case 'outside_validated_landmark': return 'Outside the validated first-assessment window';
    case 'already_ready': return 'Readiness threshold already reached';
    default: return 'Insufficient assessment history';
  }
}

export function Metrics({ latest, predictions, count }: { latest: History | null; predictions?: Predictions; count: number }) {
  const cards = [
    { label: 'Current readiness', icon: Activity, value: latest ? scoreLabel(latest.score) + '%' : '—',
      detail: latest ? '75% readiness threshold' : 'No assessments available', tone: 'violet' },
    { label: 'Predicted next score', icon: TrendingUp, value: predictions?.regression ? scoreLabel(predictions.regression.value) + '%' : '—',
      detail: predictionText(predictions?.status), tone: 'blue' },
    { label: '60-day readiness probability', icon: Brain, value: predictions?.classification ? scoreLabel(predictions.classification.value * 100) + '%' : '—',
      detail: predictionText(predictions?.classification_status ?? predictions?.status), tone: 'amber' },
    { label: 'Standardized assessments', icon: Bars3BottomLeft, value: count.toString(),
      detail: count ? 'Recorded in your progress history' : 'Ready when you are', tone: 'mint' },
  ];
  return <div className="metric-grid">{cards.map(({ icon: Icon, label, value, detail, tone }) =>
    <Card className="metric" key={label}><div className={'metric-icon ' + tone}><Icon size={18} /></div>
      <p>{label}</p><strong>{value}</strong><small>{detail}</small></Card>)}</div>;
}

export function ProgressPanels({ history, topics }: { history: History[]; topics: Topic[] }) {
  return <div className="grid-two"><Card title="Readiness over time" action={<Status>Standardized</Status>}><HistoryChart history={history} /></Card>
    <Card title="Topic & subtopic scores"><SkillScores topics={topics} /></Card></div>;
}
