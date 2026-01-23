'use client';

import { toast as sonnerToast, ExternalToast } from 'sonner';
import {
  CheckCircle,
  XCircle,
  AlertTriangle,
  Info,
  Bell,
  TrendingUp,
  TrendingDown,
} from 'lucide-react';
import { cn } from '@/lib/utils';

/**
 * Custom toast configuration for the application
 * Uses sonner under the hood with custom styling to match our design system
 */

interface ToastOptions extends Omit<ExternalToast, 'id'> {
  id?: string;
}

/**
 * Show a success toast notification
 */
export function toastSuccess(message: string, options?: ToastOptions) {
  return sonnerToast.success(message, {
    icon: <CheckCircle className="h-5 w-5 text-positive" />,
    ...options,
  });
}

/**
 * Show an error toast notification
 */
export function toastError(message: string, options?: ToastOptions) {
  return sonnerToast.error(message, {
    icon: <XCircle className="h-5 w-5 text-negative" />,
    duration: 5000, // Errors stay longer
    ...options,
  });
}

/**
 * Show a warning toast notification
 */
export function toastWarning(message: string, options?: ToastOptions) {
  return sonnerToast.warning(message, {
    icon: <AlertTriangle className="h-5 w-5 text-warning" />,
    ...options,
  });
}

/**
 * Show an info toast notification
 */
export function toastInfo(message: string, options?: ToastOptions) {
  return sonnerToast.info(message, {
    icon: <Info className="h-5 w-5 text-accent" />,
    ...options,
  });
}

/**
 * Show a loading toast that can be updated
 */
export function toastLoading(message: string, options?: ToastOptions) {
  return sonnerToast.loading(message, options);
}

/**
 * Update an existing toast
 */
export function toastUpdate(id: string | number, message: string, type: 'success' | 'error' | 'warning' | 'info') {
  const icons = {
    success: <CheckCircle className="h-5 w-5 text-positive" />,
    error: <XCircle className="h-5 w-5 text-negative" />,
    warning: <AlertTriangle className="h-5 w-5 text-warning" />,
    info: <Info className="h-5 w-5 text-accent" />,
  };

  return sonnerToast[type](message, { id, icon: icons[type] });
}

/**
 * Dismiss a specific toast or all toasts
 */
export function toastDismiss(id?: string | number) {
  if (id) {
    sonnerToast.dismiss(id);
  } else {
    sonnerToast.dismiss();
  }
}

/**
 * Show an alert notification (for high-alpha events, alerts, etc.)
 */
export function toastAlert(
  title: string,
  description?: string,
  options?: ToastOptions & { direction?: 'BULLISH' | 'BEARISH' | 'NEUTRAL' }
) {
  const { direction, ...rest } = options || {};

  const icon = direction === 'BULLISH' ? (
    <TrendingUp className="h-5 w-5 text-positive" />
  ) : direction === 'BEARISH' ? (
    <TrendingDown className="h-5 w-5 text-negative" />
  ) : (
    <Bell className="h-5 w-5 text-accent" />
  );

  return sonnerToast(title, {
    icon,
    description,
    duration: 6000,
    ...rest,
  });
}

/**
 * Promise-based toast for async operations
 */
export function toastPromise<T>(
  promise: Promise<T>,
  messages: {
    loading: string;
    success: string | ((data: T) => string);
    error: string | ((error: Error) => string);
  }
) {
  return sonnerToast.promise(promise, messages);
}

/**
 * Show a custom toast with action buttons
 */
export function toastAction(
  message: string,
  action: {
    label: string;
    onClick: () => void;
  },
  options?: ToastOptions
) {
  return sonnerToast(message, {
    action: {
      label: action.label,
      onClick: action.onClick,
    },
    ...options,
  });
}

/**
 * Custom toast component for rendering in cards/lists
 * Can be used outside the toast system for inline notifications
 */
interface InlineToastProps {
  type: 'success' | 'error' | 'warning' | 'info';
  message: string;
  onDismiss?: () => void;
  className?: string;
}

export function InlineToast({ type, message, onDismiss, className }: InlineToastProps) {
  const icons = {
    success: CheckCircle,
    error: XCircle,
    warning: AlertTriangle,
    info: Info,
  };

  const colors = {
    success: 'bg-positive-subtle text-positive border-positive',
    error: 'bg-negative-subtle text-negative border-negative',
    warning: 'bg-warning-subtle text-warning border-warning',
    info: 'bg-accent-subtle text-accent border-accent',
  };

  const Icon = icons[type];

  return (
    <div
      className={cn(
        'flex items-center gap-3 p-3 rounded-lg border animate-fade-in',
        colors[type],
        className
      )}
    >
      <Icon className="h-5 w-5 shrink-0" />
      <span className="text-sm flex-1">{message}</span>
      {onDismiss && (
        <button
          onClick={onDismiss}
          className="shrink-0 hover:opacity-70 transition-opacity"
        >
          <XCircle className="h-4 w-4" />
        </button>
      )}
    </div>
  );
}

/**
 * Export all toast functions as a single object for convenience
 */
export const toast = {
  success: toastSuccess,
  error: toastError,
  warning: toastWarning,
  info: toastInfo,
  loading: toastLoading,
  update: toastUpdate,
  dismiss: toastDismiss,
  alert: toastAlert,
  promise: toastPromise,
  action: toastAction,
};

export default toast;
