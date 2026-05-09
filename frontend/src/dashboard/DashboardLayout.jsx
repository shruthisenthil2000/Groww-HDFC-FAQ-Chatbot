import { useState, useEffect, useRef, useCallback, useId } from 'react'
import { IconMenu, IconSearch, IconBell, IconClose } from '../ui/icons'
import { SIDEBAR_ITEMS } from './dashboardNav'
import { DashboardWorkspace } from './DashboardWorkspace'
import { formatNavSynced } from '../utils/navDisplay'

const MOCK_NOTIFICATIONS = [
  { id: '1', title: 'SIP processed', body: 'HDFC Mid Cap · ₹15,000 · 08 May 2026', unread: true },
  { id: '2', title: 'Statement ready', body: 'Consolidated CAS for April is available', unread: true },
  { id: '3', title: 'NAV update', body: 'Daily NAV published for your watchlist funds', unread: false },
]

function BrandMark() {
  const gid = useId().replace(/:/g, '')
  const gradId = `growwBrandGrad-${gid}`
  return (
    <div className="dash-brand-mark" aria-hidden>
      <svg viewBox="0 0 32 32" className="dash-brand-svg" fill="none">
        <rect width="32" height="32" rx="9" fill={`url(#${gradId})`} />
        <path
          d="M9 22V12h3v10H9zm5.5-4V8h3v10h-3zM20 22v-6h3v6h-3z"
          fill="rgba(255,255,255,0.95)"
        />
        <defs>
          <linearGradient id={gradId} x1="4" y1="28" x2="28" y2="4" gradientUnits="userSpaceOnUse">
            <stop stopColor="var(--accent-primary)" />
            <stop offset="1" stopColor="var(--accent-primary-hover)" />
          </linearGradient>
        </defs>
      </svg>
    </div>
  )
}

export function DashboardLayout({
  navSection,
  onNavigate,
  funds,
  allFunds = funds,
  corpusFundCount,
  selectedFundId,
  onSelectFund,
  onFundInsightClick,
  onAskAssistant,
  searchQuery,
  setSearchQuery,
  navMeta,
  navLoading,
  children,
}) {
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false)
  const [notifOpen, setNotifOpen] = useState(false)
  const [profileOpen, setProfileOpen] = useState(false)

  const notifWrapRef = useRef(null)
  const profileWrapRef = useRef(null)

  const closePopovers = useCallback(() => {
    setNotifOpen(false)
    setProfileOpen(false)
  }, [])

  useEffect(() => {
    const onDown = (e) => {
      const t = e.target
      if (notifWrapRef.current?.contains(t)) return
      if (profileWrapRef.current?.contains(t)) return
      setNotifOpen(false)
      setProfileOpen(false)
    }
    const onKey = (e) => {
      if (e.key === 'Escape') closePopovers()
    }
    document.addEventListener('mousedown', onDown)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('mousedown', onDown)
      document.removeEventListener('keydown', onKey)
    }
  }, [closePopovers])

  const unreadCount = MOCK_NOTIFICATIONS.filter((n) => n.unread).length

  return (
    <div className="dash-root">
      <header className="dash-topnav">
        <button
          type="button"
          className="dash-icon-btn dash-nav-toggle"
          aria-label={sidebarCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          aria-expanded={!sidebarCollapsed}
          onClick={() => setSidebarCollapsed((c) => !c)}
        >
          <IconMenu className="dash-icon" />
        </button>

        <div className="dash-nav-brand">
          <BrandMark />
          <div className="dash-brand-text">
            <span className="dash-brand-title">Groww HDFC FAQ</span>
            <span className="dash-brand-tagline">AI-powered mutual fund knowledge workspace</span>
          </div>
        </div>

        <form
          className="dash-nav-search-form"
          role="search"
          onSubmit={(e) => e.preventDefault()}
        >
          <label className="dash-nav-search" htmlFor="dash-global-search">
            <IconSearch className="dash-search-icon" aria-hidden />
            <input
              id="dash-global-search"
              type="search"
              className="dash-nav-search-input"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') e.preventDefault()
              }}
              placeholder="Search funds, ISIN, scheme code, benchmark…"
              autoComplete="off"
              aria-label="Search funds"
            />
            {searchQuery ? (
              <button
                type="button"
                className="dash-search-clear"
                aria-label="Clear search"
                onClick={() => setSearchQuery('')}
              >
                <IconClose className="dash-search-clear-icon" />
              </button>
            ) : null}
          </label>
        </form>

        <div className="dash-nav-actions">
          <div className="dash-pop-wrap" ref={notifWrapRef}>
            <button
              type="button"
              className="dash-icon-btn dash-icon-btn--notif"
              aria-label="Notifications"
              aria-expanded={notifOpen}
              onClick={() => {
                setNotifOpen((o) => !o)
                setProfileOpen(false)
              }}
            >
              <IconBell className="dash-icon" />
              {unreadCount > 0 && <span className="dash-notif-dot" aria-hidden />}
            </button>
            {notifOpen && (
              <div className="dash-popover dash-popover--notif" role="dialog" aria-label="Notifications">
                <div className="dash-popover-head">
                  <span>Notifications</span>
                  {unreadCount > 0 && (
                    <span className="dash-popover-badge">{unreadCount} new</span>
                  )}
                </div>
                <ul className="dash-notif-list">
                  {MOCK_NOTIFICATIONS.map((n) => (
                    <li key={n.id} className={n.unread ? 'is-unread' : ''}>
                      <span className="dash-notif-title">{n.title}</span>
                      <span className="dash-notif-body">{n.body}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>

          <div className="dash-pop-wrap" ref={profileWrapRef}>
            <button
              type="button"
              className="dash-avatar-btn"
              aria-label="Account menu"
              aria-expanded={profileOpen}
              onClick={() => {
                setProfileOpen((o) => !o)
                setNotifOpen(false)
              }}
            >
              <span className="dash-avatar-inner" aria-hidden>SK</span>
            </button>
            {profileOpen && (
              <div className="dash-popover dash-popover--profile" role="dialog" aria-label="Account">
                <div className="dash-profile-top">
                  <span className="dash-profile-avatar" aria-hidden>SK</span>
                  <div>
                    <div className="dash-profile-name">Demo Investor</div>
                    <div className="dash-profile-email">investor@example.com</div>
                  </div>
                </div>
                <div className="dash-profile-divider" />
                <button type="button" className="dash-profile-link">
                  Profile &amp; KYC
                </button>
                <button type="button" className="dash-profile-link">
                  Settings
                </button>
                <button type="button" className="dash-profile-link dash-profile-link--muted">
                  Sign out (demo)
                </button>
              </div>
            )}
          </div>
        </div>
      </header>

      <div className="dash-stats-sync" aria-live="polite">
        {navLoading ? (
          <span className="dash-sync-skel dw-skel-line" />
        ) : (
          <>
            <span className="dash-sync-label">
              Last synced: {formatNavSynced(navMeta?.lastSyncedAt)}
            </span>
            {navMeta?.usingCachedData ? (
              <span className="dash-cache-badge" title="Live NAV refresh unavailable or data is stale; showing cached values.">
                Using cached market data
              </span>
            ) : null}
          </>
        )}
      </div>

      <div className="dash-below-header">
        <aside
          className={`dash-sidebar ${sidebarCollapsed ? 'dash-sidebar--collapsed' : ''}`}
          aria-label="Main navigation"
        >
          <nav className="dash-side-nav">
            {SIDEBAR_ITEMS.map(({ id, Icon, label, accent }) => {
              const active = navSection === id
              return (
                <button
                  key={id}
                  type="button"
                  className={`dash-side-item ${active ? 'is-active' : ''} ${accent ? 'is-accent' : ''}`}
                  aria-current={active ? 'page' : undefined}
                  title={sidebarCollapsed ? label : undefined}
                  onClick={() => onNavigate(id)}
                >
                  <Icon className="dash-side-icon" />
                  <span>{label}</span>
                </button>
              )
            })}
          </nav>
        </aside>

        <div className="dash-main-and-assistant">
          <main className="dash-main-column">
            <div className="dash-workspace-scroll">
              <DashboardWorkspace
                section={navSection}
                funds={funds}
                allFunds={allFunds}
                corpusFundCount={corpusFundCount}
                selectedFundId={selectedFundId}
                onSelectFund={onSelectFund}
                onFundInsightClick={onFundInsightClick}
                onAskAssistant={onAskAssistant}
                navMeta={navMeta}
                navLoading={navLoading}
              />
            </div>
          </main>

          <aside className="dash-assistant-dock" aria-label="Assistant">
            {children}
          </aside>
        </div>
      </div>
    </div>
  )
}
