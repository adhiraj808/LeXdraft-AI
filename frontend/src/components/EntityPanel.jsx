const LABELS = {
  persons:       { label: 'Parties & Persons',  color: '#60a5fa' },
  organizations: { label: 'Organisations',       color: '#c084fc' },
  statutes:      { label: 'Statutes Cited',      color: '#f87171' },
  dates:         { label: 'Dates',               color: 'var(--gold)' },
  courts:        { label: 'Courts',              color: '#2dd4bf' },
  locations:     { label: 'Locations',           color: '#4ade80' },
  money:         { label: 'Monetary Amounts',    color: '#fb923c' },
}
export default function EntityPanel({ entities }) {
  if (!entities) return null
  const hasAny = Object.values(entities).some(v => Array.isArray(v) && v.length > 0)
  if (!hasAny) return <p style={{ fontSize: 12, color: 'var(--cream-dim)', opacity: 0.4, fontStyle: 'italic' }}>No entities extracted</p>
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
      {Object.entries(LABELS).map(([key, { label, color }]) => {
        const items = entities[key]
        if (!items?.length) return null
        return (
          <div key={key}>
            <div style={{ fontSize: 10, letterSpacing: '0.1em', textTransform: 'uppercase', color, marginBottom: 8, opacity: 0.8 }}>{label}</div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
              {items.map((item, i) => (
                <span key={i} style={{ fontSize: 11, padding: '3px 9px', borderRadius: 4, background: `${color}15`, color, border: `1px solid ${color}25`, fontFamily: 'DM Mono, monospace', letterSpacing: '0.02em' }}>{item}</span>
              ))}
            </div>
          </div>
        )
      })}
    </div>
  )
}
