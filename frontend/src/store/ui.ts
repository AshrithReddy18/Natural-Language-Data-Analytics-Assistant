import { create } from 'zustand'
import { persist } from 'zustand/middleware'

type Theme = 'dark' | 'light'

interface UIState {
  theme: Theme
  sidebarCollapsed: boolean
  mobileNavOpen: boolean
  dataSourceId: string | null
  /** SQL handed to the workbench from elsewhere (history, schema explorer, "open in workbench"). */
  workbenchSql: string
  setTheme: (theme: Theme) => void
  toggleSidebar: () => void
  setMobileNavOpen: (open: boolean) => void
  setDataSourceId: (id: string | null) => void
  setWorkbenchSql: (sql: string) => void
}

export const useUIStore = create<UIState>()(
  persist(
    (set) => ({
      theme: 'dark',
      sidebarCollapsed: false,
      mobileNavOpen: false,
      dataSourceId: null,
      workbenchSql: '',
      setTheme: (theme) => {
        document.documentElement.classList.toggle('dark', theme === 'dark')
        set({ theme })
      },
      toggleSidebar: () => set((s) => ({ sidebarCollapsed: !s.sidebarCollapsed })),
      setMobileNavOpen: (mobileNavOpen) => set({ mobileNavOpen }),
      setDataSourceId: (dataSourceId) => set({ dataSourceId }),
      setWorkbenchSql: (workbenchSql) => set({ workbenchSql }),
    }),
    {
      name: 'datapilot-ui',
      partialize: (s) => ({ theme: s.theme, sidebarCollapsed: s.sidebarCollapsed, dataSourceId: s.dataSourceId }),
    },
  ),
)
