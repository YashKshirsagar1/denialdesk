import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from 'react'
import { AlertCircle, CheckCircle2, FileSearch, Info, X } from 'lucide-react'
import { statusMeta, type Tone } from '../lib/caseStatus'

export function Badge({ tone = 'gray', children, plain }: { tone?: Tone; children: ReactNode; plain?: boolean }) {
  return <span className={`badge tone-${tone}${plain ? ' plain' : ''}`}>{children}</span>
}

export function StatusBadge({ state }: { state: string }) {
  const m = statusMeta(state)
  return <Badge tone={m.tone}>{m.label}</Badge>
}

export function Stat({ label, value, hint, icon, tone = 'blue' }: {
  label: string; value: ReactNode; hint?: ReactNode; icon?: ReactNode; tone?: Tone
}) {
  return (
    <div className="card stat">
      <div className="label">
        {icon && <span className={`ico tone-${tone}`}>{icon}</span>}
        {label}
      </div>
      <div className="value">{value}</div>
      {hint && <div className="hint">{hint}</div>}
    </div>
  )
}

export function PageHead({ title, sub, actions }: { title: string; sub?: ReactNode; actions?: ReactNode }) {
  return (
    <div className="page-head">
      <div>
        <h1>{title}</h1>
        {sub && <div className="sub">{sub}</div>}
      </div>
      {actions && <div className="row wrap">{actions}</div>}
    </div>
  )
}

export function Empty({ title, children, icon, action }: { title: string; children?: ReactNode; icon?: ReactNode; action?: ReactNode }) {
  return (
    <div className="empty">
      <div className="ico">{icon ?? <FileSearch size={24} />}</div>
      <h3>{title}</h3>
      {children && <p>{children}</p>}
      {action && <div style={{ marginTop: 16 }}>{action}</div>}
    </div>
  )
}

export function Spinner({ large }: { large?: boolean }) {
  return <span className={`spinner${large ? ' lg' : ''}`} role="status" aria-label="Loading" />
}

export function Loading() {
  return <div className="center"><Spinner large /></div>
}

export function Alert({ kind = 'info', children }: { kind?: 'info' | 'warn' | 'error' | 'success'; children: ReactNode }) {
  const Icon = kind === 'error' || kind === 'warn' ? AlertCircle : kind === 'success' ? CheckCircle2 : Info
  return (
    <div className={`alert ${kind}`} role={kind === 'error' ? 'alert' : undefined}>
      <Icon size={17} style={{ flex: 'none', marginTop: 1 }} />
      <div>{children}</div>
    </div>
  )
}

export function Modal({ title, onClose, children, footer }: { title: string; onClose: () => void; children: ReactNode; footer?: ReactNode }) {
  useEffect(() => {
    const h = (e: KeyboardEvent) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', h)
    return () => window.removeEventListener('keydown', h)
  }, [onClose])
  return (
    <div className="overlay" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className="modal" role="dialog" aria-modal="true" aria-label={title}>
        <div className="modal-head">
          <h3>{title}</h3>
          <button className="icon-btn" style={{ color: 'var(--text-3)' }} onClick={onClose} aria-label="Close"><X size={18} /></button>
        </div>
        <div className="modal-body">{children}</div>
        {footer && <div className="modal-foot">{footer}</div>}
      </div>
    </div>
  )
}

// ---- toasts ----
type ToastKind = 'info' | 'success' | 'error'
const ToastCtx = createContext<(msg: string, kind?: ToastKind) => void>(() => {})
export const useToast = () => useContext(ToastCtx)

export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<{ id: number; msg: string; kind: ToastKind }[]>([])
  const next = useRef(1)
  const push = useCallback((msg: string, kind: ToastKind = 'info') => {
    const id = next.current++
    setItems((l) => [...l, { id, msg, kind }])
    setTimeout(() => setItems((l) => l.filter((t) => t.id !== id)), kind === 'error' ? 6000 : 3500)
  }, [])
  return (
    <ToastCtx.Provider value={push}>
      {children}
      <div className="toasts" aria-live="polite">
        {items.map((t) => (
          <div key={t.id} className={`toast ${t.kind}`}>{t.msg}</div>
        ))}
      </div>
    </ToastCtx.Provider>
  )
}

// ---- data loading ----
export function useAsync<T>(fn: () => Promise<T>, deps: unknown[] = []) {
  const [data, setData] = useState<T | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const seq = useRef(0)

  const run = useCallback(() => {
    const mine = ++seq.current
    setLoading(true)
    fn()
      .then((d) => { if (mine === seq.current) { setData(d); setError(null) } })
      .catch((e: Error) => { if (mine === seq.current) setError(e.message) })
      .finally(() => { if (mine === seq.current) setLoading(false) })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps)

  useEffect(() => { run() }, [run])
  return { data, error, loading, reload: run, setData }
}

export function Async<T>({ state, children, empty }: {
  state: { data: T | null; error: string | null; loading: boolean }
  children: (d: T) => ReactNode
  empty?: ReactNode
}) {
  if (state.loading && !state.data) return <Loading />
  if (state.error && !state.data) return <Alert kind="error">{state.error}</Alert>
  if (!state.data) return <>{empty}</>
  return <>{children(state.data)}</>
}
