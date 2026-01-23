'use client';

import { useSession, signOut } from 'next-auth/react';
import Link from 'next/link';
import { Bell, Search, LogOut, Settings, ChevronDown, Sun, Moon, Monitor } from 'lucide-react';
import { useState, useEffect } from 'react';
import { useTheme } from 'next-themes';
import { ConnectionStatus } from './ConnectionStatus';

export function Header() {
  const { data: session } = useSession();
  const [showUserMenu, setShowUserMenu] = useState(false);
  const [showThemeMenu, setShowThemeMenu] = useState(false);
  const { theme, setTheme, resolvedTheme } = useTheme();
  const [mounted, setMounted] = useState(false);

  // Avoid hydration mismatch
  useEffect(() => {
    setMounted(true);
  }, []);

  const ThemeIcon = mounted ? (resolvedTheme === 'dark' ? Moon : Sun) : Monitor;

  return (
    <header className="sticky top-0 z-50 bg-bg-elevated/80 backdrop-blur-xl border-b border-border">
      <div className="flex items-center justify-between h-16 px-6">
        {/* Logo */}
        <Link href="/dashboard" className="flex items-center gap-2.5 group">
          <div className="w-8 h-8 bg-text-primary rounded-lg flex items-center justify-center group-hover:scale-105 transition-transform">
            <span className="text-bg-primary font-mono font-bold text-sm">M</span>
          </div>
          <span className="font-semibold text-lg tracking-tight text-text-primary">Micro-Alpha</span>
        </Link>

        {/* Search */}
        <div className="flex-1 max-w-xl mx-8">
          <div className="relative">
            <Search className="absolute left-4 top-1/2 -translate-y-1/2 h-4 w-4 text-text-quaternary" />
            <input
              type="text"
              placeholder="Search events, tickers, news..."
              className="input w-full pl-11 pr-4 py-2.5 text-sm"
            />
            <div className="absolute right-3 top-1/2 -translate-y-1/2 hidden sm:flex items-center gap-1">
              <kbd className="px-1.5 py-0.5 text-2xs font-mono bg-bg-tertiary border border-border rounded text-text-quaternary">⌘</kbd>
              <kbd className="px-1.5 py-0.5 text-2xs font-mono bg-bg-tertiary border border-border rounded text-text-quaternary">K</kbd>
            </div>
          </div>
        </div>

        {/* Right side */}
        <div className="flex items-center gap-2">
          {/* WebSocket Connection Status Indicator */}
          <div className="hidden md:block mr-2">
            <ConnectionStatus showLabel={true} showReconnectInfo={true} />
          </div>
          {/* Compact version for mobile */}
          <div className="block md:hidden mr-1">
            <ConnectionStatus compact={true} />
          </div>

          {/* Theme toggle */}
          <div className="relative">
            <button
              onClick={() => setShowThemeMenu(!showThemeMenu)}
              className="p-2.5 text-text-tertiary hover:text-text-primary hover:bg-hover rounded-lg transition-colors"
              aria-label="Toggle theme"
            >
              <ThemeIcon className="h-5 w-5" />
            </button>

            {showThemeMenu && (
              <>
                <div
                  className="fixed inset-0 z-10"
                  onClick={() => setShowThemeMenu(false)}
                />
                <div className="absolute right-0 mt-2 w-40 bg-bg-elevated border border-border rounded-xl shadow-lg z-20 py-1 overflow-hidden animate-scale-in">
                  <button
                    onClick={() => { setTheme('light'); setShowThemeMenu(false); }}
                    className={`w-full flex items-center px-4 py-2.5 text-sm transition-colors ${
                      theme === 'light' ? 'text-accent bg-accent-subtle' : 'text-text-secondary hover:text-text-primary hover:bg-hover'
                    }`}
                  >
                    <Sun className="h-4 w-4 mr-3" />
                    Light
                  </button>
                  <button
                    onClick={() => { setTheme('dark'); setShowThemeMenu(false); }}
                    className={`w-full flex items-center px-4 py-2.5 text-sm transition-colors ${
                      theme === 'dark' ? 'text-accent bg-accent-subtle' : 'text-text-secondary hover:text-text-primary hover:bg-hover'
                    }`}
                  >
                    <Moon className="h-4 w-4 mr-3" />
                    Dark
                  </button>
                  <button
                    onClick={() => { setTheme('system'); setShowThemeMenu(false); }}
                    className={`w-full flex items-center px-4 py-2.5 text-sm transition-colors ${
                      theme === 'system' ? 'text-accent bg-accent-subtle' : 'text-text-secondary hover:text-text-primary hover:bg-hover'
                    }`}
                  >
                    <Monitor className="h-4 w-4 mr-3" />
                    System
                  </button>
                </div>
              </>
            )}
          </div>

          {/* Notifications */}
          <button className="relative p-2.5 text-text-tertiary hover:text-text-primary hover:bg-hover rounded-lg transition-colors">
            <Bell className="h-5 w-5" />
            <span className="absolute top-2 right-2 w-2 h-2 bg-negative rounded-full" />
          </button>

          {/* User menu */}
          <div className="relative">
            <button
              onClick={() => setShowUserMenu(!showUserMenu)}
              className="flex items-center gap-2 p-2 rounded-lg hover:bg-hover transition-colors"
            >
              <div className="w-8 h-8 bg-accent-subtle rounded-full flex items-center justify-center">
                <span className="text-sm font-semibold text-accent">
                  {session?.user?.name?.[0] || session?.user?.email?.[0]?.toUpperCase() || 'U'}
                </span>
              </div>
              <span className="text-text-primary text-sm hidden sm:block font-medium">
                {session?.user?.name || session?.user?.email?.split('@')[0]}
              </span>
              <ChevronDown className="h-4 w-4 text-text-quaternary hidden sm:block" />
            </button>

            {showUserMenu && (
              <>
                <div
                  className="fixed inset-0 z-10"
                  onClick={() => setShowUserMenu(false)}
                />
                <div className="absolute right-0 mt-2 w-60 bg-bg-elevated border border-border rounded-xl shadow-lg z-20 py-1 overflow-hidden animate-scale-in">
                  <div className="px-4 py-3 border-b border-border bg-bg-secondary">
                    <p className="text-sm font-medium text-text-primary truncate">
                      {session?.user?.name || 'User'}
                    </p>
                    <p className="text-xs text-text-tertiary truncate mt-0.5">
                      {session?.user?.email}
                    </p>
                    <div className="flex items-center gap-2 mt-2">
                      <span className="px-2 py-0.5 text-2xs font-medium bg-accent-subtle text-accent rounded-full capitalize">
                        {session?.user?.subscriptionTier || 'starter'} Plan
                      </span>
                    </div>
                  </div>

                  <div className="py-1">
                    <Link
                      href="/dashboard/settings"
                      className="flex items-center px-4 py-2.5 text-sm text-text-secondary hover:text-text-primary hover:bg-hover transition-colors"
                      onClick={() => setShowUserMenu(false)}
                    >
                      <Settings className="h-4 w-4 mr-3" />
                      Settings
                    </Link>

                    <button
                      onClick={() => signOut({ callbackUrl: '/auth/login' })}
                      className="w-full flex items-center px-4 py-2.5 text-sm text-text-secondary hover:text-text-primary hover:bg-hover transition-colors"
                    >
                      <LogOut className="h-4 w-4 mr-3" />
                      Sign out
                    </button>
                  </div>
                </div>
              </>
            )}
          </div>
        </div>
      </div>
    </header>
  );
}
