import { ArrowRight, BookOpenCheck, ChartNoAxesCombined, Route } from 'lucide-react';
import { useState, type FormEvent } from 'react';
import { Button, Logo, State } from '../components/ui';
import { api, json, setSession } from '../services/api';
import type { Session } from '../types/api';

export function AuthPage({ onSession }: { onSession: () => void }) {
  const [register, setRegister] = useState(false);
  const [error, setError] = useState<unknown>();
  const [pending, setPending] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setPending(true);
    setError(undefined);
    const form = Object.fromEntries(new FormData(event.currentTarget));
    try {
      setSession(await api<Session>(register ? '/auth/register' : '/auth/login', json('POST', form), false));
      onSession();
    } catch (reason) { setError(reason); }
    finally { setPending(false); }
  }

  return <div className="auth-shell">
    <aside className="auth-brand"><Logo />
      <div className="auth-story"><h1>Build your<br />placement readiness.</h1>
        <p>Assess your skills, see what needs work, and follow a study plan for the role you want.</p>
        <div className="auth-features">
          <span><BookOpenCheck size={18} /> Role-based assessments</span>
          <span><ChartNoAxesCombined size={18} /> Progress over time</span>
          <span><Route size={18} /> Personalized roadmaps</span>
        </div>
      </div><div className="auth-decoration" aria-hidden="true"><i /><i /><i /><i /><i /><i /></div>
    </aside>
    <main className="auth-main">
      <div className="auth-form">
        <h2>{register ? 'Create a student account' : 'Sign in'}</h2>
        <p>{register ? 'Set up your profile to choose a career role.' : 'Access your placement readiness workspace.'}</p>
        <form onSubmit={submit}>
          {register && <><label>Full name<input required name="display_name" autoComplete="name" maxLength={150} /></label>
            <label>Department<input required name="department" placeholder="e.g. Computer Science" maxLength={100} /></label></>}
          <label>Email<input required name="email" type="email" autoComplete="username" maxLength={254} placeholder="you@college.edu" /></label>
          <label>Password<input required name="password" type="password" minLength={register ? 12 : 1} maxLength={256}
            autoComplete={register ? 'new-password' : 'current-password'} placeholder={register ? 'At least 12 characters' : 'Enter your password'} /></label>
          <State error={error} />
          <Button disabled={pending} type="submit">{pending ? 'Please wait…' : register ? 'Create account' : 'Sign in'}<ArrowRight size={16} /></Button>
        </form>
        <p className="auth-toggle">{register ? 'Already registered?' : 'New student?'}{' '}
          <button type="button" onClick={() => { setRegister(!register); setError(undefined); }}>
            {register ? 'Sign in' : 'Create an account'}</button></p>
      </div>
    </main>
  </div>;
}
