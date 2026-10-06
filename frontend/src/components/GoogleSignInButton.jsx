import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import toast from 'react-hot-toast'
import { useAuth } from '../hooks/useAuth'

const CLIENT_ID = import.meta.env.VITE_GOOGLE_CLIENT_ID

function GLogo() {
  return (
    <svg width="20" height="20" viewBox="0 0 48 48" aria-hidden="true">
      <path fill="#FFC107" d="M43.6 20.1H42V20H24v8h11.3C33.7 32.7 29.2 36 24 36c-6.6 0-12-5.4-12-12s5.4-12 12-12c3.1 0 5.9 1.2 8 3l5.7-5.7C34.3 6.1 29.4 4 24 4 13 4 4 13 4 24s9 20 20 20 20-9 20-20c0-1.3-.1-2.6-.4-3.9z" />
      <path fill="#FF3D00" d="M6.3 14.7l6.6 4.8C14.7 15.1 19 12 24 12c3.1 0 5.9 1.2 8 3l5.7-5.7C34.3 6.1 29.4 4 24 4 16.3 4 9.7 8.3 6.3 14.7z" />
      <path fill="#1976D2" d="M24 44c5.2 0 9.9-2 13.4-5.2l-6.2-5.2C29.2 35.1 26.7 36 24 36c-5.2 0-9.6-3.3-11.3-8l-6.5 5C9.5 39.6 16.2 44 24 44z" />
      <path fill="#388E3C" d="M43.6 20.1H42V20H24v8h11.3c-.8 2.2-2.2 4.2-4.1 5.6l6.2 5.2C36.9 39.2 44 34 44 24c0-1.3-.1-2.6-.4-3.9z" />
    </svg>
  )
}

export default function GoogleSignInButton() {
  const { googleLogin } = useAuth()
  const navigate = useNavigate()
  const boxRef = useRef(null)
  const wrapRef = useRef(null)
  const [ready, setReady] = useState(false)
  const lastWidth = useRef(0)

  useEffect(() => {
    if (!CLIENT_ID) return
    let cancelled = false
    let observer = null
    let timer = null

    const renderReal = (width) => {
      if (cancelled || !boxRef.current || !window.google?.accounts?.id) return false
      const w = Math.max(200, Math.min(400, Math.round(width) || 320))
      if (Math.abs(w - lastWidth.current) < 12 && boxRef.current.firstChild) return true
      lastWidth.current = w
      window.google.accounts.id.initialize({
        client_id: CLIENT_ID,
        callback: async ({ credential }) => {
          const loadToast = toast.loading('Verifying with Google...')
          try {
            await googleLogin(credential)
            toast.success('Welcome back, Counselor', { id: loadToast })
            navigate('/dashboard')
          } catch (err) {
            toast.error(err.response?.data?.detail || 'Google sign-in failed', { id: loadToast })
          }
        },
      })
      window.google.accounts.id.renderButton(boxRef.current, {
        theme: 'outline',
        size: 'large',
        shape: 'rectangular',
        text: 'continue_with',
        width: w,
      })
      setReady(true)
      return true
    }

    const tryBoot = () => {
      if (!window.google?.accounts?.id || !wrapRef.current) return false
      const boot = () => renderReal(wrapRef.current.getBoundingClientRect().width)
      boot()
      if (typeof ResizeObserver !== 'undefined') {
        observer = new ResizeObserver(() => {
          if (wrapRef.current) renderReal(wrapRef.current.getBoundingClientRect().width)
        })
        observer.observe(wrapRef.current)
      }
      return true
    }

    if (!tryBoot()) {
      timer = setInterval(() => { if (tryBoot()) clearInterval(timer) }, 300)
    }
    return () => {
      cancelled = true
      if (timer) clearInterval(timer)
      if (observer) observer.disconnect()
    }
  }, [googleLogin, navigate])

  if (!CLIENT_ID) return null

  return (
    <div className="google-themed-wrap" ref={wrapRef}>
      <button type="button" className="google-themed-btn" disabled={!ready} tabIndex={-1} aria-hidden="true">
        <GLogo />
        <span>Continue with Google</span>
      </button>
      <div ref={boxRef} className="google-real-overlay" aria-hidden="true" />
    </div>
  )
}
