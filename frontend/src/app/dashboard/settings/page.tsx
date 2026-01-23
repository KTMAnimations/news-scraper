'use client';

import { useState } from 'react';
import { useSession } from 'next-auth/react';
import { useQuery, useMutation } from '@tanstack/react-query';
import {
  User,
  Mail,
  Bell,
  CreditCard,
  Shield,
  Moon,
  Sun,
  Check,
  ExternalLink,
  Crown,
  Zap,
} from 'lucide-react';
import { api } from '@/lib/api';
import { cn } from '@/lib/utils';
import { TIER_FEATURES, type SubscriptionTier } from '@/types/user';

type SettingsTab = 'profile' | 'notifications' | 'billing' | 'security';

export default function SettingsPage() {
  const { data: session } = useSession();
  const [activeTab, setActiveTab] = useState<SettingsTab>('profile');

  // Fetch subscription
  const { data: subscription } = useQuery({
    queryKey: ['subscription'],
    queryFn: () => api.getSubscription(),
  });

  // Checkout mutation
  const checkoutMutation = useMutation({
    mutationFn: (tier: string) => api.createCheckoutSession(tier),
    onSuccess: (data) => {
      if (data.url) {
        window.location.href = data.url;
      }
    },
  });

  // Portal mutation
  const portalMutation = useMutation({
    mutationFn: () => api.createPortalSession(),
    onSuccess: (data) => {
      if (data.url) {
        window.location.href = data.url;
      }
    },
  });

  const currentTier = (subscription?.tier || 'starter') as SubscriptionTier;

  const tabs = [
    { id: 'profile' as const, label: 'Profile', icon: User },
    { id: 'notifications' as const, label: 'Notifications', icon: Bell },
    { id: 'billing' as const, label: 'Billing', icon: CreditCard },
    { id: 'security' as const, label: 'Security', icon: Shield },
  ];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold text-text-primary mb-1 tracking-tight">
          Settings
        </h1>
        <p className="text-text-secondary">
          Manage your account preferences and subscription
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        {/* Sidebar */}
        <div className="card rounded-2xl p-4">
          <nav className="space-y-1">
            {tabs.map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={cn(
                  'w-full flex items-center gap-3 px-4 py-3 rounded-xl text-sm font-medium transition-colors',
                  activeTab === tab.id
                    ? 'bg-text-primary text-bg-primary'
                    : 'text-text-secondary hover:bg-hover hover:text-text-primary'
                )}
              >
                <tab.icon className="h-4 w-4" />
                {tab.label}
              </button>
            ))}
          </nav>
        </div>

        {/* Content */}
        <div className="lg:col-span-3 space-y-6">
          {/* Profile Tab */}
          {activeTab === 'profile' && (
            <div className="card rounded-2xl p-6">
              <h2 className="text-lg font-semibold text-text-primary mb-6">
                Profile Information
              </h2>

              <div className="space-y-5">
                {/* Avatar */}
                <div className="flex items-center gap-4">
                  <div className="w-20 h-20 rounded-2xl bg-accent-subtle flex items-center justify-center">
                    <span className="text-3xl font-bold text-accent">
                      {session?.user?.name?.[0] ||
                        session?.user?.email?.[0]?.toUpperCase() ||
                        'U'}
                    </span>
                  </div>
                  <div>
                    <p className="font-medium text-text-primary">
                      {session?.user?.name || 'User'}
                    </p>
                    <p className="text-sm text-text-tertiary">
                      {session?.user?.email}
                    </p>
                    <span className="inline-flex items-center gap-1.5 mt-2 px-2.5 py-1 text-xs font-medium bg-accent-subtle text-accent rounded-full">
                      <Crown className="h-3 w-3" />
                      {TIER_FEATURES[currentTier].name} Plan
                    </span>
                  </div>
                </div>

                {/* Form */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-5 pt-5 border-t border-border">
                  <div>
                    <label className="data-label mb-2 block">Full Name</label>
                    <input
                      type="text"
                      defaultValue={session?.user?.name || ''}
                      className="input w-full"
                    />
                  </div>
                  <div>
                    <label className="data-label mb-2 block">Email</label>
                    <input
                      type="email"
                      defaultValue={session?.user?.email || ''}
                      className="input w-full"
                      disabled
                    />
                  </div>
                  <div className="md:col-span-2">
                    <label className="data-label mb-2 block">Company (optional)</label>
                    <input
                      type="text"
                      placeholder="Your company name"
                      className="input w-full"
                    />
                  </div>
                </div>

                <div className="flex justify-end pt-4">
                  <button className="btn btn-primary">Save Changes</button>
                </div>
              </div>
            </div>
          )}

          {/* Notifications Tab */}
          {activeTab === 'notifications' && (
            <div className="card rounded-2xl p-6">
              <h2 className="text-lg font-semibold text-text-primary mb-6">
                Notification Preferences
              </h2>

              <div className="space-y-6">
                {/* Email Notifications */}
                <div>
                  <h3 className="font-medium text-text-primary mb-4">
                    Email Notifications
                  </h3>
                  <div className="space-y-4">
                    {[
                      {
                        id: 'alerts',
                        label: 'Alert Notifications',
                        desc: 'Receive emails when your alerts are triggered',
                      },
                      {
                        id: 'daily',
                        label: 'Daily Digest',
                        desc: 'Get a summary of high-alpha events each day',
                      },
                      {
                        id: 'weekly',
                        label: 'Weekly Report',
                        desc: 'Comprehensive weekly market analysis',
                      },
                      {
                        id: 'product',
                        label: 'Product Updates',
                        desc: 'Learn about new features and improvements',
                      },
                    ].map((item) => (
                      <div
                        key={item.id}
                        className="flex items-center justify-between p-4 bg-bg-secondary rounded-xl"
                      >
                        <div>
                          <p className="font-medium text-text-primary">
                            {item.label}
                          </p>
                          <p className="text-sm text-text-tertiary">
                            {item.desc}
                          </p>
                        </div>
                        <label className="relative inline-flex items-center cursor-pointer">
                          <input
                            type="checkbox"
                            defaultChecked={item.id !== 'product'}
                            className="sr-only peer"
                          />
                          <div className="w-11 h-6 bg-bg-tertiary peer-focus:ring-2 peer-focus:ring-accent/20 rounded-full peer peer-checked:after:translate-x-full rtl:peer-checked:after:-translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:start-[2px] after:bg-white after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-accent"></div>
                        </label>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Push Notifications */}
                <div className="pt-6 border-t border-border">
                  <h3 className="font-medium text-text-primary mb-4">
                    Push Notifications
                  </h3>
                  <div className="space-y-4">
                    {[
                      {
                        id: 'realtime',
                        label: 'Real-time Alerts',
                        desc: 'Get instant push notifications for triggered alerts',
                      },
                      {
                        id: 'highalpha',
                        label: 'High Alpha Signals',
                        desc: 'Notifications for signals with alpha score > 80',
                      },
                    ].map((item) => (
                      <div
                        key={item.id}
                        className="flex items-center justify-between p-4 bg-bg-secondary rounded-xl"
                      >
                        <div>
                          <p className="font-medium text-text-primary">
                            {item.label}
                          </p>
                          <p className="text-sm text-text-tertiary">
                            {item.desc}
                          </p>
                        </div>
                        <label className="relative inline-flex items-center cursor-pointer">
                          <input
                            type="checkbox"
                            defaultChecked
                            className="sr-only peer"
                          />
                          <div className="w-11 h-6 bg-bg-tertiary peer-focus:ring-2 peer-focus:ring-accent/20 rounded-full peer peer-checked:after:translate-x-full rtl:peer-checked:after:-translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:start-[2px] after:bg-white after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-accent"></div>
                        </label>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Billing Tab */}
          {activeTab === 'billing' && (
            <>
              {/* Current Plan */}
              <div className="card rounded-2xl p-6">
                <div className="flex items-center justify-between mb-6">
                  <h2 className="text-lg font-semibold text-text-primary">
                    Current Plan
                  </h2>
                  {subscription?.status === 'active' && (
                    <span className="badge badge-positive">Active</span>
                  )}
                </div>

                <div className="flex items-center gap-4 p-5 bg-gradient-to-r from-accent/10 to-transparent rounded-xl border border-accent/20">
                  <div className="w-14 h-14 rounded-2xl bg-accent flex items-center justify-center">
                    <Crown className="h-7 w-7 text-bg-primary" />
                  </div>
                  <div className="flex-1">
                    <p className="text-xl font-bold text-text-primary">
                      {TIER_FEATURES[currentTier].name}
                    </p>
                    <p className="text-sm text-text-tertiary">
                      {TIER_FEATURES[currentTier].price > 0
                        ? `$${TIER_FEATURES[currentTier].price}/month`
                        : 'Contact for pricing'}
                    </p>
                  </div>
                  <button
                    onClick={() => portalMutation.mutate()}
                    className="btn btn-secondary flex items-center gap-2"
                  >
                    Manage Subscription
                    <ExternalLink className="h-4 w-4" />
                  </button>
                </div>

                <div className="mt-5 grid grid-cols-1 md:grid-cols-2 gap-3">
                  {TIER_FEATURES[currentTier].features.map((feature) => (
                    <div key={feature} className="flex items-center gap-2">
                      <Check className="h-4 w-4 text-positive" />
                      <span className="text-sm text-text-secondary">
                        {feature}
                      </span>
                    </div>
                  ))}
                </div>
              </div>

              {/* Upgrade Plans */}
              <div className="card rounded-2xl p-6">
                <h2 className="text-lg font-semibold text-text-primary mb-6">
                  Upgrade Your Plan
                </h2>

                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  {(
                    Object.entries(TIER_FEATURES) as [
                      SubscriptionTier,
                      (typeof TIER_FEATURES)[SubscriptionTier]
                    ][]
                  )
                    .filter(([tier]) => tier !== 'enterprise')
                    .map(([tier, info]) => (
                      <div
                        key={tier}
                        className={cn(
                          'p-5 rounded-xl border-2 transition-colors',
                          currentTier === tier
                            ? 'border-accent bg-accent/5'
                            : 'border-border hover:border-accent/50'
                        )}
                      >
                        <div className="flex items-center justify-between mb-3">
                          <h3 className="font-semibold text-text-primary">
                            {info.name}
                          </h3>
                          {tier === 'professional' && (
                            <span className="badge badge-accent text-2xs">
                              Popular
                            </span>
                          )}
                        </div>
                        <p className="text-2xl font-bold text-text-primary mb-4">
                          ${info.price}
                          <span className="text-sm font-normal text-text-tertiary">
                            /mo
                          </span>
                        </p>
                        <ul className="space-y-2 mb-5">
                          {info.features.slice(0, 4).map((feature) => (
                            <li
                              key={feature}
                              className="flex items-start gap-2 text-sm text-text-secondary"
                            >
                              <Check className="h-4 w-4 text-positive shrink-0 mt-0.5" />
                              {feature}
                            </li>
                          ))}
                        </ul>
                        <button
                          onClick={() => checkoutMutation.mutate(tier)}
                          disabled={
                            currentTier === tier || checkoutMutation.isPending
                          }
                          className={cn(
                            'btn w-full',
                            currentTier === tier
                              ? 'btn-secondary'
                              : 'btn-primary'
                          )}
                        >
                          {currentTier === tier
                            ? 'Current Plan'
                            : `Upgrade to ${info.name}`}
                        </button>
                      </div>
                    ))}
                </div>

                {/* Enterprise */}
                <div className="mt-6 p-5 rounded-xl bg-gradient-to-r from-bg-tertiary to-bg-secondary border border-border">
                  <div className="flex items-center justify-between">
                    <div>
                      <h3 className="font-semibold text-text-primary flex items-center gap-2">
                        <Zap className="h-5 w-5 text-accent" />
                        Enterprise
                      </h3>
                      <p className="text-sm text-text-tertiary mt-1">
                        Custom solutions for large teams with dedicated support
                      </p>
                    </div>
                    <a
                      href="mailto:sales@micro-alpha.com"
                      className="btn btn-secondary"
                    >
                      Contact Sales
                    </a>
                  </div>
                </div>
              </div>
            </>
          )}

          {/* Security Tab */}
          {activeTab === 'security' && (
            <div className="card rounded-2xl p-6">
              <h2 className="text-lg font-semibold text-text-primary mb-6">
                Security Settings
              </h2>

              <div className="space-y-6">
                {/* Change Password */}
                <div className="p-5 bg-bg-secondary rounded-xl">
                  <h3 className="font-medium text-text-primary mb-4">
                    Change Password
                  </h3>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div>
                      <label className="data-label mb-2 block">
                        Current Password
                      </label>
                      <input
                        type="password"
                        className="input w-full"
                        placeholder="Enter current password"
                      />
                    </div>
                    <div />
                    <div>
                      <label className="data-label mb-2 block">
                        New Password
                      </label>
                      <input
                        type="password"
                        className="input w-full"
                        placeholder="Enter new password"
                      />
                    </div>
                    <div>
                      <label className="data-label mb-2 block">
                        Confirm New Password
                      </label>
                      <input
                        type="password"
                        className="input w-full"
                        placeholder="Confirm new password"
                      />
                    </div>
                  </div>
                  <button className="btn btn-primary mt-4">
                    Update Password
                  </button>
                </div>

                {/* Two-Factor Authentication */}
                <div className="p-5 bg-bg-secondary rounded-xl">
                  <div className="flex items-center justify-between">
                    <div>
                      <h3 className="font-medium text-text-primary">
                        Two-Factor Authentication
                      </h3>
                      <p className="text-sm text-text-tertiary mt-1">
                        Add an extra layer of security to your account
                      </p>
                    </div>
                    <button className="btn btn-secondary">Enable 2FA</button>
                  </div>
                </div>

                {/* Active Sessions */}
                <div className="p-5 bg-bg-secondary rounded-xl">
                  <h3 className="font-medium text-text-primary mb-4">
                    Active Sessions
                  </h3>
                  <div className="space-y-3">
                    <div className="flex items-center justify-between p-3 bg-bg-primary rounded-lg">
                      <div className="flex items-center gap-3">
                        <div className="w-10 h-10 rounded-lg bg-positive-subtle flex items-center justify-center">
                          <Check className="h-5 w-5 text-positive" />
                        </div>
                        <div>
                          <p className="text-sm font-medium text-text-primary">
                            Current Session
                          </p>
                          <p className="text-xs text-text-tertiary">
                            Chrome on macOS • San Francisco, CA
                          </p>
                        </div>
                      </div>
                      <span className="badge badge-positive">Active</span>
                    </div>
                  </div>
                </div>

                {/* Danger Zone */}
                <div className="p-5 border border-negative/30 bg-negative/5 rounded-xl">
                  <h3 className="font-medium text-negative mb-2">
                    Danger Zone
                  </h3>
                  <p className="text-sm text-text-tertiary mb-4">
                    Once you delete your account, there is no going back.
                  </p>
                  <button className="btn border border-negative text-negative hover:bg-negative hover:text-white transition-colors">
                    Delete Account
                  </button>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
