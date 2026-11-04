import { useState, useEffect, useCallback, useRef } from 'react'
import { casesAPI } from '../services/api'
import toast from 'react-hot-toast'

export function useCaseList() {
  const [cases, setCases] = useState([])
  const [loading, setLoading] = useState(true)

  const fetch = useCallback(async () => {
    try {
      setLoading(true)
      const { data } = await casesAPI.list()
      setCases(data)
    } catch {
      toast.error('Failed to load cases')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { fetch() }, [fetch])
  return { cases, loading, refetch: fetch }
}

export function useCaseDetail(caseId) {
  const [caseData, setCaseData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [polling, setPolling] = useState(false)
  const pollRef = useRef(null)

  const fetch = useCallback(async () => {
    if (!caseId) return
    try {
      const { data } = await casesAPI.get(caseId)
      setCaseData(data)
      // If still processing, keep polling
      if (data.status === 'processing' || data.status === 'pending') {
        setPolling(true)
      } else {
        setPolling(false)
        if (pollRef.current) clearInterval(pollRef.current)
      }
      return data
    } catch {
      toast.error('Failed to load case')
    } finally {
      setLoading(false)
    }
  }, [caseId])

  useEffect(() => {
    fetch()
  }, [fetch])

  useEffect(() => {
    if (polling) {
      pollRef.current = setInterval(() => fetch(), 3000)
    }
    return () => { if (pollRef.current) clearInterval(pollRef.current) }
  }, [polling, fetch])

  const regenerate = async (section, additionalContext) => {
    try {
      toast.loading(`Regenerating ${section}...`, { id: 'regen' })
      const { data } = await casesAPI.regenerate(caseId, section, additionalContext)
      // "all" is queued in the background: the response is only a status, the
      // draft arrives later. Just refetch - the poller will refresh the view.
      if (section === 'all') {
        toast.success('Regeneration queued', { id: 'regen' })
        fetch()
        return
      }
      setCaseData(prev => prev ? {
        ...prev,
        draft: prev.draft ? {
          ...prev.draft,
          sections: { ...prev.draft.sections, [section]: data.content }
        } : prev.draft
      } : prev)
      toast.success('Section regenerated', { id: 'regen' })
    } catch {
      toast.error('Regeneration failed', { id: 'regen' })
    }
  }

  const exportPdf = async () => {
    try {
      toast.loading('Generating PDF...', { id: 'pdf' })
      const resp = await casesAPI.exportPdf(caseId)
      // The backend falls back to HTML when ReportLab fails: download that as a
      // .html file instead of a broken "PDF".
      const contentType = resp.headers?.['content-type'] || ''
      const isPdf = !contentType.includes('html')
      const type = isPdf ? 'application/pdf' : 'text/html'
      const filename = `legal_draft_${caseId.slice(0, 8)}${isPdf ? '.pdf' : '.html'}`
      const url = URL.createObjectURL(new Blob([resp.data], { type }))
      const a = document.createElement('a')
      a.href = url
      a.download = filename
      document.body.appendChild(a)
      a.click()
      a.remove()
      // Revoking immediately can cancel the download in some browsers.
      setTimeout(() => URL.revokeObjectURL(url), 5000)
      toast.success('PDF downloaded', { id: 'pdf' })
    } catch {
      toast.error('PDF export failed', { id: 'pdf' })
    }
  }

  return { caseData, loading, polling, refetch: fetch, regenerate, exportPdf }
}
