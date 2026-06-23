import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth'
import { useTheme } from '../hooks/useTheme'
import toast from 'react-hot-toast'
import { Sun, Moon, Scale, Mail, Lock, ArrowRight, Shield, Award, Zap, FileCheck } from 'lucide-react'
import GoogleSignInButton from '../components/GoogleSignInButton'

export default function LoginPage() {
  const { login } = useAuth()
  const { isDark, toggleTheme } = useTheme()
  const navigate = useNavigate()
  const [form, setForm] = useState({ username: '', password: '' })
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e) => {
    e.preventDefault()
    setLoading(true)
    const loadToast = toast.loading('Verifying Credentials...')
    try {
      await login(form.username, form.password)
      toast.success('Welcome back, Counselor', { id: loadToast })
      navigate('/dashboard')
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Authentication Failed', { id: loadToast })
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="auth-page">
      <div className="auth-bg-blob auth-bg-blob--a animate-pulse" />
      <div className="auth-bg-blob auth-bg-blob--b animate-pulse" />

      <div className="auth-container">
        <div className="auth-card">

          <div className="auth-panel-brand">
            <div className="auth-panel-pattern auth-panel-pattern--dots" />
            <div className="auth-panel-glow" />

            <div style={{ position: 'relative', zIndex: 10 }}>
              <div className="auth-brand-row animate-fade-up">
                <div className="auth-brand-badge">
                  <Scale size={28} />
                </div>
                <span className="auth-brand-name">Lex<span className="brand-accent">Draft</span> AI</span>
              </div>

              <h2 className="auth-headline animate-fade-up stagger-1">
                Precision Drafting <br/>
                <span className="auth-headline-accent">Simplified.</span>
              </h2>

              <div className="auth-feature-list animate-fade-up stagger-2">
                {[
                  { icon: Shield, title: "Enterprise Security", text: "Bank-grade encryption for all client matters." },
                  { icon: Zap, title: "AI-Accelerated", text: "Reduce drafting time by up to 70% with intelligent precedents." },
                  { icon: Award, title: "Optimized for High Court", text: "Formatting and logic aligned with strict judicial standards." }
                ].map((item, i) => (
                  <div key={i} className="auth-feature">
                    <div className="auth-feature-icon">
                      <item.icon size={18} />
                    </div>
                    <div>
                      <div className="auth-feature-title">{item.title}</div>
                      <span className="auth-feature-text">{item.text}</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            <div className="auth-brand-footer animate-fade-up stagger-3">
              © 2024 LexDraft Enterprise Legal Systems
            </div>
          </div>

          <div className="auth-panel-form">
            <button onClick={toggleTheme} className="theme-toggle-floating" aria-label="Toggle theme">
              {isDark ? <Sun size={20} /> : <Moon size={20} />}
            </button>

            <div className="auth-form-wrap">
              <div style={{ marginBottom: '3rem' }}>
                <h3 className="auth-form-title">Secure Authentication</h3>
                <p className="auth-form-subtitle">Enter your credentials to access the secure drafting environment.</p>
              </div>

              <form onSubmit={handleSubmit} className="auth-form">
                <div className="auth-form-group">
                  <label className="auth-label">Identification</label>
                  <div className="auth-input-wrap">
                    <Mail className="auth-input-icon" size={20} />
                    <input
                      type="text"
                      value={form.username}
                      onChange={e => setForm(f => ({...f, username: e.target.value}))}
                      className="auth-input"
                      placeholder="Username"
                      required
                    />
                  </div>
                </div>

                <div className="auth-form-group">
                  <div className="auth-row">
                    <label className="auth-label" style={{ marginBottom: 0 }}>Access Key</label>
                    <a href="#" className="auth-inline-link">Reset Key</a>
                  </div>
                  <div className="auth-input-wrap">
                    <Lock className="auth-input-icon" size={20} />
                    <input
                      type="password"
                      value={form.password}
                      onChange={e => setForm(f => ({...f, password: e.target.value}))}
                      className="auth-input"
                      placeholder="••••••••"
                      required
                    />
                  </div>
                </div>

                <div className="auth-checkbox-row">
                  <input type="checkbox" id="remember" />
                  <label htmlFor="remember">Remember this device</label>
                </div>

                <button type="submit" disabled={loading} className="auth-submit">
                  <span>{loading ? 'Verifying...' : 'Initialize Access'}</span>
                  {!loading && <ArrowRight size={22} />}
                </button>
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
                  Don't have a secure ID?{' '}
                  <Link to="/register">
                    Request Account
                  </Link>
                </p>
              </div>
            </div>
          </div>

        </div>
      </div>
    </div>
  )
}
