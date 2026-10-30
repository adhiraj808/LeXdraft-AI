import { useState, useEffect } from 'react'
import { casesAPI } from '../../services/api'
import { Icon } from './Icons'

/**
 * Dual Model Selector for Chat Interface
 * Allows user to select Primary and Fallback models
 */
export function ModelSelector({ onModelsChange, initialPrimary, initialFallback }) {
  const [models, setModels] = useState([])
  const [primaryModel, setPrimaryModel] = useState(initialPrimary || 'groq')
  const [fallbackModel, setFallbackModel] = useState(initialFallback || 'template')
  const [showPrimaryDropdown, setShowPrimaryDropdown] = useState(false)
  const [showFallbackDropdown, setShowFallbackDropdown] = useState(false)

  // Fetch available models
  useEffect(() => {
    const fetchModels = async () => {
      try {
        const res = await casesAPI.getModels()
        if (res.data && res.data.models) {
          setModels(res.data.models)
          // Set defaults if not already set
          if (!initialPrimary && res.data.models.length > 0) {
            setPrimaryModel(res.data.models[0].id)
          }
          if (!initialFallback && res.data.models.length > 1) {
            setFallbackModel(res.data.models[1].id)
          }
        }
      } catch (e) {
        console.warn('Failed to fetch models:', e)
      }
    }
    fetchModels()
  }, [initialPrimary, initialFallback])

  const handlePrimaryChange = (modelId) => {
    if (modelId === fallbackModel) {
      // Swap fallback to previous primary
      setFallbackModel(primaryModel)
    }
    setPrimaryModel(modelId)
    setShowPrimaryDropdown(false)
    onModelsChange?.({ primary: modelId, fallback: fallbackModel })
  }

  const handleFallbackChange = (modelId) => {
    if (modelId === primaryModel) {
      // Swap primary to previous fallback
      setPrimaryModel(fallbackModel)
    }
    setFallbackModel(modelId)
    setShowFallbackDropdown(false)
    onModelsChange?.({ primary: primaryModel, fallback: modelId })
  }

  const getModelLabel = (modelId) => {
    return models.find(m => m.id === modelId)?.label || modelId
  }

  const getModelProvider = (modelId) => {
    return models.find(m => m.id === modelId)?.provider || ''
  }

  return (
    <div className="model-selector-dual">
      <div className="model-selector-row">
        <div className="model-slot">
          <label className="model-slot-label">
            <Icon name="Cpu" size={14} />
            <span>Primary Model</span>
          </label>
          <div className="model-dropdown">
            <button
              className="model-dropdown-trigger"
              type="button"
              onClick={() => setShowPrimaryDropdown(!showPrimaryDropdown)}
              aria-expanded={showPrimaryDropdown}
              aria-haspopup="listbox"
            >
              <span className="model-dropdown-label">{getModelLabel(primaryModel)}</span>
              <span className="model-dropdown-provider">{getModelProvider(primaryModel)}</span>
              <Icon name={showPrimaryDropdown ? 'ChevronUp' : 'ChevronDown'} size={14} />
            </button>
            {showPrimaryDropdown && (
              <ul className="model-dropdown-list" role="listbox">
                {models.map((model) => (
                  <li
                    key={model.id}
                    role="option"
                    aria-selected={primaryModel === model.id}
                    onClick={() => handlePrimaryChange(model.id)}
                    className={`model-dropdown-item ${primaryModel === model.id ? 'selected' : ''} ${fallbackModel === model.id ? 'fallback-occupied' : ''}`}
                  >
                    <span className="model-item-label">{model.label}</span>
                    <span className="model-item-provider">{model.provider}</span>
                    {fallbackModel === model.id && <span className="fallback-badge">Fallback</span>}
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>

        <div className="model-swap">
          <button
            type="button"
            className="model-swap-btn"
            onClick={() => {
              const temp = primaryModel
              setPrimaryModel(fallbackModel)
              setFallbackModel(temp)
              onModelsChange?.({ primary: fallbackModel, fallback: temp })
            }}
            title="Swap primary and fallback"
            aria-label="Swap primary and fallback models"
          >
            <Icon name="RefreshCw" size={16} />
          </button>
        </div>

        <div className="model-slot">
          <label className="model-slot-label">
            <Icon name="Shield" size={14} />
            <span>Fallback Model</span>
          </label>
          <div className="model-dropdown">
            <button
              className="model-dropdown-trigger"
              type="button"
              onClick={() => setShowFallbackDropdown(!showFallbackDropdown)}
              aria-expanded={showFallbackDropdown}
              aria-haspopup="listbox"
            >
              <span className="model-dropdown-label">{getModelLabel(fallbackModel)}</span>
              <span className="model-dropdown-provider">{getModelProvider(fallbackModel)}</span>
              <Icon name={showFallbackDropdown ? 'ChevronUp' : 'ChevronDown'} size={14} />
            </button>
            {showFallbackDropdown && (
              <ul className="model-dropdown-list" role="listbox">
                {models.map((model) => (
                  <li
                    key={model.id}
                    role="option"
                    aria-selected={fallbackModel === model.id}
                    onClick={() => handleFallbackChange(model.id)}
                    className={`model-dropdown-item ${fallbackModel === model.id ? 'selected' : ''} ${primaryModel === model.id ? 'primary-occupied' : ''}`}
                  >
                    <span className="model-item-label">{model.label}</span>
                    <span className="model-item-provider">{model.provider}</span>
                    {primaryModel === model.id && <span className="primary-badge">Primary</span>}
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

export default ModelSelector