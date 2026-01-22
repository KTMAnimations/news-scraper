'use client';

import { useSession, signOut } from 'next-auth/react';
import Link from 'next/link';
import { Bell, Search, User, LogOut, Settings, Activity, ChevronDown } from 'lucide-react';
import { useState } from 'react';

export function Header() {
  const { data: session } = useSession();
  const [showUserMenu, setShowUserMenu] = useState(false);

  return (
    <header className="sticky top-0 z-50 bg-paper/95 backdrop-blur-sm border-b border-border">
      <div className="flex items-center justify-between h-16 px-6">
        {/* Logo */}
        <Link href="/dashboard" className="flex items-center gap-3 group">
          <div className="w-9 h-9 bg-ink rounded-md flex items-center justify-center group-hover:scale-105 transition-transform">
            <Activity className="h-5 w-5 text-paper" strokeWidth={2.5} />
          </div>
          <div className="flex flex-col">
            <span className="font-serif text-lg text-ink tracking-tight leading-tight">Micro-Alpha</span>
            <span className="text-2xs text-ink-faint uppercase tracking-widest">Dashboard</span>
          </div>
        </Link>

        {/* Search */}
        <div className="flex-1 max-w-xl mx-8">
          <div className="relative">
            <Search className="absolute left-4 top-1/2 -translate-y-1/2 h-4 w-4 text-ink-faint" />
            <input
              type="text"
              placeholder="Search events, tickers, news..."
              className="input w-full pl-11 pr-4 py-2.5 rounded-lg text-ink placeholder-ink-faint text-sm"
            />
            <div className="absolute right-3 top-1/2 -translate-y-1/2 hidden sm:flex items-center gap-1">
              <kbd className="px-1.5 py-0.5 text-2xs font-mono bg-paper-warm border border-border rounded text-ink-faint">⌘</kbd>
              <kbd className="px-1.5 py-0.5 text-2xs font-mono bg-paper-warm border border-border rounded text-ink-faint">K</kbd>
            </div>
          </div>
        </div>

        {/* Right side */}
        <div className="flex items-center gap-2">
          {/* Live indicator */}
          <div className="hidden md:flex items-center gap-2 px-3 py-1.5 bg-bullish-bg rounded-full mr-2">
            <div className="w-2 h-2 rounded-full bg-bullish live-indicator" />
            <span className="text-xs font-medium text-bullish">Live</span>
          </div>

          {/* Notifications */}
          <button className="relative p-2.5 text-ink-muted hover:text-ink hover:bg-paper-warm rounded-lg transition-colors">
            <Bell className="h-5 w-5" />
            <span className="absolute top-2 right-2 w-2 h-2 bg-bearish rounded-full" />
          </button>

          {/* User menu */}
          <div className="relative">
            <button
              onClick={() => setShowUserMenu(!showUserMenu)}
              className="flex items-center gap-2 p-2 rounded-lg hover:bg-paper-warm transition-colors"
            >
              <div className="w-8 h-8 bg-accent-light rounded-full flex items-center justify-center">
                <span className="text-sm font-medium text-accent">
                  {session?.user?.name?.[0] || session?.user?.email?.[0]?.toUpperCase() || 'U'}
                </span>
              </div>
              <span className="text-ink text-sm hidden sm:block">
                {session?.user?.name || session?.user?.email?.split('@')[0]}
              </span>
              <ChevronDown className="h-4 w-4 text-ink-faint hidden sm:block" />
            </button>

            {showUserMenu && (
              <>
                <div
                  className="fixed inset-0 z-10"
                  onClick={() => setShowUserMenu(false)}
                />
                <div className="absolute right-0 mt-2 w-56 bg-paper border border-border rounded-lg shadow-elevated z-20 py-1 overflow-hidden">
                  <div className="px-4 py-3 border-b border-border bg-paper-warm">
                    <p className="text-sm font-medium text-ink truncate">
                      {session?.user?.name || 'User'}
                    </p>
                    <p className="text-xs text-ink-muted truncate mt-0.5">
                      {session?.user?.email}
                    </p>
                    <div className="flex items-center gap-2 mt-2">
                      <span className="px-2 py-0.5 text-2xs font-medium bg-accent-light text-accent rounded-full capitalize">
                        {session?.user?.subscriptionTier || 'starter'} Plan
                      </span>
                    </div>
                  </div>

                  <div className="py-1">
                    <Link
                      href="/dashboard/settings"
                      className="flex items-center px-4 py-2.5 text-sm text-ink-muted hover:text-ink hover:bg-paper-warm transition-colors"
                      onClick={() => setShowUserMenu(false)}
                    >
                      <Settings className="h-4 w-4 mr-3" />
                      Settings
                    </Link>

                    <button
                      onClick={() => signOut({ callbackUrl: '/auth/login' })}
                      className="w-full flex items-center px-4 py-2.5 text-sm text-ink-muted hover:text-ink hover:bg-paper-warm transition-colors"
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
