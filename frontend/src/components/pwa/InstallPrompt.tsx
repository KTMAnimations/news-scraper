'use client';

import { useState } from 'react';
import { Download, X, Bell, Smartphone } from 'lucide-react';
import { usePWA } from '@/hooks/usePWA';
import { cn } from '@/lib/utils';

interface InstallPromptProps {
  className?: string;
}

export function InstallPrompt({ className }: InstallPromptProps) {
  const {
    canInstall,
    isInstalled,
    install,
    requestNotificationPermission,
    notificationPermission,
  } = usePWA();
  const [isDismissed, setIsDismissed] = useState(false);
  const [isInstalling, setIsInstalling] = useState(false);

  // Don't show if dismissed, already installed, or can't install
  if (isDismissed || isInstalled || !canInstall) {
    return null;
  }

  const handleInstall = async () => {
    setIsInstalling(true);
    const success = await install();
    setIsInstalling(false);
    if (success) {
      setIsDismissed(true);
    }
  };

  return (
    <div
      className={cn(
        'fixed bottom-4 left-4 right-4 md:left-auto md:right-4 md:max-w-sm z-50',
        'card rounded-2xl p-4 shadow-lg border border-border-strong',
        'animate-slide-up',
        className
      )}
    >
      <button
        onClick={() => setIsDismissed(true)}
        className="absolute top-3 right-3 p-1 hover:bg-hover rounded-lg transition-colors"
        aria-label="Dismiss"
      >
        <X className="h-4 w-4 text-text-tertiary" />
      </button>

      <div className="flex items-start gap-3">
        <div className="w-12 h-12 rounded-xl bg-accent-subtle flex items-center justify-center shrink-0">
          <Smartphone className="h-6 w-6 text-accent" />
        </div>

        <div className="flex-1 min-w-0">
          <h3 className="font-semibold text-text-primary mb-1">
            Install Micro-Alpha
          </h3>
          <p className="text-sm text-text-secondary mb-3">
            Get instant access from your home screen with offline support.
          </p>

          <div className="flex items-center gap-2">
            <button
              onClick={handleInstall}
              disabled={isInstalling}
              className="btn btn-primary flex items-center gap-2 text-sm px-4 py-2"
            >
              <Download className="h-4 w-4" />
              {isInstalling ? 'Installing...' : 'Install App'}
            </button>

            <button
              onClick={() => setIsDismissed(true)}
              className="btn btn-secondary text-sm px-4 py-2"
            >
              Not now
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

/**
 * Notification permission button component
 */
interface NotificationButtonProps {
  className?: string;
  variant?: 'default' | 'compact';
}

export function NotificationButton({ className, variant = 'default' }: NotificationButtonProps) {
  const { requestNotificationPermission, notificationPermission, isServiceWorkerActive } = usePWA();
  const [isRequesting, setIsRequesting] = useState(false);

  // Don't show if already granted or service worker not active
  if (!isServiceWorkerActive || notificationPermission === 'granted') {
    return null;
  }

  // If denied, show disabled state
  if (notificationPermission === 'denied') {
    return (
      <button
        disabled
        className={cn(
          'flex items-center gap-2 text-sm text-text-tertiary opacity-50 cursor-not-allowed',
          className
        )}
        title="Notifications blocked. Enable in browser settings."
      >
        <Bell className="h-4 w-4" />
        {variant === 'default' && <span>Notifications blocked</span>}
      </button>
    );
  }

  const handleRequest = async () => {
    setIsRequesting(true);
    await requestNotificationPermission();
    setIsRequesting(false);
  };

  if (variant === 'compact') {
    return (
      <button
        onClick={handleRequest}
        disabled={isRequesting}
        className={cn(
          'p-2 hover:bg-hover rounded-lg transition-colors',
          className
        )}
        title="Enable notifications"
      >
        <Bell className="h-5 w-5 text-text-secondary" />
      </button>
    );
  }

  return (
    <button
      onClick={handleRequest}
      disabled={isRequesting}
      className={cn(
        'flex items-center gap-2 px-3 py-2 text-sm',
        'hover:bg-hover rounded-lg transition-colors',
        'text-text-secondary hover:text-text-primary',
        className
      )}
    >
      <Bell className="h-4 w-4" />
      <span>{isRequesting ? 'Requesting...' : 'Enable notifications'}</span>
    </button>
  );
}
