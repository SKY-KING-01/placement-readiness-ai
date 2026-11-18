import { Slot } from '@radix-ui/react-slot';
import { cva, type VariantProps } from 'class-variance-authority';
import { CircleAlert, Command, LoaderCircle } from 'lucide-react';
import type { ButtonHTMLAttributes, ReactNode } from 'react';
import { twMerge } from 'tailwind-merge';

// Local shadcn-style primitives composed with Radix Slot.
const button = cva('button', { variants: { variant: {
  primary: 'button-primary', outline: 'button-outline', ghost: 'button-ghost', danger: 'button-danger',
} }, defaultVariants: { variant: 'primary' } });

export function Button({ asChild, variant, className, ...rest }:
  ButtonHTMLAttributes<HTMLButtonElement> & VariantProps<typeof button> & { asChild?: boolean }) {
  const Node = asChild ? Slot : 'button';
  return <Node className={twMerge(button({ variant }), className)} {...rest} />;
}

export function Logo() {
  return <span className="logo"><span className="logo-icon"><Command size={19} strokeWidth={2.8} /></span>
    <span>Placement<span className="logo-light">Readiness</span></span></span>;
}

export function Header({ title, children, aside }: { title: string; children?: ReactNode; aside?: ReactNode }) {
  return <header className="page-heading"><div><h1>{title}</h1>{children && <p>{children}</p>}</div>{aside}</header>;
}

export function Card({ title, children, action, className = '' }:
  { title?: string; children: ReactNode; action?: ReactNode; className?: string }) {
  return <section className={'card ' + className}>{(title || action) &&
    <div className="card-heading"><h2>{title}</h2>{action}</div>}{children}</section>;
}

export function Status({ children, kind = 'neutral' }: { children: ReactNode; kind?: 'neutral' | 'good' | 'warn' }) {
  return <span className={'status ' + kind}>{children}</span>;
}

export function State({ loading, error, children }: { loading?: boolean; error?: unknown; children?: ReactNode }) {
  if (loading) return <p className="feedback" role="status"><LoaderCircle className="spin" size={17} />Loading…</p>;
  if (error) return <p className="feedback error" role="alert"><CircleAlert size={17} />
    {error instanceof Error ? error.message : String(error)}</p>;
  return children;
}

export function Empty({ children }: { children: ReactNode }) {
  return <div className="empty">{children}</div>;
}

export const dateLabel = (value: string) => new Intl.DateTimeFormat(undefined, { month: 'short', day: 'numeric', year: 'numeric' }).format(new Date(value));
export const scoreLabel = (value: number) => new Intl.NumberFormat(undefined, { maximumFractionDigits: 1 }).format(value);
