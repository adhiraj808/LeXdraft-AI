import { useState } from 'react'
import { ChevronDown } from 'lucide-react'
const SECTIONS = [
  { key:'title_block',        label:'Title Block & Case Caption',           num:'I'   },
  { key:'complaint_body',     label:'Complaint — Most Respectfully Showeth',num:'II'  },
  { key:'prayer',             label:'Prayer',                               num:'III' },
  { key:'list_of_witnesses',  label:'List of Witnesses',                    num:'IV'  },
  { key:'list_of_documents',  label:'List of Documents',                    num:'V'   },
  { key:'affidavit',          label:'Affidavit',                            num:'VI'  },
  { key:'evidence_affidavit', label:'Evidence by Way of Affidavit',         num:'VII' },
]
function Section({ num, label, sectionKey, content, onRegenerate }) {
  const [open, setOpen] = useState(true)
  const [regenOpen, setRegenOpen] = useState(false)
  const [ctx, setCtx] = useState('')
  return (
    <div style={{ border:'1px solid var(--border)', borderRadius:8, overflow:'hidden', marginBottom:10 }}>
      <div onClick={() => setOpen(o => !o)} style={{ display:'flex', alignItems:'center', gap:12, padding:'12px 18px', background:'var(--navy-3)', cursor:'pointer', userSelect:'none' }}>
        <span style={{ fontFamily:'DM Mono, monospace', fontSize:10, color:'var(--gold)', opacity:0.6, width:28, flexShrink:0 }}>{num}</span>
        <span style={{ fontSize:11, letterSpacing:'0.08em', textTransform:'uppercase', color:'var(--cream-dim)', flex:1 }}>{label}</span>
        <div onClick={e => { e.stopPropagation(); setRegenOpen(o => !o) }}
          style={{ display:'flex', alignItems:'center', fontSize:11, color:'var(--gold)', opacity:0.6, padding:'2px 8px', border:'1px solid var(--border-strong)', borderRadius:4, cursor:'pointer', lineHeight:1.6 }}
          onMouseEnter={e => e.currentTarget.style.opacity=1} onMouseLeave={e => e.currentTarget.style.opacity=0.6}>Regenerate</div>
        <span style={{ color:'var(--cream-dim)', opacity:0.3, display:'inline-flex', alignItems:'center', lineHeight:0, transition:'transform 0.2s', transform:open?'rotate(180deg)':'none' }}><ChevronDown size={14} /></span>
      </div>
      {regenOpen && (
        <div style={{ padding:'12px 18px', background:'rgba(201,168,76,0.05)', borderBottom:'1px solid var(--border)', display:'flex', gap:8 }}>
          <input value={ctx} onChange={e => setCtx(e.target.value)} placeholder="Optional: additional instructions..." className="input-dark" style={{ flex:1, borderRadius:5, padding:'7px 12px', fontSize:13 }} />
          <button onClick={() => { onRegenerate(sectionKey, ctx); setRegenOpen(false); setCtx('') }} className="btn-gold" style={{ borderRadius:5, padding:'7px 16px', fontSize:12, border:'none', cursor:'pointer' }}>Generate</button>
          <button onClick={() => setRegenOpen(false)} style={{ background:'transparent', border:'1px solid var(--border)', borderRadius:5, padding:'7px 12px', fontSize:12, color:'var(--cream-dim)', cursor:'pointer' }}>Cancel</button>
        </div>
      )}
      {open && (
        <div style={{ padding:'28px 32px', background:'var(--navy-2)' }}>
          {content
            ? <pre style={{ fontFamily:'Cormorant Garamond, serif', fontSize:14, lineHeight:2, color:'var(--cream)', whiteSpace:'pre-wrap', wordBreak:'break-word', margin:0 }}>{content}</pre>
            : <p style={{ fontSize:12, color:'var(--cream-dim)', opacity:0.35, fontStyle:'italic', margin:0 }}>No content generated for this section.</p>}
        </div>
      )}
    </div>
  )
}
export default function DraftViewer({ draft, onRegenerate }) {
  if (!draft) return (
    <div style={{ textAlign:'center', padding:'60px 0', border:'1px dashed var(--border)', borderRadius:12 }}>
      <div style={{ fontFamily:'Cormorant Garamond, serif', fontSize:20, color:'var(--cream-dim)', opacity:0.4 }}>Draft not yet generated</div>
    </div>
  )
  return (
    <div>
      <div style={{ display:'flex', alignItems:'center', gap:10, marginBottom:16, padding:'10px 14px', background:'rgba(201,168,76,0.04)', border:'1px solid var(--border)', borderRadius:6 }}>
        <span style={{ fontSize:10, color:'var(--gold)', letterSpacing:'0.1em', textTransform:'uppercase' }}>Format</span>
        <span style={{ fontSize:11, color:'var(--cream-dim)', opacity:0.55 }}>Indian Court Complaint — 7 sections: Title Block → Complaint Body → Prayer → Witnesses → Documents → Affidavit → Evidence</span>
      </div>
      {SECTIONS.map(({ key, label, num }) => (
        <Section key={key} num={num} label={label} sectionKey={key} content={draft.sections?.[key]} onRegenerate={onRegenerate} />
      ))}
    </div>
  )
}
