// Simple SVG icon set for the chat UI (plain JSX, no TypeScript).
function Svg({ size, children }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      {children}
    </svg>
  )
}

const paths = {
  Search: (<><circle cx="11" cy="11" r="7" /><path d="m20 20-4-4" /></>),
  Bell: (<><path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9" /><path d="M13.73 21a2 2 0 0 1-3.46 0" /></>),
  Sparkles: (<><path d="M12 2c.6 5.3 3 7.5 8 8-5 .5-7.4 2.7-8 8-.6-5.3-3-7.5-8-8 5-.5 7.4-2.7 8-8Z" /><path d="M19 17c.2 2.1 1.2 3 3 3.2-1.8.2-2.8 1.1-3 3.2-.2-2.1-1.2-3-3-3.2 1.8-.2 2.8-1.1 3-3.2Z" /></>),
  Send: (<><path d="m4 4 17 8-17 8 3-8z" /><path d="M7 12h14" /></>),
  Mic: (<><rect x="9" y="3" width="6" height="11" rx="3" /><path d="M5 11a7 7 0 0 0 14 0M12 18v3M9 21h6" /></>),
  Paperclip: (<path d="m8 12 6.5-6.5a3 3 0 0 1 4.2 4.2L10 18.4a5 5 0 0 1-7.1-7.1l8.5-8.5" />),
  ChevronDown: (<path d="m6 9 6 6 6-6" />),
  ChevronRight: (<path d="m9 18 6-6-6-6" />),
  File: (<><path d="M6 3h8l4 4v14H6z" /><path d="M14 3v5h4" /></>),
  Document: (<><path d="M6 3h8l4 4v14H6z" /><path d="M14 3v5h4M9 13h6M9 17h6" /></>),
  Library: (<><path d="M4 4h4v16H4zM10 4h4v16h-4zM16 5l4-1v16l-4 1z" /></>),
  Briefcase: (<><rect x="3" y="7" width="18" height="13" rx="2" /><path d="M8 7V5a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2M3 12h18M10 12v2h4v-2" /></>),
  Folder: (<path d="M3 6h7l2 2h9v11H3z" />),
  Clock: (<><circle cx="12" cy="12" r="9" /><path d="M12 7v5l3 2" /></>),
  User: (<><circle cx="12" cy="8" r="4" /><path d="M4 21a8 8 0 0 1 16 0" /></>),
  Dots: (<><circle cx="5" cy="12" r="1" fill="currentColor" stroke="none" /><circle cx="12" cy="12" r="1" fill="currentColor" stroke="none" /><circle cx="19" cy="12" r="1" fill="currentColor" stroke="none" /></>),
  New: (<><rect x="3" y="3" width="18" height="18" rx="3" /><path d="M12 8v8M8 12h8" /></>),
  Upload: (<><path d="M12 16V3M7 8l5-5 5 5M4 14v7h16v-7" /></>),
}

export function Icon({ name, size }) {
  const s = size || 18
  return <Svg size={s}>{paths[name] || null}</Svg>
}
