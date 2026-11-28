import { useState, useMemo } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import Layout from '../components/Layout'
import { casesAPI } from '../services/api'
import toast from 'react-hot-toast'
import { getErrorMessage } from '../services/api'
import { 
  ChevronRight, ChevronLeft, Save, Scale, User, FileText, CheckCircle2, 
  Briefcase, Gavel, Home, Factory, Building2, Users, Search,
  ArrowRight, ArrowLeft, Plus, Minus, AlertTriangle, Info
} from 'lucide-react'
import { 
  LOCATION_DATA, 
  getCourtsForLocation, 
  getPoliceStationsForLocation,
  ALL_COURTS,
  ALL_POLICE_STATIONS,
  CASE_TYPE_STATUTES
} from '../data/legalLists'
import { CASE_TYPES, CASE_TYPE_FIELDS, COMMON_FIELDS, JURISDICTION_FIELDS } from '../data/caseTypes'

// --- Step Indicator Component ---
function StepIndicator({ currentStep, totalSteps, steps }) {
  return (
    <div className="step-indicator">
      {steps.map((step, idx) => {
        const isActive = currentStep === idx + 1
        const isCompleted = currentStep > idx + 1
        return (
          <div key={idx} className="step-item">
            <div className={`step-circle ${isActive ? 'is-active' : ''} ${isCompleted ? 'is-completed' : ''}`}>
              {isCompleted ? <CheckCircle2 size={20} /> : <step.icon size={20} />}
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

// --- Field Wrapper Component ---
function Field({ label, hint, required, children, className = "", error }) {
  return (
    <div className={className}>
      <div className="field-label-row">
        <label className="field-label">
          {label}{required && <span className="field-required">*</span>}
        </label>
        {hint && <span className="field-hint">— {hint}</span>}
      </div>
      {children}
      {error && <span className="field-error">{error}</span>}
    </div>
  )
}

// --- Case Type Card Component ---
function CaseTypeCard({ type, selected, onClick }) {
  return (
    <button
      type="button"
      className={`case-type-card ${selected ? 'selected' : ''}`}
      onClick={() => onClick(type.id)}
    >
      <div className="case-type-icon">{type.icon}</div>
      <div className="case-type-info">
        <h4>{type.label}</h4>
        <p>{type.subtitle}</p>
      </div>
      {selected && <div className="case-type-check"><CheckCircle2 size={24} /></div>}
    </button>
  )
}

// --- Dynamic Input Component ---
function DynamicInput({ field, value, onChange, error, className = "" }) {
  const { type = 'text', options, rows = 3, minChars, maxChars } = field
  const showCharCount = minChars && type === 'textarea'
  const charCount = value?.length || 0

  if (type === 'select') {
    return (
      <Field label={field.label} hint={field.hint} required={field.required} error={error}>
        <select 
          className={`select-input ${className}`} 
          value={value || ''} 
          onChange={e => onChange(e.target.value)}
          required={field.required}
        >
          <option value="">Select {field.label}...</option>
          {options?.map(opt => (
            <option key={opt} value={opt}>{opt}</option>
          ))}
        </select>
      </Field>
    )
  }

  if (type === 'textarea') {
    return (
      <Field label={field.label} hint={field.hint} required={field.required} error={error} className={className}>
        <textarea
          rows={rows}
          className="text-area text-input"
          value={value || ''}
          onChange={e => onChange(e.target.value)}
          placeholder={field.placeholder}
          required={field.required}
        />
        {showCharCount && (
          <div className={`char-counter ${charCount >= (minChars || 0) ? 'char-counter--ok' : 'char-counter--low'}`}>
            {charCount} / {minChars} minimum characters
          </div>
        )}
      </Field>
    )
  }

  if (type === 'date') {
    return (
      <Field label={field.label} hint={field.hint} required={field.required} error={error} className={className}>
        <input
          type="date"
          className="text-input"
          value={value || ''}
          onChange={e => onChange(e.target.value)}
          required={field.required}
        />
      </Field>
    )
  }

  if (type === 'number') {
    return (
      <Field label={field.label} hint={field.hint} required={field.required} error={error} className={className}>
        <input
          type="number"
          className="text-input"
          value={value || ''}
          onChange={e => onChange(e.target.value)}
          required={field.required}
          min="0"
          step="any"
        />
      </Field>
    )
  }

  // Default text input
  return (
    <Field label={field.label} hint={field.hint} required={field.required} error={error} className={className}>
      <input
        className="text-input"
        value={value || ''}
        onChange={e => onChange(e.target.value)}
        placeholder={field.placeholder}
        required={field.required}
        list={field.datalist}
      />
      {field.datalist && <datalist id={field.datalist}>{field.datalistOptions?.map(o => <option key={o} value={o} />)}</datalist>}
    </Field>
  )
}

export default function NewCasePage() {
  const navigate = useNavigate()
  const [loading, setLoading] = useState(false)
  const [step, setStep] = useState(1)
  const [selectedCaseType, setSelectedCaseType] = useState(null)
  const [errors, setErrors] = useState({})
  const [touched, setTouched] = useState({})

  // Form state - dynamic based on case type
  const [form, setForm] = useState({
    // Case type
    case_type: '',
    
    // Jurisdiction (common)
    court_name: '', 
    court_location: '', 
    police_station: '',
    
    // Parties (common - labels change)
    petitioner_name: '', 
    petitioner_address: '', 
    petitioner_phone: '', 
    petitioner_email: '',
    respondent_name: '', 
    respondent_details: '',
    
    // Case-specific dynamic fields
    sections_alleged: '',
    incident_date: '',
    case_description: '',
    relief_sought: '',
    
    // Criminal
    fir_number: '',
    accused_details: '',
    
    // Civil
    contract_date: '',
    contract_value: '',
    defendant_details: '',
    
    // Family Law
    marriage_date: '',
    separation_date: '',
    children_details: '',
    relief_type: '',
    
    // Labour
    joining_date: '',
    termination_date: '',
    designation: '',
    salary: '',
    employer_details: '',
    dispute_type: '',
    
    // Constitutional
    authority: '',
    writ_type: '',
    fundamental_rights: '',
    
    // Property
    property_address: '',
    property_type: '',
    ownership_basis: '',
  })

  const caseTypeConfig = useMemo(() => 
    CASE_TYPES.find(t => t.id === selectedCaseType), [selectedCaseType])

  const specificFields = useMemo(() => 
    selectedCaseType ? CASE_TYPE_FIELDS[selectedCaseType] : {}, [selectedCaseType])

  // Party labels based on case type
  const partyLabels = caseTypeConfig?.partyLabels || { petitioner: 'Petitioner', respondent: 'Respondent' }

  // --- Cascading dropdown state ---
  const [filteredCourts, setFilteredCourts] = useState(ALL_COURTS)
  const [filteredPoliceStations, setFilteredPoliceStations] = useState(ALL_POLICE_STATIONS)
  const [caseTypeStatutes, setCaseTypeStatutes] = useState([])

  // Update filtered courts/police stations when location changes
  useMemo(() => {
    if (form.court_location) {
      setFilteredCourts(getCourtsForLocation(form.court_location))
      setFilteredPoliceStations(getPoliceStationsForLocation(form.court_location))
    } else {
      setFilteredCourts(ALL_COURTS)
      setFilteredPoliceStations(ALL_POLICE_STATIONS)
    }
  }, [form.court_location])

  // Update case-type specific statutes when case type changes
  useMemo(() => {
    if (selectedCaseType) {
      setCaseTypeStatutes(CASE_TYPE_STATUTES[selectedCaseType] || [])
    } else {
      setCaseTypeStatutes([])
    }
  }, [selectedCaseType])

  // --- Validation ---
  const validateStep = () => {
    const newErrors = {}
    let hasError = false

    if (step === 1) {
      if (!selectedCaseType) {
        newErrors.case_type = 'Please select a case type'
        hasError = true
      }
    }

    if (step === 2) {
      if (!form.court_name) { newErrors.court_name = 'Court name is required'; hasError = true }
      if (!form.court_location) { newErrors.court_location = 'Location is required'; hasError = true }
      if (!form.police_station) { newErrors.police_station = 'Police station is required (nearest to the incident/court)'; hasError = true }
    }

    if (step === 3) {
      if (!form.petitioner_name) { newErrors.petitioner_name = `${partyLabels.petitioner} name is required`; hasError = true }
      if (!form.petitioner_address) { newErrors.petitioner_address = `${partyLabels.petitioner} address is required`; hasError = true }
      if (!form.respondent_name) { newErrors.respondent_name = `${partyLabels.respondent} name is required`; hasError = true }
      
      // Case-specific required fields in step 3
      Object.entries(specificFields).forEach(([key, field]) => {
        if (field.required && field.step === 3 && !form[key]) {
          newErrors[key] = `${field.label} is required`
          hasError = true
        }
      })
    }

    if (step === 4) {
      if (!form.case_description || form.case_description.length < 50) {
        newErrors.case_description = 'Case narrative must be at least 50 characters'
        hasError = true
      }
      if (!form.relief_sought) { newErrors.relief_sought = 'Relief sought is required'; hasError = true }
      
      Object.entries(specificFields).forEach(([key, field]) => {
        if (field.required && field.step === 4 && !form[key]) {
          newErrors[key] = `${field.label} is required`
          hasError = true
        }
      })
    }

    setErrors(newErrors)
    return !hasError
  }

  const nextStep = () => {
    if (validateStep()) setStep(s => Math.min(s + 1, 5))
  }

  const prevStep = () => setStep(s => Math.max(s - 1, 1))

  const handleChange = (key) => (value) => {
    setForm(f => ({ ...f, [key]: value }))
    setTouched(t => ({ ...t, [key]: true }))
    if (errors[key]) setErrors(e => ({ ...e, [key]: null }))
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!validateStep()) return
    
    setLoading(true)
    const loadToast = toast.loading('Generating draft...')

    try {
      // Build case description with all structured data
      const details = []
      
      // Add case-specific details
      if (selectedCaseType === 'Criminal') {
        form.fir_number && details.push(`FIR No: ${form.fir_number}`)
        form.accused_details && details.push(`Accused Details: ${form.accused_details}`)
        form.police_station && details.push(`Police Station: ${form.police_station}`)
      } else if (selectedCaseType === 'Civil') {
        form.contract_date && details.push(`Contract Date: ${form.contract_date}`)
        form.contract_value && details.push(`Contract Value: ₹${form.contract_value}`)
        form.defendant_details && details.push(`Defendant Details: ${form.defendant_details}`)
      } else if (selectedCaseType === 'Family Law') {
        form.marriage_date && details.push(`Marriage Date: ${form.marriage_date}`)
        form.separation_date && details.push(`Separation Date: ${form.separation_date}`)
        form.children_details && details.push(`Children: ${form.children_details}`)
        form.relief_type && details.push(`Relief Type: ${form.relief_type}`)
        form.respondent_details && details.push(`Respondent Details: ${form.respondent_details}`)
      } else if (selectedCaseType === 'Labour / Employment') {
        form.joining_date && details.push(`Joining Date: ${form.joining_date}`)
        form.termination_date && details.push(`Termination Date: ${form.termination_date}`)
        form.designation && details.push(`Designation: ${form.designation}`)
        form.salary && details.push(`Salary: ₹${form.salary}/month`)
        form.employer_details && details.push(`Employer Details: ${form.employer_details}`)
        form.dispute_type && details.push(`Dispute Type: ${form.dispute_type}`)
      } else if (selectedCaseType === 'Constitutional') {
        form.authority && details.push(`Respondent Authority: ${form.authority}`)
        form.writ_type && details.push(`Writ Type: ${form.writ_type}`)
        form.fundamental_rights && details.push(`Rights Violated: ${form.fundamental_rights}`)
      } else if (selectedCaseType === 'Property Dispute') {
        form.property_address && details.push(`Property Address: ${form.property_address}`)
        form.property_type && details.push(`Property Type: ${form.property_type}`)
        form.ownership_basis && details.push(`Ownership Basis: ${form.ownership_basis}`)
        form.defendant_details && details.push(`Defendant Details: ${form.defendant_details}`)
      }

      const caseDescription = details.length
        ? `${form.case_description}\n\nStructured Particulars:\n${details.join('\n')}`
        : form.case_description

      await casesAPI.submit({
        title: `${form.petitioner_name} vs ${form.respondent_name}`,
        jurisdiction: form.court_location,
        petitioner_name: form.petitioner_name,
        respondent_name: form.respondent_name,
        incident_date: form.incident_date,
        relief_sought: form.relief_sought,
        case_description: caseDescription,
        sections_alleged: form.sections_alleged,
      })
      
      toast.success('Case draft created successfully!', { id: loadToast })
      navigate('/cases')
    } catch (err) {
      toast.error(getErrorMessage(err, 'Failed to create case'), { id: loadToast })
    } finally {
      setLoading(false)
    }
  }

  // --- Step Definitions ---
  const getSteps = () => {
    if (!selectedCaseType) {
      return [
        { icon: Scale, label: 'Case Type' },
        { icon: Gavel, label: 'Jurisdiction' },
        { icon: Users, label: 'Parties' },
        { icon: FileText, label: 'Details' },
        { icon: Search, label: 'Review' },
      ]
    }
    return [
      { icon: Scale, label: 'Case Type' },
      { icon: Gavel, label: 'Jurisdiction' },
      { icon: Users, label: 'Parties' },
      { icon: FileText, label: 'Case Details' },
      { icon: Search, label: 'Review' },
    ]
  }

  const steps = getSteps()
  const totalSteps = steps.length

  // --- Render Steps ---
  const renderStep1 = () => (
    <div className="form-step animate-fade-up">
      <div className="form-step-header">
        <h2>Select Case Category</h2>
        <p>Choose the legal domain that best describes your matter</p>
      </div>
      <div className="case-type-grid">
        {CASE_TYPES.map(type => (
          <CaseTypeCard 
            key={type.id} 
            type={type} 
            selected={selectedCaseType === type.id} 
            onClick={setSelectedCaseType} 
          />
        ))}
      </div>
      {errors.case_type && <div className="form-error">{errors.case_type}</div>}
    </div>
  )

  const renderStep2 = () => (
    <div className="form-step animate-fade-up">
      <div className="form-step-header">
        <h2>Court & Jurisdiction</h2>
        <p>Select location first — courts & police stations will filter automatically</p>
      </div>
      <div className="form-grid-2">
        <DynamicInput 
          field={{ ...JURISDICTION_FIELDS.court_location, datalistOptions: LOCATION_DATA.map(d => d.location) }}
          value={form.court_location} 
          onChange={handleChange('court_location')} 
          error={errors.court_location} 
        />
        <DynamicInput 
          field={{ ...JURISDICTION_FIELDS.court_name, required: true, datalistOptions: filteredCourts }}
          value={form.court_name} 
          onChange={handleChange('court_name')} 
          error={errors.court_name} 
        />
        <DynamicInput 
          field={{ ...JURISDICTION_FIELDS.police_station, required: true, datalistOptions: filteredPoliceStations }}
          value={form.police_station} 
          onChange={handleChange('police_station')} 
          error={errors.police_station} 
        />
        <DynamicInput 
          field={{ ...JURISDICTION_FIELDS.sections_alleged, datalistOptions: caseTypeStatutes }}
          value={form.sections_alleged} 
          onChange={handleChange('sections_alleged')} 
          error={errors.sections_alleged} 
        />
      </div>
    </div>
  )

  const renderStep3 = () => (
    <div className="form-step animate-fade-up">
      <div className="form-step-header">
        <h2>Parties Involved</h2>
        <p>Details of {partyLabels.petitioner} and {partyLabels.respondent}</p>
      </div>
      
      <div className="form-cols">
        <div className="form-party">
          <h3>{partyLabels.petitioner}</h3>
          <DynamicInput 
            field={{ label: 'Legal Name', required: true }}
            value={form.petitioner_name} 
            onChange={handleChange('petitioner_name')} 
            error={errors.petitioner_name} 
          />
          <DynamicInput 
            field={{ label: 'Address', type: 'textarea', required: true }}
            value={form.petitioner_address} 
            onChange={handleChange('petitioner_address')} 
            error={errors.petitioner_address} 
          />
          <DynamicInput 
            field={{ label: 'Phone', required: false }}
            value={form.petitioner_phone} 
            onChange={handleChange('petitioner_phone')} 
          />
          <DynamicInput 
            field={{ label: 'Email', required: false }}
            value={form.petitioner_email} 
            onChange={handleChange('petitioner_email')} 
          />
        </div>

        <div className="form-party">
          <h3>{partyLabels.respondent}</h3>
          <DynamicInput 
            field={{ label: 'Full Name', required: true }}
            value={form.respondent_name} 
            onChange={handleChange('respondent_name')} 
            error={errors.respondent_name} 
          />
          
          {/* Case-specific respondent fields */}
          {selectedCaseType === 'Family Law' && (
            <DynamicInput 
              field={{ label: 'Respondent Details', type: 'textarea', required: true }}
              value={form.respondent_details} 
              onChange={handleChange('respondent_details')} 
              error={errors.respondent_details} 
            />
          )}
          {selectedCaseType === 'Civil' && (
            <DynamicInput 
              field={{ label: 'Defendant Details', type: 'textarea', required: true }}
              value={form.defendant_details} 
              onChange={handleChange('defendant_details')} 
              error={errors.defendant_details} 
            />
          )}
          {selectedCaseType === 'Labour / Employment' && (
            <DynamicInput 
              field={{ label: 'Employer/Management Details', type: 'textarea', required: true }}
              value={form.employer_details} 
              onChange={handleChange('employer_details')} 
              error={errors.employer_details} 
            />
          )}
          {selectedCaseType === 'Property Dispute' && (
            <DynamicInput 
              field={{ label: 'Defendant/Opposite Party Details', type: 'textarea', required: true }}
              value={form.defendant_details} 
              onChange={handleChange('defendant_details')} 
              error={errors.defendant_details} 
            />
          )}
        </div>
      </div>

      {/* Incident Date & Case-specific fields for step 3 */}
      <div className="form-grid-2" style={{ marginTop: '1.5rem' }}>
        <DynamicInput 
          field={{ label: 'Incident/Key Date', type: 'date', required: true }}
          value={form.incident_date} 
          onChange={handleChange('incident_date')} 
          error={errors.incident_date} 
        />
        
        {selectedCaseType === 'Criminal' && (
          <>
            <DynamicInput 
              field={{ label: 'FIR Number', required: false }}
              value={form.fir_number} 
              onChange={handleChange('fir_number')} 
            />
            <DynamicInput 
              field={{ label: 'Accused Details', type: 'textarea', required: true }}
              value={form.accused_details} 
              onChange={handleChange('accused_details')} 
              error={errors.accused_details} 
            />
          </>
        )}
        
        {selectedCaseType === 'Civil' && (
          <>
            <DynamicInput 
              field={{ label: 'Contract Date', type: 'date', required: false }}
              value={form.contract_date} 
              onChange={handleChange('contract_date')} 
            />
            <DynamicInput 
              field={{ label: 'Contract Value (₹)', type: 'number', required: false }}
              value={form.contract_value} 
              onChange={handleChange('contract_value')} 
            />
          </>
        )}
        
        {selectedCaseType === 'Family Law' && (
          <>
            <DynamicInput 
              field={{ label: 'Marriage Date', type: 'date', required: true }}
              value={form.marriage_date} 
              onChange={handleChange('marriage_date')} 
              error={errors.marriage_date} 
            />
            <DynamicInput 
              field={{ label: 'Separation Date', type: 'date', required: false }}
              value={form.separation_date} 
              onChange={handleChange('separation_date')} 
            />
          </>
        )}
        
        {selectedCaseType === 'Labour / Employment' && (
          <>
            <DynamicInput 
              field={{ label: 'Joining Date', type: 'date', required: true }}
              value={form.joining_date} 
              onChange={handleChange('joining_date')} 
              error={errors.joining_date} 
            />
            <DynamicInput 
              field={{ label: 'Termination Date', type: 'date', required: false }}
              value={form.termination_date} 
              onChange={handleChange('termination_date')} 
            />
          </>
        )}
        
        {selectedCaseType === 'Constitutional' && (
          <>
            <DynamicInput 
              field={{ label: 'Respondent Authority', required: true }}
              value={form.authority} 
              onChange={handleChange('authority')} 
              error={errors.authority} 
            />
            <DynamicInput 
              field={{ label: 'Writ Type', type: 'select', options: CASE_TYPE_FIELDS['Constitutional'].writType.options, required: true }}
              value={form.writ_type} 
              onChange={handleChange('writ_type')} 
              error={errors.writ_type} 
            />
          </>
        )}
        
        {selectedCaseType === 'Property Dispute' && (
          <>
            <DynamicInput 
              field={{ label: 'Property Address', type: 'textarea', required: true }}
              value={form.property_address} 
              onChange={handleChange('property_address')} 
              error={errors.property_address} 
            />
            <DynamicInput 
              field={{ label: 'Property Type', type: 'select', options: CASE_TYPE_FIELDS['Property Dispute'].propertyType.options, required: true }}
              value={form.property_type} 
              onChange={handleChange('property_type')} 
              error={errors.property_type} 
            />
          </>
        )}
      </div>
    </div>
  )

  const renderStep4 = () => (
    <div className="form-step animate-fade-up">
      <div className="form-step-header">
        <h2>Case Narrative & Relief</h2>
        <p>Detailed facts for the AI engine</p>
      </div>
      
      <DynamicInput 
        field={{ label: 'Case Narrative / Facts', type: 'textarea', required: true, minChars: 50, placeholder: 'Describe the complete facts of the case chronologically...' }}
        value={form.case_description} 
        onChange={handleChange('case_description')} 
        error={errors.case_description} 
      />
      
      <DynamicInput 
        field={{ label: 'Relief Sought', required: true, hint: 'What do you want the court to order?' }}
        value={form.relief_sought} 
        onChange={handleChange('relief_sought')} 
        error={errors.relief_sought} 
      />

      {/* Case-specific fields for step 4 */}
      {selectedCaseType === 'Family Law' && (
        <>
          <DynamicInput 
            field={{ label: 'Children Details', type: 'textarea', required: false }}
            value={form.children_details} 
            onChange={handleChange('children_details')} 
          />
          <DynamicInput 
            field={{ label: 'Primary Relief Type', type: 'select', options: CASE_TYPE_FIELDS['Family Law'].reliefType.options, required: true }}
            value={form.relief_type} 
            onChange={handleChange('relief_type')} 
            error={errors.relief_type} 
          />
        </>
      )}
      
      {selectedCaseType === 'Labour / Employment' && (
        <>
          <DynamicInput 
            field={{ label: 'Designation/Post', required: true }}
            value={form.designation} 
            onChange={handleChange('designation')} 
            error={errors.designation} 
          />
          <DynamicInput 
            field={{ label: 'Last Drawn Salary (₹/month)', type: 'number', required: true }}
            value={form.salary} 
            onChange={handleChange('salary')} 
            error={errors.salary} 
          />
          <DynamicInput 
            field={{ label: 'Nature of Dispute', type: 'select', options: CASE_TYPE_FIELDS['Labour / Employment'].disputeType.options, required: true }}
            value={form.dispute_type} 
            onChange={handleChange('dispute_type')} 
            error={errors.dispute_type} 
          />
        </>
      )}
      
      {selectedCaseType === 'Constitutional' && (
        <DynamicInput 
          field={{ label: 'Fundamental Rights Violated', type: 'textarea', required: true }}
          value={form.fundamental_rights} 
          onChange={handleChange('fundamental_rights')} 
          error={errors.fundamental_rights} 
        />
      )}
      
      {selectedCaseType === 'Property Dispute' && (
        <>
          <DynamicInput 
            field={{ label: 'Ownership Basis (Sale Deed, Will, Inheritance, etc.)', type: 'textarea', required: true }}
            value={form.ownership_basis} 
            onChange={handleChange('ownership_basis')} 
            error={errors.ownership_basis} 
          />
        </>
      )}
    </div>
  )

  const renderStep5 = () => (
    <div className="form-step animate-fade-up">
      <div className="form-step-header">
        <h2>Review & Generate</h2>
        <p>Verify all details before generating the draft</p>
      </div>
      
      <div className="review-summary">
        <div className="review-section">
          <h4>Case Type</h4>
          <p>{caseTypeConfig?.label || 'Not selected'}</p>
        </div>
        <div className="review-section">
          <h4>Jurisdiction</h4>
          <p>{form.court_name}, {form.court_location}</p>
        </div>
        <div className="review-section">
          <h4>Parties</h4>
          <p>{partyLabels.petitioner}: {form.petitioner_name}</p>
          <p>{partyLabels.respondent}: {form.respondent_name}</p>
        </div>
        <div className="review-section">
          <h4>Incident Date</h4>
          <p>{form.incident_date || 'Not provided'}</p>
        </div>
        <div className="review-section full-width">
          <h4>Relief Sought</h4>
          <p>{form.relief_sought || 'Not provided'}</p>
        </div>
        <div className="review-section full-width">
          <h4>Case Narrative Preview</h4>
          <p className="narrative-preview">{form.case_description?.substring(0, 300) || 'Not provided'}{form.case_description?.length > 300 ? '...' : ''}</p>
        </div>
      </div>
    </div>
  )

  const renderCurrentStep = () => {
    switch (step) {
      case 1: return renderStep1()
      case 2: return renderStep2()
      case 3: return renderStep3()
      case 4: return renderStep4()
      case 5: return renderStep5()
      default: return null
    }
  }

  return (
    <Layout>
      <div className="page-wrap-md">
        <header className="page-header-center">
          <h1>Initialize New Draft</h1>
          <p>Select your case category and fill in the details to generate an AI-powered legal draft.</p>
          <p>
            Prefer talking it through?{' '}
            <Link to="/cases/aichat" className="empty-link">
              Try chat mode
            </Link>
          </p>
        </header>

        <StepIndicator currentStep={step} totalSteps={totalSteps} steps={steps} />

        <div className="case-form-card">
          <form onSubmit={handleSubmit} className="form-step" style={{ flex: 1 }}>
            {renderCurrentStep()}

            <div className="form-actions">
              <button
                type="button"
                onClick={prevStep}
                disabled={step === 1}
                className={`btn-step-prev ${step === 1 ? 'btn-step-prev--hidden' : ''}`}
              >
                <ChevronLeft size={18} /> Previous
              </button>

              {step < totalSteps ? (
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