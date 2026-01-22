'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import {
  LayoutDashboard,
  Rss,
  Search,
  Star,
  Bell,
  Settings,
  Zap,
  TrendingUp,
  TrendingDown,
  BarChart3,
} from 'lucide-react';
import { cn } from '@/lib/utils';

const navigation = [
  { name: 'Dashboard', href: '/dashboard', icon: LayoutDashboard },
  { name: 'Event Feed', href: '/dashboard/feed', icon: Rss },
  { name: 'High Alpha', href: '/dashboard/high-alpha', icon: Zap },
  { name: 'Search', href: '/dashboard/search', icon: Search },
  { name: 'Watchlist', href: '/dashboard/watchlist', icon: Star },
  { name: 'Alerts', href: '/dashboard/alerts', icon: Bell },
];

const secondaryNavigation = [
  { name: 'Settings', href: '/dashboard/settings', icon: Settings },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="fixed left-0 top-16 bottom-0 w-64 bg-paper border-r border-border overflow-y-auto custom-scrollbar">
      <nav className="p-4 space-y-6">
        {/* Main navigation */}
        <div className="space-y-1">
          <p className="px-3 mb-2 text-2xs font-medium text-ink-faint uppercase tracking-wider">
            Navigation
          </p>
          {navigation.map((item) => {
            const isActive = pathname === item.href;
            return (
              <Link
                key={item.name}
                href={item.href}
                className={cn(
                  'flex items-center gap-3 px-3 py-2.5 rounded-lg transition-all text-sm',
                  isActive
                    ? 'bg-ink text-paper font-medium'
                    : 'text-ink-muted hover:bg-paper-warm hover:text-ink'
                )}
              >
                <item.icon className={cn('h-4 w-4', isActive ? 'text-paper' : 'text-ink-faint')} />
                <span>{item.name}</span>
                {item.name === 'High Alpha' && (
                  <span className="ml-auto px-1.5 py-0.5 text-2xs font-mono bg-accent text-paper rounded">
                    3
                  </span>
                )}
              </Link>
            );
          })}
        </div>

        {/* Live Status Card */}
        <div className="card rounded-lg p-4">
          <div className="flex items-center gap-2 mb-3">
            <div className="w-2 h-2 bg-bullish rounded-full live-indicator" />
            <span className="text-xs font-medium text-ink">Live Connection</span>
          </div>
          <p className="text-2xs text-ink-muted leading-relaxed">
            Receiving real-time events from 50+ data sources with &lt;2s latency.
          </p>
        </div>

        {/* Today's Activity */}
        <div className="space-y-3">
          <p className="px-3 text-2xs font-medium text-ink-faint uppercase tracking-wider">
            Today&apos;s Activity
          </p>
          <div className="card rounded-lg p-4 space-y-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <div className="w-8 h-8 rounded-md bg-paper-warm flex items-center justify-center">
                  <BarChart3 className="h-4 w-4 text-ink-muted" />
                </div>
                <div>
                  <div className="font-mono text-lg font-semibold text-ink">247</div>
                  <div className="text-2xs text-ink-faint">Total Events</div>
                </div>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-3 pt-3 border-t border-border">
              <div className="flex items-center gap-2">
                <div className="w-6 h-6 rounded bg-bullish-bg flex items-center justify-center">
                  <TrendingUp className="h-3 w-3 text-bullish" />
                </div>
                <div>
                  <div className="font-mono text-sm font-semibold text-bullish">84</div>
                  <div className="text-2xs text-ink-faint">Bullish</div>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-6 h-6 rounded bg-bearish-bg flex items-center justify-center">
                  <TrendingDown className="h-3 w-3 text-bearish" />
                </div>
                <div>
                  <div className="font-mono text-sm font-semibold text-bearish">52</div>
                  <div className="text-2xs text-ink-faint">Bearish</div>
                </div>
              </div>
            </div>

            <div className="flex items-center gap-2 pt-3 border-t border-border">
              <div className="w-6 h-6 rounded bg-accent-light flex items-center justify-center">
                <Zap className="h-3 w-3 text-accent" />
              </div>
              <div>
                <div className="font-mono text-sm font-semibold text-accent">12</div>
                <div className="text-2xs text-ink-faint">High Alpha Signals</div>
              </div>
            </div>
          </div>
        </div>

        {/* Secondary navigation */}
        <div className="pt-4 border-t border-border space-y-1">
          {secondaryNavigation.map((item) => {
            const isActive = pathname === item.href;
            return (
              <Link
                key={item.name}
                href={item.href}
                className={cn(
                  'flex items-center gap-3 px-3 py-2.5 rounded-lg transition-all text-sm',
                  isActive
                    ? 'bg-ink text-paper font-medium'
                    : 'text-ink-muted hover:bg-paper-warm hover:text-ink'
                )}
              >
                <item.icon className={cn('h-4 w-4', isActive ? 'text-paper' : 'text-ink-faint')} />
                <span>{item.name}</span>
              </Link>
            );
          })}
        </div>

        {/* Upgrade CTA */}
        <div className="card-elevated rounded-lg p-4 text-center">
          <p className="text-xs font-medium text-ink mb-1">Upgrade to Pro</p>
          <p className="text-2xs text-ink-muted mb-3">
            Get unlimited watchlist slots and real-time alerts
          </p>
          <Link
            href="/dashboard/settings/billing"
            className="btn btn-primary text-xs px-4 py-2 rounded-md inline-block w-full"
          >
            View Plans
          </Link>
        </div>
      </nav>
    </aside>
  );
}
