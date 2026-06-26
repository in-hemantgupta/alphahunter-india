import { NavLink, Outlet } from 'react-router-dom'
import { LayoutDashboard, Globe, History, RefreshCw } from 'lucide-react'

const links = [
  { to: '/', icon: LayoutDashboard, label: 'Dashboard' },
  { to: '/universe', icon: Globe, label: 'Universe' },
  { to: '/scan-history', icon: History, label: 'Scan History' },
  { to: '/rebalancing', icon: RefreshCw, label: 'Rebalancing' },
]

export default function Layout() {
  return (
    <div className="min-h-screen bg-gray-900 text-white flex">
      <nav className="w-64 bg-gray-800 p-6 flex flex-col">
        <h1 className="text-xl font-bold mb-8">QuantumAlpha India</h1>
        <div className="space-y-2 flex-1">
          {links.map(({ to, icon: Icon, label }) => (
            <NavLink
              key={to}
              to={to}
              end={to === '/'}
              className={({ isActive }) =>
                `flex items-center gap-3 px-4 py-3 rounded-lg transition-colors ${
                  isActive ? 'bg-blue-600 text-white' : 'text-gray-400 hover:bg-gray-700 hover:text-white'
                }`
              }
            >
              <Icon className="w-5 h-5" />
              {label}
            </NavLink>
          ))}
        </div>
        <p className="text-xs text-gray-500 mt-8">Institutional-Grade Alpha Discovery</p>
      </nav>
      <main className="flex-1 p-8 overflow-auto">
        <Outlet />
      </main>
    </div>
  )
}
