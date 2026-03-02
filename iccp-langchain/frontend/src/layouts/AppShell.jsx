import { useEffect, useState } from 'react'
import { Outlet } from 'react-router-dom'
import Sidebar from '../components/Sidebar'
import TopBar from '../components/TopBar'

const SIDEBAR_COLLAPSED_KEY = 'iccp:sidebar-collapsed'

function AppShell() {
  const [collapsed, setCollapsed] = useState(() => {
    try { return localStorage.getItem(SIDEBAR_COLLAPSED_KEY) === 'true' } catch { return false }
  })

  useEffect(() => {
    const onStorage = () => {
      try {
        setCollapsed(localStorage.getItem(SIDEBAR_COLLAPSED_KEY) === 'true')
      } catch { /* ignore */ }
    }
    window.addEventListener('sidebar-toggle', onStorage)
    return () => window.removeEventListener('sidebar-toggle', onStorage)
  }, [])

  return (
    <div className="min-h-screen bg-muted/30">
      <Sidebar onToggle={() => setCollapsed((p) => !p)} />
      <div
        className="transition-all duration-200 min-h-screen flex flex-col"
        style={{ marginLeft: collapsed ? 60 : 208 }}
      >
        <TopBar />
        <main className="flex-1 px-6 py-5 max-w-[1200px] mx-auto w-full">
          <Outlet />
        </main>
      </div>
    </div>
  )
}

export default AppShell
