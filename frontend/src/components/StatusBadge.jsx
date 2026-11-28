const CFG = {
  pending:    { label: 'Pending',    variant: 'pending' },
  processing: { label: 'Processing', variant: 'processing', pulse: true },
  completed:  { label: 'Completed',  variant: 'completed' },
  failed:     { label: 'Failed',     variant: 'failed' },
}

export default function StatusBadge({ status }) {
  const c = CFG[status] || CFG.pending
  return (
    <span className={`status-badge status-badge--${c.variant}`}>
      <span className={`status-dot ${c.pulse ? 'animate-pulse' : ''}`} />
      {c.label}
    </span>
  )
}
