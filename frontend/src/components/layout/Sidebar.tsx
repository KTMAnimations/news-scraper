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
  TrendingUp,
  TrendingDown,
  ArrowUpRight,
} from 'lucide-react';
import { cn } from '@/lib/utils';

const navigation = [
  { name: 'Dashboard', href: '/dashboard', icon: LayoutDashboard },
  { name: 'Event Feed', href: '/dashboard/feed', icon: Rss },
  { name: 'High Alpha', href: '/dashboard/high-alpha', icon: TrendingUp, badge: 3 },
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
    <aside className="fixed left-0 top-16 bottom-0 w-64 bg-bg-elevated border-r border-border overflow-y-auto custom-scrollbar">
      <nav className="p-4 space-y-6">
        {/* Main navigation */}
        <div className="space-y-1">
          <p className="px-3 mb-3 text-2xs font-medium text-text-quaternary uppercase tracking-wider">
            Navigation
          </p>
          {navigation.map((item) => {
            const isActive = pathname === item.href;
            return (
              <Link
                key={item.name}
                href={item.href}
                className={cn(
                  'flex items-center gap-3 px-3 py-2.5 rounded-xl transition-all text-sm group',
                  isActive
                    ? 'bg-text-primary text-bg-primary font-medium'
                    : 'text-text-secondary hover:bg-hover hover:text-text-primary'
                )}
              >
                <item.icon className={cn('h-4 w-4', isActive ? 'text-bg-primary' : 'text-text-tertiary group-hover:text-text-secondary')} />
                <span>{item.name}</span>
                {item.badge && (
                  <span className={cn(
                    'ml-auto px-1.5 py-0.5 text-2xs font-mono rounded',
                    isActive ? 'bg-accent text-bg-primary' : 'bg-accent-subtle text-accent'
                  )}>
                    {item.badge}
                  </span>
                )}
              </Link>
            );
          })}
        </div>

        {/* Live Status Card */}
        <div className="card rounded-xl p-4">
          <div className="flex items-center gap-2 mb-3">
            <div className="live-dot" />
            <span className="text-xs font-medium text-text-primary">Live Connection</span>
          </div>
          <p className="text-2xs text-text-tertiary leading-relaxed">
            Receiving real-time events from 50+ sources with &lt;2s latency.
          </p>
        </div>

        {/* Today's Activity */}
        <div className="space-y-3">
          <p className="px-3 text-2xs font-medium text-text-quaternary uppercase tracking-wider">
            Today&apos;s Activity
          </p>
          <div className="card rounded-xl p-4 space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <div className="font-mono text-2xl font-semibold text-text-primary">247</div>
                <div className="text-2xs text-text-tertiary">Total Events</div>
              </div>
              <div className="text-2xs text-positive font-medium flex items-center gap-1">
                +12%
                <ArrowUpRight className="h-3 w-3" />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-3 pt-3 border-t border-border">
              <div className="flex items-center gap-2">
                <div className="w-6 h-6 rounded-md bg-positive-subtle flex items-center justify-center">
                  <TrendingUp className="h-3 w-3 text-positive" />
                </div>
                <div>
                  <div className="font-mono text-sm font-semibold text-positive">84</div>
                  <div className="text-2xs text-text-tertiary">Bullish</div>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-6 h-6 rounded-md bg-negative-subtle flex items-center justify-center">
                  <TrendingDown className="h-3 w-3 text-negative" />
                </div>
                <div>
                  <div className="font-mono text-sm font-semibold text-negative">52</div>
                  <div className="text-2xs text-text-tertiary">Bearish</div>
                </div>
              </div>
            </div>

            <div className="flex items-center gap-2 pt-3 border-t border-border">
              <div className="w-6 h-6 rounded-md bg-accent-subtle flex items-center justify-center">
                <TrendingUp className="h-3 w-3 text-accent" />
              </div>
              <div>
                <div className="font-mono text-sm font-semibold text-accent">12</div>
                <div className="text-2xs text-text-tertiary">High Alpha Signals</div>
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
                  'flex items-center gap-3 px-3 py-2.5 rounded-xl transition-all text-sm group',
                  isActive
                    ? 'bg-text-primary text-bg-primary font-medium'
                    : 'text-text-secondary hover:bg-hover hover:text-text-primary'
                )}
              >
                <item.icon className={cn('h-4 w-4', isActive ? 'text-bg-primary' : 'text-text-tertiary group-hover:text-text-secondary')} />
                <span>{item.name}</span>
              </Link>
            );
          })}
        </div>

        {/* Upgrade CTA */}
        <div className="card rounded-xl p-4 text-center border-accent/20 bg-gradient-to-br from-accent/5 to-transparent">
          <p className="text-sm font-medium text-text-primary mb-1">Upgrade to Pro</p>
          <p className="text-2xs text-text-tertiary mb-3">
            Get unlimited watchlist slots and real-time alerts
          </p>
          <Link
            href="/dashboard/settings/billing"
            className="btn btn-primary text-xs px-4 py-2 w-full"
          >
            View Plans
          </Link>
        </div>
      </nav>
    </aside>
  );
}
