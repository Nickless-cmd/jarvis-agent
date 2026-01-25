import { Navigate, useLocation } from 'react-router-dom'
import { ReactNode } from 'react'
import { useChat } from '../../contexts/ChatContext'

type Props = { children: ReactNode }

export default function RequireAdmin({ children }: Props) {
  const { profile, profileLoading } = useChat()
  const { pathname } = useLocation()

  if (profileLoading) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <div className="text-sm text-neutral-400">Loader profil…</div>
      </div>
    )
  }

  if (!profile?.is_admin) {
    return <Navigate to="/" state={{ from: pathname }} replace />
  }

  return <>{children}</>
}
