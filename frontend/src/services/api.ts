import type { Session } from '../types/api';

const base = import.meta.env.VITE_API_BASE_URL ?? '/api/v1';
const storage = 'placement-session';
let refreshRequest: Promise<Session> | null = null;

export function getSession(): Session | null {
  try { return JSON.parse(sessionStorage.getItem(storage) ?? 'null') as Session | null; }
  catch { return null; }
}

export function setSession(session: Session | null) {
  if (session) sessionStorage.setItem(storage, JSON.stringify(session));
  else sessionStorage.removeItem(storage);
}

export class ApiError extends Error {
  constructor(readonly status: number, message: string) { super(message); }
}

async function request<T>(path: string, init: RequestInit, session: Session | null): Promise<T> {
  const headers = new Headers(init.headers);
  if (init.body && !(init.body instanceof FormData)) headers.set('Content-Type', 'application/json');
  if (session) headers.set('Authorization', 'Bearer ' + session.access_token);
  let response: Response;
  try { response = await fetch(base + path, { ...init, headers }); }
  catch { throw new ApiError(0, 'Could not reach the placement service. Check that the backend is running.'); }
  if (response.status === 204) return undefined as T;
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    const details = body.detail;
    const message = Array.isArray(details) ? details.map(d => d.msg).join(' ')
      : typeof details === 'string' ? details : details?.message;
    throw new ApiError(response.status, message ?? 'The service could not complete this request.');
  }
  return body as T;
}

export async function api<T>(path: string, init: RequestInit = {}, authenticated = true): Promise<T> {
  const session = authenticated ? getSession() : null;
  try { return await request<T>(path, init, session); }
  catch (error) {
    if (!(error instanceof ApiError) || error.status !== 401 || !session) throw error;
    const current = getSession();
    if (current?.access_token !== session.access_token) return request<T>(path, init, current);
    const oldToken = session.refresh_token;
    if (!refreshRequest) {
      refreshRequest = request<Session>('/auth/refresh', json('POST', { refresh_token: oldToken }), null)
        .then(next => {
          if (getSession()?.refresh_token !== oldToken) throw new ApiError(401, 'Session ended.');
          setSession(next);
          return next;
        })
        .catch(reason => {
          if (getSession()?.refresh_token === oldToken) setSession(null);
          throw reason;
        })
        .finally(() => { refreshRequest = null; });
    }
    return request<T>(path, init, await refreshRequest);
  }
}

export function json(method: string, body: unknown = {}): RequestInit {
  return { method, body: JSON.stringify(body) };
}
