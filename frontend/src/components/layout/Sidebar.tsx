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
  Zap,
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
    <aside className="fixed left-0 top-16 bottom-0 w-64 bg-slate-800/50 border-r border-slate-700 overflow-y-auto">
      <nav className="p-4 space-y-6">
        {/* Main navigation */}
        <div className="space-y-1">
          {navigation.map((item) => {
            const isActive = pathname === item.href;
            return (
              <Link
                key={item.name}
                href={item.href}
                className={cn(
                  'flex items-center space-x-3 px-3 py-2 rounded-lg transition-colors',
                  isActive
                    ? 'bg-brand-500/20 text-brand-400'
                    : 'text-slate-400 hover:bg-slate-700/50 hover:text-white'
                )}
              >
                <item.icon className="h-5 w-5" />
                <span>{item.name}</span>
              </Link>
            );
          })}
        </div>

        {/* Connection status */}
        <div className="px-3">
          <div className="flex items-center space-x-2 text-sm">
            <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse" />
            <span className="text-slate-400">Live connection</span>
          </div>
        </div>

        {/* Stats */}
        <div className="px-3 py-4 bg-slate-900/50 rounded-lg">
          <div className="text-xs text-slate-500 uppercase tracking-wider mb-3">
            Today&apos;s Activity
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <div className="text-2xl font-semibold text-white">0</div>
              <div className="text-xs text-slate-400">Events</div>
            </div>
            <div>
              <div className="text-2xl font-semibold text-brand-400">0</div>
              <div className="text-xs text-slate-400">High Alpha</div>
            </div>
          </div>
        </div>

        {/* Secondary navigation */}
        <div className="pt-4 border-t border-slate-700 space-y-1">
          {secondaryNavigation.map((item) => {
            const isActive = pathname === item.href;
            return (
              <Link
                key={item.name}
                href={item.href}
                className={cn(
                  'flex items-center space-x-3 px-3 py-2 rounded-lg transition-colors',
                  isActive
                    ? 'bg-brand-500/20 text-brand-400'
                    : 'text-slate-400 hover:bg-slate-700/50 hover:text-white'
                )}
              >
                <item.icon className="h-5 w-5" />
                <span>{item.name}</span>
              </Link>
            );
          })}
        </div>
      </nav>
    </aside>
  );
}
