import { useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import toast from 'react-hot-toast'
import { useAuth } from '../hooks/useAuth'

const CLIENT_ID = import.meta.env.VITE_GOOGLE_CLIENT_ID

export default function GoogleSignInButton() {
  const { googleLogin } = useAuth()
  const navigate = useNavigate()
  const buttonRef = useRef(null)

  useEffect(() => {
    if (!CLIENT_ID || !buttonRef.current) return

    const handleCredential = async ({ credential }) => {
      const loadToast = toast.loading('Verifying with Google...')
      try {
        await googleLogin(credential)
        toast.success('Welcome back, Counselor', { id: loadToast })
        navigate('/dashboard')
      } catch (err) {
        toast.error(err.response?.data?.detail || 'Google sign-in failed', { id: loadToast })
      }
    }

    const renderButton = () => {
      if (!window.google?.accounts?.id) return false
      window.google.accounts.id.initialize({ client_id: CLIENT_ID, callback: handleCredential })
      window.google.accounts.id.renderButton(buttonRef.current, {
        theme: 'outline', size: 'large', width: 320, text: 'continue_with',
      })
      return true
    }

    if (!renderButton()) {
      const interval = setInterval(() => { if (renderButton()) clearInterval(interval) }, 200)
      return () => clearInterval(interval)
    }
  }, [googleLogin, navigate])

  if (!CLIENT_ID) return null

  return <div ref={buttonRef} className="auth-google-button" />
}
