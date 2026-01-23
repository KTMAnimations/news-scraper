'use client';

import { useState } from 'react';
import { Bell, BellOff, BellRing, Mail, Smartphone, AlertCircle, CheckCircle, Loader2 } from 'lucide-react';
import { toast } from 'sonner';
import { useNotifications } from '@/contexts/NotificationContext';
import { api } from '@/lib/api';
import { cn } from '@/lib/utils';

/**
 * Comprehensive notification settings component for the settings page.
 * Handles both push notification permissions and notification preferences.
 */
export function NotificationSettings() {
  const {
    isSupported,
    permission,
    fcmToken,
    isLoading: contextLoading,
    preferences,
    updatePreferences,
    requestPermission,
  } = useNotifications();

  const [isSendingTest, setIsSendingTest] = useState(false);

  // Handle enabling push notifications
  const handleEnablePush = async () => {
    const granted = await requestPermission();
    if (granted) {
      toast.success('Push notifications enabled');
      await updatePreferences({ pushEnabled: true });
    } else {
      toast.error('Could not enable push notifications. Please check your browser settings.');
    }
  };

  // Handle sending a test notification
  const handleTestNotification = async () => {
    setIsSendingTest(true);
    try {
      await api.sendTestNotification();
      toast.success('Test notification sent. You should receive it shortly.');
    } catch (error) {
      toast.error('Failed to send test notification');
    } finally {
      setIsSendingTest(false);
    }
  };

  // Toggle component
  const Toggle = ({
    id,
    checked,
    onChange,
    disabled = false,
  }: {
    id: string;
    checked: boolean;
    onChange: (checked: boolean) => void;
    disabled?: boolean;
  }) => (
    <label className={cn('relative inline-flex items-center', disabled ? 'cursor-not-allowed opacity-50' : 'cursor-pointer')}>
      <input
        type="checkbox"
        id={id}
        checked={checked}
        onChange={(e) => !disabled && onChange(e.target.checked)}
        disabled={disabled}
        className="sr-only peer"
      />
      <div className="w-11 h-6 bg-bg-tertiary peer-focus:ring-2 peer-focus:ring-accent/20 rounded-full peer peer-checked:after:translate-x-full rtl:peer-checked:after:-translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:start-[2px] after:bg-white after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-accent"></div>
    </label>
  );

  // Notification item component
  const NotificationItem = ({
    id,
    icon: Icon,
    label,
    description,
    checked,
    onChange,
    disabled = false,
  }: {
    id: string;
    icon: React.ElementType;
    label: string;
    description: string;
    checked: boolean;
    onChange: (checked: boolean) => void;
    disabled?: boolean;
  }) => (
    <div className="flex items-center justify-between p-4 bg-bg-secondary rounded-xl">
      <div className="flex items-start gap-3">
        <Icon className="h-5 w-5 text-text-tertiary mt-0.5 shrink-0" />
        <div>
          <p className="font-medium text-text-primary">{label}</p>
          <p className="text-sm text-text-tertiary">{description}</p>
        </div>
      </div>
      <Toggle id={id} checked={checked} onChange={onChange} disabled={disabled} />
    </div>
  );

  return (
    <div className="space-y-6">
      {/* Push Notification Status */}
      <div className="card rounded-2xl p-6">
        <h2 className="text-lg font-semibold text-text-primary mb-4">
          Push Notification Status
        </h2>

        {!isSupported ? (
          <div className="flex items-center gap-3 p-4 bg-warning-subtle rounded-xl border border-warning/30">
            <AlertCircle className="h-5 w-5 text-warning shrink-0" />
            <div>
              <p className="font-medium text-text-primary">Browser Not Supported</p>
              <p className="text-sm text-text-tertiary">
                Your browser does not support push notifications. Try using Chrome, Firefox, or Edge.
              </p>
            </div>
          </div>
        ) : permission === 'denied' ? (
          <div className="flex items-center gap-3 p-4 bg-negative-subtle rounded-xl border border-negative/30">
            <BellOff className="h-5 w-5 text-negative shrink-0" />
            <div>
              <p className="font-medium text-text-primary">Notifications Blocked</p>
              <p className="text-sm text-text-tertiary">
                Push notifications are blocked. Please enable them in your browser settings to receive alerts.
              </p>
            </div>
          </div>
        ) : permission === 'granted' && fcmToken ? (
          <div className="space-y-4">
            <div className="flex items-center gap-3 p-4 bg-positive-subtle rounded-xl border border-positive/30">
              <CheckCircle className="h-5 w-5 text-positive shrink-0" />
              <div className="flex-1">
                <p className="font-medium text-text-primary">Notifications Enabled</p>
                <p className="text-sm text-text-tertiary">
                  You will receive push notifications for your alerts and high-alpha signals.
                </p>
              </div>
            </div>
            <button
              onClick={handleTestNotification}
              disabled={isSendingTest}
              className="btn btn-secondary flex items-center gap-2"
            >
              {isSendingTest ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <BellRing className="h-4 w-4" />
              )}
              Send Test Notification
            </button>
          </div>
        ) : (
          <div className="flex items-center justify-between p-4 bg-bg-secondary rounded-xl">
            <div className="flex items-center gap-3">
              <Bell className="h-5 w-5 text-text-tertiary" />
              <div>
                <p className="font-medium text-text-primary">Enable Push Notifications</p>
                <p className="text-sm text-text-tertiary">
                  Get instant alerts for high-alpha signals and triggered alerts.
                </p>
              </div>
            </div>
            <button
              onClick={handleEnablePush}
              disabled={contextLoading}
              className="btn btn-primary"
            >
              {contextLoading ? 'Enabling...' : 'Enable'}
            </button>
          </div>
        )}
      </div>

      {/* Email Notifications */}
      <div className="card rounded-2xl p-6">
        <h2 className="text-lg font-semibold text-text-primary mb-4">
          Email Notifications
        </h2>
        <div className="space-y-4">
          <NotificationItem
            id="email-alerts"
            icon={Mail}
            label="Alert Notifications"
            description="Receive emails when your alerts are triggered"
            checked={preferences.emailAlerts}
            onChange={(checked) => updatePreferences({ emailAlerts: checked })}
          />
          <NotificationItem
            id="daily-digest"
            icon={Mail}
            label="Daily Digest"
            description="Get a summary of high-alpha events each day"
            checked={preferences.dailyDigest}
            onChange={(checked) => updatePreferences({ dailyDigest: checked })}
          />
          <NotificationItem
            id="weekly-report"
            icon={Mail}
            label="Weekly Report"
            description="Comprehensive weekly market analysis"
            checked={preferences.weeklyReport}
            onChange={(checked) => updatePreferences({ weeklyReport: checked })}
          />
          <NotificationItem
            id="product-updates"
            icon={Mail}
            label="Product Updates"
            description="Learn about new features and improvements"
            checked={preferences.productUpdates}
            onChange={(checked) => updatePreferences({ productUpdates: checked })}
          />
        </div>
      </div>

      {/* Push Notification Preferences */}
      <div className="card rounded-2xl p-6">
        <h2 className="text-lg font-semibold text-text-primary mb-4">
          Push Notification Preferences
        </h2>
        <div className="space-y-4">
          <NotificationItem
            id="push-enabled"
            icon={Smartphone}
            label="Push Notifications"
            description="Master toggle for all push notifications"
            checked={preferences.pushEnabled}
            onChange={(checked) => updatePreferences({ pushEnabled: checked })}
            disabled={permission !== 'granted'}
          />
          <NotificationItem
            id="realtime-alerts"
            icon={BellRing}
            label="Real-time Alerts"
            description="Get instant push notifications for triggered alerts"
            checked={preferences.realtimeAlerts}
            onChange={(checked) => updatePreferences({ realtimeAlerts: checked })}
            disabled={permission !== 'granted' || !preferences.pushEnabled}
          />
          <NotificationItem
            id="high-alpha-signals"
            icon={AlertCircle}
            label="High Alpha Signals"
            description="Notifications for signals with alpha score above threshold"
            checked={preferences.highAlphaSignals}
            onChange={(checked) => updatePreferences({ highAlphaSignals: checked })}
            disabled={permission !== 'granted' || !preferences.pushEnabled}
          />
        </div>
      </div>

      {/* Alpha Score Threshold */}
      <div className="card rounded-2xl p-6">
        <h2 className="text-lg font-semibold text-text-primary mb-4">
          Alert Threshold
        </h2>
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="font-medium text-text-primary">Minimum Alpha Score</p>
              <p className="text-sm text-text-tertiary">
                Only notify for signals with alpha score above this threshold
              </p>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-lg font-semibold text-accent">
                {Math.round(preferences.minAlphaScore * 100)}%
              </span>
            </div>
          </div>
          <input
            type="range"
            min="0"
            max="100"
            value={preferences.minAlphaScore * 100}
            onChange={(e) => updatePreferences({ minAlphaScore: parseInt(e.target.value) / 100 })}
            className="w-full h-2 bg-bg-tertiary rounded-lg appearance-none cursor-pointer accent-accent"
          />
          <div className="flex justify-between text-xs text-text-tertiary">
            <span>0% (All signals)</span>
            <span>50%</span>
            <span>100% (Only highest)</span>
          </div>
        </div>
      </div>
    </div>
  );
}
