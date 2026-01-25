import { NavLink, Outlet } from 'react-router-dom'

const tabs = [
  { to: '/admin/dashboard', label: 'Dashboard' },
  { to: '/admin/users', label: 'Users' },
  { to: '/admin/sessions', label: 'Sessions' },
]

export default function AdminLayout() {
  return (
    <div className="flex-1 min-h-0 flex flex-col">
      <div className="border-b border-neutral-800 px-6 py-4 flex items-center gap-6">
        <h1 className="text-xl font-semibold">Admin</h1>
        <nav className="flex items-center gap-3 text-sm">
          {tabs.map((t) => (
            <NavLink
              key={t.to}
              to={t.to}
              className={({ isActive }) =>
                [
                  "px-3 py-1.5 rounded-lg border",
                  isActive
                    ? "border-emerald-500 bg-emerald-500/10 text-emerald-100"
                    : "border-transparent text-neutral-300 hover:bg-neutral-800",
                ].join(" ")
              }
            >
              {t.label}
            </NavLink>
          ))}
        </nav>
      </div>
      <div className="flex-1 overflow-auto">
        <Outlet />
      </div>
    </div>
  )
}
