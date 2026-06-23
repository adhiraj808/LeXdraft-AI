import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth'
import { useTheme } from '../hooks/useTheme'
import toast from 'react-hot-toast'
import { Sun, Moon, Scale, Mail, Lock, User, UserPlus, ArrowRight, CheckCircle2, FileCheck } from 'lucide-react'
import GoogleSignInButton from '../components/GoogleSignInButton'

export default function RegisterPage() {
  const { register } = useAuth()
  const { isDark, toggleTheme } = useTheme()
  const navigate = useNavigate()
  const [form, setForm] = useState({ email: '', username: '', password: '', full_name: '' })
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e) => {
    e.preventDefault()
    setLoading(true)
    const loadToast = toast.loading('Creating Secure Identity...')
    try {
      await register(form)
      toast.success('Account Activated. Please Sign In.', { id: loadToast })
      navigate('/login')
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Registration failed', { id: loadToast })
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="auth-page">
      <div className="auth-bg-blob auth-bg-blob--a" />

      <div className="auth-container auth-container--register">
        <div className="auth-card">

          <div className="auth-panel-form" style={{ order: 2 }}>
            <button onClick={toggleTheme} className="theme-toggle-floating" style={{ top: '2rem', right: '2rem' }} aria-label="Toggle theme">
              {isDark ? <Sun size={20} /> : <Moon size={20} />}
            </button>

            <div className="auth-form-wrap">
              <div style={{ marginBottom: '2.5rem' }}>
                <h2 className="auth-form-title" style={{ fontSize: '2.25rem' }}>Join the Archives</h2>
                <p className="auth-form-subtitle">Create your legal professional account.</p>
              </div>

              <form onSubmit={handleSubmit} className="auth-form auth-form--compact">
                <div className="auth-form-grid">
                  <div>
                    <label className="auth-label">Full Name</label>
                    <div className="auth-input-wrap">
                      <User className="auth-input-icon" size={18} />
                      <input type="text" value={form.full_name} onChange={e => setForm({...form, full_name: e.target.value})} className="auth-input auth-input--compact" placeholder="Counsel Name" />
                    </div>
                  </div>

                  <div>
                    <label className="auth-label">Email Address</label>
                    <div className="auth-input-wrap">
                      <Mail className="auth-input-icon" size={18} />
                      <input type="email" value={form.email} onChange={e => setForm({...form, email: e.target.value})} className="auth-input auth-input--compact" placeholder="advocate@court.in" required />
                    </div>
                  </div>

                  <div>
                    <label className="auth-label">Unique Username</label>
                    <div className="auth-input-wrap">
                      <UserPlus className="auth-input-icon" size={18} />
                      <input type="text" value={form.username} onChange={e => setForm({...form, username: e.target.value})} className="auth-input auth-input--compact" placeholder="counsel_24" required />
                    </div>
                  </div>

                  <div>
                    <label className="auth-label">Access Password</label>
                    <div className="auth-input-wrap">
                      <Lock className="auth-input-icon" size={18} />
                      <input type="password" value={form.password} onChange={e => setForm({...form, password: e.target.value})} className="auth-input auth-input--compact" placeholder="••••••••" required />
                    </div>
                  </div>
                </div>

                <div style={{ paddingTop: '1rem' }}>
                  <button type="submit" disabled={loading} className="auth-submit">
                    {loading ? (
                      <div className="spinner" />
                    ) : (
                      <>Create Account <ArrowRight size={22} /></>
                    )}
                  </button>
                </div>
              </form>

              <div className="auth-divider"><span>or</span></div>
              <GoogleSignInButton />

              <div className="auth-security-badges">
                <span className="auth-security-badge"><Lock size={13} /> AES-256</span>
                <span className="auth-security-badge-sep" />
                <span className="auth-security-badge"><FileCheck size={13} /> Compliance Ready</span>
              </div>

              <div className="auth-footer">
                <p>
                  Already have access?{' '}
                  <Link to="/login">
                    Sign in here
                  </Link>
                </p>
              </div>
            </div>
          </div>

          <div className="auth-panel-brand auth-panel-brand--center" style={{ order: 1 }}>
            <div className="auth-panel-pattern auth-panel-pattern--lines" />

            <div style={{ position: 'relative', zIndex: 10 }}>
              <div className="auth-brand-row">
                <div className="auth-brand-badge" style={{ width: '4rem', height: '4rem', borderRadius: '1rem' }}>
                  <Scale size={32} />
                </div>
                <span className="auth-brand-name">Lex<span className="brand-accent">Draft</span> AI</span>
              </div>

              <h1 className="auth-headline" style={{ fontSize: '3rem', marginBottom: '2rem' }}>
                Unlock the <span className="auth-headline-accent">Standard</span> in Legal Automation.
              </h1>

              <div className="auth-feature-list">
                {[
                  "Draft high-quality complaints in seconds",
                  "Automated Indian Statute referencing",
                  "Secure, private case management",
                  "Verified RAG-enhanced accuracy"
                ].map((text, i) => (
                  <div key={i} className="auth-feature-card">
                    <CheckCircle2 size={24} className="auth-headline-accent" />
                    <span className="auth-feature-card-text">{text}</span>
                  </div>
                ))}
              </div>
            </div>

            <div className="auth-brand-footer" style={{ marginTop: '2rem' }}>
              © 2024 LexDraft Enterprise Legal Systems
            </div>
          </div>

        </div>
      </div>
    </div>
  )
}
