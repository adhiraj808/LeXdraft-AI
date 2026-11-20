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
  if (!hasAny) return <p className="draft-section-empty">No entities extracted</p>

  return (
    <div className="entity-panel animate-fade-up">
      {Object.entries(LABELS).map(([key, { label, color }]) => {
        const items = entities[key]
        if (!items?.length) return null
        return (
          <div key={key} className="entity-panel-group">
            <div className="entity-panel-label" style={{ color }}>{label}</div>
            <div className="entity-panel-chips">
              {items.map((item, i) => (
                <span
                  key={i}
                  className="entity-panel-chip"
                  style={{
                    background: `${color}15`,
                    color,
                    borderColor: `${color}25`,
                  }}
                >
                  {item}
                </span>
              ))}
            </div>
          </div>
        )
      })}
    </div>
  )
}