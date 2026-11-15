import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Menu, Search, Bell, Sun, Moon, Building2, ChevronDown, LogOut, Check, Plus } from 'lucide-react';
import { useTheme } from '../../context/ThemeContext';
import { useAuth } from '../../context/AuthContext';

interface TopBarProps {
  title: string;
  onMenuToggle: () => void;
  alertCount: number;
}

export default function TopBar({ title, onMenuToggle, alertCount }: TopBarProps) {
  const { theme, toggleTheme } = useTheme();
  const { user, activeOrg, organizations, switchOrg, createOrg, logout } = useAuth();
  const [orgDropdownOpen, setOrgDropdownOpen] = useState(false);
  const [userMenuOpen, setUserMenuOpen] = useState(false);
  const [showNewOrgModal, setShowNewOrgModal] = useState(false);
  const [newOrgName, setNewOrgName] = useState('');

  const initials = user?.full_name
    ? user.full_name
        .split(' ')
        .map((p) => p[0])
        .join('')
        .toUpperCase()
        .slice(0, 2)
    : (user?.email?.slice(0, 2).toUpperCase() || 'DP');

  const handleCreateOrg = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newOrgName.trim()) return;
    try {
      const created = await createOrg(newOrgName.trim());
      await switchOrg(created.id);
      setNewOrgName('');
      setShowNewOrgModal(false);
      setOrgDropdownOpen(false);
    } catch (err: any) {
      alert(err.message || 'Failed to create organization');
    }
  };

  const roleBadgeColors: Record<string, string> = {
    admin: 'bg-rose-500/10 text-rose-400 border-rose-500/30',
    data_engineer: 'bg-indigo-500/10 text-indigo-400 border-indigo-500/30',
    analyst: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30',
    viewer: 'bg-zinc-500/10 text-zinc-400 border-zinc-500/30',
  };

  return (
    <header className="flex items-center gap-3 px-4 md:px-6 h-16 border-b border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 flex-shrink-0 z-20 transition-colors">
      {/* Mobile menu button */}
      <button
        onClick={onMenuToggle}
        className="md:hidden text-zinc-500 hover:text-zinc-900 dark:text-zinc-400 dark:hover:text-zinc-100 transition-colors"
      >
        <Menu size={20} />
      </button>

      {/* Page title */}
      <h1 className="text-zinc-900 dark:text-zinc-100 font-semibold text-base sm:text-lg flex-shrink-0">
        {title}
      </h1>

      {/* Organization Selector */}
      <div className="relative ml-1 sm:ml-3">
        <button
          onClick={() => setOrgDropdownOpen(!orgDropdownOpen)}
          className="flex items-center gap-2 px-2.5 py-1.5 rounded-lg bg-zinc-100 dark:bg-zinc-800/80 hover:bg-zinc-200 dark:hover:bg-zinc-800 border border-zinc-200 dark:border-zinc-700/60 text-xs font-medium text-zinc-700 dark:text-zinc-200 transition-colors cursor-pointer"
        >
          <Building2 size={13} className="text-indigo-500" />
          <span className="max-w-[120px] sm:max-w-[160px] truncate">
            {activeOrg?.name || 'Default Workspace'}
          </span>
          <ChevronDown size={12} className="text-zinc-400" />
        </button>

        {/* Org Dropdown */}
        {orgDropdownOpen && (
          <div className="absolute left-0 mt-2 w-56 rounded-xl bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 shadow-xl py-1.5 z-50">
            <div className="px-3 py-1.5 text-[10px] font-semibold text-zinc-400 uppercase tracking-wider">
              Workspaces & Tenants
            </div>
            {organizations.map((org) => {
              const isActive = activeOrg?.id === org.id;
              return (
                <button
                  key={org.id}
                  onClick={() => {
                    switchOrg(org.id);
                    setOrgDropdownOpen(false);
                  }}
                  className="w-full flex items-center justify-between px-3 py-1.5 text-xs text-left hover:bg-zinc-100 dark:hover:bg-zinc-800 text-zinc-700 dark:text-zinc-300 transition-colors"
                >
                  <span className="truncate">{org.name}</span>
                  {isActive && <Check size={13} className="text-indigo-500 shrink-0" />}
                </button>
              );
            })}
            <div className="border-t border-zinc-200 dark:border-zinc-800 my-1" />
            <button
              onClick={() => {
                setShowNewOrgModal(true);
                setOrgDropdownOpen(false);
              }}
              className="w-full flex items-center gap-2 px-3 py-1.5 text-xs text-indigo-600 dark:text-indigo-400 hover:bg-zinc-100 dark:hover:bg-zinc-800 font-medium transition-colors"
            >
              <Plus size={13} />
              <span>Create New Workspace</span>
            </button>
          </div>
        )}
      </div>

      {/* Search bar */}
      <div className="flex-1 max-w-xs md:max-w-md mx-auto hidden md:flex items-center gap-2 bg-zinc-100 dark:bg-zinc-800/60 border border-zinc-200 dark:border-zinc-700/80 rounded-lg px-3 py-1.5 group focus-within:border-indigo-500 transition-colors">
        <Search size={14} className="text-zinc-400 flex-shrink-0" />
        <input
          type="text"
          placeholder="Search pipelines, anomalies..."
          className="bg-transparent text-xs text-zinc-900 dark:text-zinc-100 placeholder-zinc-400 dark:placeholder-zinc-500 outline-none flex-1 min-w-0"
          readOnly
        />
        <kbd className="hidden lg:flex items-center gap-0.5 text-zinc-500 dark:text-zinc-400 text-[10px] bg-zinc-200 dark:bg-zinc-700 rounded px-1 py-0.5 font-mono">
          ⌘K
        </kbd>
      </div>

      {/* Right actions */}
      <div className="flex items-center gap-2 ml-auto">
        {/* Role Badge */}
        {user && (
          <span
            className={`hidden sm:inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-semibold border capitalize ${
              roleBadgeColors[user.role] || roleBadgeColors.viewer
            }`}
          >
            {user.role.replace('_', ' ')}
          </span>
        )}

        {/* Theme toggle */}
        <button
          onClick={toggleTheme}
          className="relative w-8 h-8 rounded-lg flex items-center justify-center text-zinc-600 dark:text-zinc-400 hover:text-zinc-900 dark:hover:text-zinc-100 hover:bg-zinc-100 dark:hover:bg-zinc-800 transition-colors cursor-pointer"
          title={theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}
          aria-label={theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}
        >
          <AnimatePresence mode="wait" initial={false}>
            {theme === 'dark' ? (
              <motion.div
                key="sun"
                initial={{ rotate: -90, opacity: 0, scale: 0.5 }}
                animate={{ rotate: 0, opacity: 1, scale: 1 }}
                exit={{ rotate: 90, opacity: 0, scale: 0.5 }}
                transition={{ duration: 0.2 }}
              >
                <Sun size={16} className="text-amber-400" />
              </motion.div>
            ) : (
              <motion.div
                key="moon"
                initial={{ rotate: 90, opacity: 0, scale: 0.5 }}
                animate={{ rotate: 0, opacity: 1, scale: 1 }}
                exit={{ rotate: -90, opacity: 0, scale: 0.5 }}
                transition={{ duration: 0.2 }}
              >
                <Moon size={16} className="text-indigo-600" />
              </motion.div>
            )}
          </AnimatePresence>
        </button>

        {/* Notification bell */}
        <button className="relative w-8 h-8 rounded-lg flex items-center justify-center text-zinc-600 dark:text-zinc-400 hover:text-zinc-900 dark:hover:text-zinc-100 hover:bg-zinc-100 dark:hover:bg-zinc-800 transition-colors">
          <Bell size={16} />
          {alertCount > 0 && (
            <span className="absolute top-1 right-1 w-3.5 h-3.5 rounded-full bg-rose-500 text-white text-[9px] font-bold flex items-center justify-center leading-none">
              {alertCount > 9 ? '9+' : alertCount}
            </span>
          )}
        </button>

        {/* User profile & logout menu */}
        <div className="relative">
          <button
            onClick={() => setUserMenuOpen(!userMenuOpen)}
            className="w-8 h-8 rounded-full bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center text-white text-xs font-bold shadow hover:opacity-90 transition-opacity cursor-pointer"
            title={user?.email}
          >
            {initials}
          </button>

          {userMenuOpen && (
            <div className="absolute right-0 mt-2 w-56 rounded-xl bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 shadow-xl py-2 z-50">
              <div className="px-3.5 py-2 border-b border-zinc-200 dark:border-zinc-800">
                <p className="text-xs font-semibold text-zinc-900 dark:text-zinc-100 truncate">
                  {user?.full_name || 'Active User'}
                </p>
                <p className="text-[11px] text-zinc-500 truncate">{user?.email}</p>
                <div className="mt-1.5 flex items-center gap-1.5">
                  <span
                    className={`inline-flex px-1.5 py-0.5 rounded text-[9px] font-medium border capitalize ${
                      roleBadgeColors[user?.role || 'viewer']
                    }`}
                  >
                    {user?.role.replace('_', ' ')}
                  </span>
                  <span className="text-[10px] text-zinc-400">
                    Org: {activeOrg?.name || 'Default'}
                  </span>
                </div>
              </div>
              <button
                onClick={() => {
                  setUserMenuOpen(false);
                  logout();
                }}
                className="w-full flex items-center gap-2 px-3.5 py-2 text-xs text-rose-600 dark:text-rose-400 hover:bg-rose-50 dark:hover:bg-rose-500/10 font-medium transition-colors cursor-pointer"
              >
                <LogOut size={13} />
                <span>Sign Out</span>
              </button>
            </div>
          )}
        </div>
      </div>

      {/* Create Org Modal */}
      {showNewOrgModal && (
        <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-2xl p-5 max-w-sm w-full shadow-2xl">
            <h3 className="text-sm font-semibold text-zinc-900 dark:text-zinc-100 mb-1">
              Create New Organization
            </h3>
            <p className="text-xs text-zinc-500 mb-4">
              Add a separate tenant workspace with isolated pipelines and datasets.
            </p>
            <form onSubmit={handleCreateOrg}>
              <input
                type="text"
                value={newOrgName}
                onChange={(e) => setNewOrgName(e.target.value)}
                placeholder="Workspace name (e.g. Risk Analytics)"
                required
                className="w-full bg-zinc-50 dark:bg-zinc-950 border border-zinc-200 dark:border-zinc-800 rounded-xl px-3 py-2 text-xs text-zinc-900 dark:text-zinc-100 focus:outline-none focus:border-indigo-500 mb-4"
              />
              <div className="flex justify-end gap-2">
                <button
                  type="button"
                  onClick={() => setShowNewOrgModal(false)}
                  className="px-3 py-1.5 rounded-lg border border-zinc-200 dark:border-zinc-800 text-xs text-zinc-600 dark:text-zinc-400 hover:bg-zinc-100 dark:hover:bg-zinc-800"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-3 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-medium shadow"
                >
                  Create
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </header>
  );
}
