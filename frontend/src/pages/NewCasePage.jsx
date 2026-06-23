import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import Layout from '../components/Layout'
import { casesAPI } from '../services/api'
import toast from 'react-hot-toast'
import { ChevronRight, ChevronLeft, Save, Scale, User, CreditCard, FileText, CheckCircle2 } from 'lucide-react'

function StepIndicator({ currentStep }) {
  const steps = [
    { icon: Scale, label: 'Jurisdiction' },
    { icon: User, label: 'Parties' },
    { icon: CreditCard, label: 'Transaction' },
    { icon: FileText, label: 'Review' },
  ]

  return (
    <div className="step-indicator">
      {steps.map((step, idx) => {
        const Icon = step.icon
        const isActive = currentStep === idx + 1
        const isCompleted = currentStep > idx + 1
        return (
          <div key={idx} className="step-item">
            <div className={`step-circle ${isActive ? 'is-active' : ''} ${isCompleted ? 'is-completed' : ''}`}>
              {isCompleted ? <CheckCircle2 size={20} /> : <Icon size={20} />}
            </div>
            <span className={`step-text ${isActive ? 'is-active' : ''}`}>
              {step.label}
            </span>
            {idx < steps.length - 1 && (
              <div className={`step-connector ${isCompleted ? 'is-completed' : ''}`} />
            )}
          </div>
        )
      })}
    </div>
  )
}

function Field({ label, hint, required, children, className = "" }) {
  return (
    <div className={className}>
      <div className="field-label-row">
        <label className="field-label">
          {label}{required && <span className="field-required">*</span>}
        </label>
        {hint && <span className="field-hint">— {hint}</span>}
      </div>
      {children}
    </div>
  )
}

export default function NewCasePage() {
  const navigate = useNavigate()
  const [loading, setLoading] = useState(false)
  const [step, setStep] = useState(1)

  const [form, setForm] = useState({
    court_name: '', court_location: '', police_station: '', sections_alleged: '',
    complainant_name: '', complainant_ar_name: '', complainant_address: '', complainant_phone: '', complainant_email: '',
    accused_name: '', accused_proprietor: '', accused_address: '', accused_phone: '', accused_email: '',
    cheque_number: '', cheque_date: '', cheque_amount: '', cheque_amount_words: '',
    drawee_bank: '', drawee_branch: '', deposit_bank: '', deposit_branch: '',
    dishonour_date: '', dishonour_reason: '', notice_date: '', notice_sent_by: '',
    notice_delivery_date: '', case_description: '', relief_sought: '',
  })

  const set = k => e => setForm(f => ({ ...f, [k]: e.target.value }))

  const validateStep = () => {
    if (step === 1) {
      if (!form.court_name || !form.court_location) {
        toast.error("Please fill required court details")
        return false
      }
    }
    if (step === 2) {
      if (!form.complainant_name || !form.accused_name) {
        toast.error("Please provide names for both parties")
        return false
      }
    }
    return true
  }

  const nextStep = () => {
    if (validateStep()) setStep(s => Math.min(s + 1, 4))
  }

  const prevStep = () => setStep(s => Math.max(s - 1, 1))

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (form.case_description.length < 50) {
      toast.error('Please provide a case description (min 50 chars)')
      return
    }
    setLoading(true)

    try {
      await casesAPI.submit({
        title: `${form.complainant_name} vs ${form.accused_name}`,
        jurisdiction: form.court_location,
        petitioner_name: form.complainant_name,
        respondent_name: form.accused_name,
        incident_date: form.cheque_date,
        relief_sought: form.relief_sought,
        case_description: form.case_description,
        sections_alleged: form.sections_alleged,
      })
      toast.success('Case draft created successfully!')
      navigate('/cases')
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to create case')
    } finally {
      setLoading(false)
    }
  }

  return (
    <Layout>
      <div className="page-wrap-md">
        <header className="page-header-center">
          <h1>Initialize New Draft</h1>
          <p>Fill in the details below to generate an AI-powered legal draft.</p>
        </header>

        <StepIndicator currentStep={step} />

        <div className="case-form-card">
          <form onSubmit={handleSubmit} className="form-step" style={{ flex: 1 }}>

            {step === 1 && (
              <div className="form-step animate-fade-up">
                <div className="form-step-header">
                  <h2>Court & Jurisdiction</h2>
                  <p>Specify where the case will be filed</p>
                </div>
                <div className="form-grid-2">
                  <Field label="Name of the Court" hint="e.g. District Court" required>
                    <input className="text-input" value={form.court_name} onChange={set('court_name')} placeholder="Enter court name..." />
                  </Field>
                  <Field label="Location/Place" hint="e.g. Saket, Delhi" required>
                    <input className="text-input" value={form.court_location} onChange={set('court_location')} placeholder="Enter location..." />
                  </Field>
                  <Field label="Police Station">
                    <input className="text-input" value={form.police_station} onChange={set('police_station')} placeholder="PS name..." />
                  </Field>
                  <Field label="Statutes/Sections" hint="Comma separated">
                    <input className="text-input" value={form.sections_alleged} onChange={set('sections_alleged')} placeholder="e.g. Section 138 NI Act" />
                  </Field>
                </div>
              </div>
            )}

            {step === 2 && (
              <div className="form-step animate-fade-up">
                <div className="form-step-header">
                  <h2>Parties Involved</h2>
                  <p>Details of Complainant and Accused</p>
                </div>

                <div className="form-cols">
                  <div className="form-party">
                    <h3>Complainant</h3>
                    <Field label="Legal Name" required>
                      <input className="text-input" value={form.complainant_name} onChange={set('complainant_name')} />
                    </Field>
                    <Field label="Authorised Rep (AR)">
                      <input className="text-input" value={form.complainant_ar_name} onChange={set('complainant_ar_name')} />
                    </Field>
                    <Field label="Address">
                      <textarea rows="3" className="text-area text-input" value={form.complainant_address} onChange={set('complainant_address')} />
                    </Field>
                  </div>

                  <div className="form-party">
                    <h3>Accused</h3>
                    <Field label="Full Name" required>
                      <input className="text-input" value={form.accused_name} onChange={set('accused_name')} />
                    </Field>
                    <Field label="Proprietor/Director">
                      <input className="text-input" value={form.accused_proprietor} onChange={set('accused_proprietor')} />
                    </Field>
                    <Field label="Address">
                      <textarea rows="3" className="text-area text-input" value={form.accused_address} onChange={set('accused_address')} />
                    </Field>
                  </div>
                </div>
              </div>
            )}

            {step === 3 && (
              <div className="form-step animate-fade-up">
                <div className="form-step-header">
                  <h2>Transaction Details</h2>
                  <p>Cheque and banking information</p>
                </div>
                <div className="form-grid-3">
                  <Field label="Cheque No.">
                    <input className="text-input" value={form.cheque_number} onChange={set('cheque_number')} />
                  </Field>
                  <Field label="Cheque Date">
                    <input type="date" className="text-input" value={form.cheque_date} onChange={set('cheque_date')} />
                  </Field>
                  <Field label="Amount (₹)">
                    <input type="number" className="text-input" value={form.cheque_amount} onChange={set('cheque_amount')} />
                  </Field>
                </div>
                <div className="form-grid-2">
                  <Field label="Drawee Bank">
                    <input className="text-input" value={form.drawee_bank} onChange={set('drawee_bank')} placeholder="Accused's Bank" />
                  </Field>
                  <Field label="Dishonour Reason">
                    <select className="select-input" value={form.dishonour_reason} onChange={set('dishonour_reason')}>
                      <option value="">Select Reason</option>
                      <option value="funds_insufficient">Funds Insufficient</option>
                      <option value="stop_payment">Stop Payment</option>
                      <option value="account_closed">Account Closed</option>
                      <option value="signature_mismatch">Signature Mismatch</option>
                    </select>
                  </Field>
                </div>
              </div>
            )}

            {step === 4 && (
              <div className="form-step animate-fade-up">
                <div className="form-step-header">
                  <h2>Drafting Context</h2>
                  <p>Final narrative for the AI engine</p>
                </div>
                <Field label="Case Narrative" hint="Detailed facts of the transaction" required>
                  <textarea
                    rows="8"
                    className="text-area text-input"
                    value={form.case_description}
                    onChange={set('case_description')}
                    placeholder="Describe the business relationship, how the debt arose, and the sequence of events leading to the cheque bounce..."
                  />
                  <div className="char-counter">
                    <span>Minimum 50 characters required for better AI results.</span>
                    <span className={form.case_description.length >= 50 ? "char-counter--ok" : "char-counter--low"}>
                      Count: {form.case_description.length}
                    </span>
                  </div>
                </Field>
                <Field label="Relief Sought">
                  <input className="text-input" value={form.relief_sought} onChange={set('relief_sought')} placeholder="e.g. Recovery of ₹5,00,000 with 18% p.a. interest" />
                </Field>
              </div>
            )}

            <div className="form-actions">
              <button
                type="button"
                onClick={prevStep}
                disabled={step === 1}
                className={`btn-step-prev ${step === 1 ? 'btn-step-prev--hidden' : ''}`}
              >
                <ChevronLeft size={18} /> Previous
              </button>

              {step < 4 ? (
                <button type="button" onClick={nextStep} className="btn-step-next">
                  Next Step <ChevronRight size={18} />
                </button>
              ) : (
                <button type="submit" disabled={loading} className="btn-step-submit">
                  {loading ? (
                    <>
                      <div className="spinner" />
                      Generating Draft...
                    </>
                  ) : (
                    <>
                      Generate Final Draft <Save size={18} />
                    </>
                  )}
                </button>
              )}
            </div>
          </form>
        </div>
      </div>
    </Layout>
  )
}
