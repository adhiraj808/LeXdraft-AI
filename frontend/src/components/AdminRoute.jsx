import { Navigate } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth'

export default function AdminRoute({ children }) {
  const { user, loading } = useAuth()
  
  if (loading) return (
    <div className="route-loading">
      <div className="spinner" />
    </div>
  )
  
  // Only allow access if user exists AND has admin role
  if (!user || user.role !== 'admin') {
    return <Navigate to="/dashboard" replace />
  }
  
  return children
}