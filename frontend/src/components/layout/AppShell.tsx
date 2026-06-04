import { Link, useLocation, Outlet, Navigate } from 'react-router-dom'
import { useAuthStore } from '../../stores/authStore'
import {
  LayoutDashboard, User, FileText, Calendar, Network,
  BarChart2, Zap, BrainCircuit, Settings, LogOut
} from 'lucide-react'
import { cn } from '../../lib/utils'

const navItems = [
  { to: '/dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { to: '/profile', label: 'Profile Builder', icon: User },
  { to: '/content', label: 'Content Studio', icon: FileText },
  { to: '/calendar', label: 'Calendar', icon: Calendar },
  { to: '/network', label: 'Network', icon: Network },
  { to: '/analytics', label: 'Analytics', icon: BarChart2 },
  { to: '/automation', label: 'Automation', icon: Zap },
  { to: '/learning', label: 'AI Learning', icon: BrainCircuit },
  { to: '/settings', label: 'Settings', icon: Settings },
]

export function AppShell() {
  const { isAuthenticated, logout, displayName } = useAuthStore()
  const location = useLocation()

  if (!isAuthenticated) return <Navigate to="/login" replace />

  return (
    <div className="flex h-screen bg-gray-50 overflow-hidden" style={{ textAlign: 'left', width: '100%', maxWidth: '100%', border: 'none' }}>
      {/* Sidebar */}
      <aside className="w-64 bg-white border-r border-gray-200 flex flex-col shrink-0">
        <div className="p-6 border-b border-gray-200">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 bg-linkedin-blue rounded-lg flex items-center justify-center">
              <Network className="w-5 h-5 text-white" />
            </div>
            <span className="font-semibold text-gray-900 text-sm">LinkedIn Manager</span>
          </div>
        </div>

        <nav className="flex-1 p-4 overflow-y-auto">
          <div className="space-y-1">
            {navItems.map(({ to, label, icon: Icon }) => (
              <Link
                key={to}
                to={to}
                className={cn(
                  'flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors',
                  location.pathname === to
                    ? 'bg-linkedin-light text-linkedin-blue'
                    : 'text-gray-600 hover:bg-gray-100 hover:text-gray-900'
                )}
              >
                <Icon className="w-4 h-4 shrink-0" />
                {label}
              </Link>
            ))}
          </div>
        </nav>

        <div className="p-4 border-t border-gray-200">
          <div className="flex items-center gap-3 mb-3">
            <div className="w-8 h-8 rounded-full bg-linkedin-blue flex items-center justify-center text-white text-xs font-medium">
              {displayName?.charAt(0)?.toUpperCase() || 'U'}
            </div>
            <span className="text-sm font-medium text-gray-900 truncate">{displayName}</span>
          </div>
          <button
            onClick={logout}
            className="flex items-center gap-2 text-sm text-gray-500 hover:text-red-600 transition-colors w-full"
          >
            <LogOut className="w-4 h-4" />
            Sign out
          </button>
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 overflow-y-auto">
        <Outlet />
      </main>
    </div>
  )
}
