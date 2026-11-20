const COLORS = {
  'Criminal':            { bg: 'rgba(192,57,43,0.12)',  color: '#f87171' },
  'Civil':               { bg: 'rgba(59,130,246,0.1)',  color: '#60a5fa' },
  'Family Law':          { bg: 'rgba(236,72,153,0.1)',  color: '#f472b6' },
  'Labour / Employment': { bg: 'rgba(249,115,22,0.1)', color: '#fb923c' },
  'Constitutional':      { bg: 'rgba(139,92,246,0.1)', color: '#c084fc' },
  'Property Dispute':    { bg: 'rgba(20,184,166,0.1)', color: '#2dd4bf' },
}

export default function CaseTypeBadge({ type, confidence }) {
  const c = COLORS[type] || { bg: 'rgba(201,168,76,0.1)', color: 'var(--gold)' }
  return (
    <span
      className="case-type-badge badge-colored"
      style={{ background: c.bg, color: c.color, borderColor: `${c.color}30` }}
    >
      {type}
      {confidence != null && (
        <span style={{ opacity: 0.55, fontSize: '0.625rem' }}>{Math.round(confidence * 100)}%</span>
      )}
    </span>
  )
}