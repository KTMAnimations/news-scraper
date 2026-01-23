'use client';

import { useConnectionStatus } from '@/contexts/WebSocketContext';
import { Wifi, WifiOff, RefreshCw, AlertCircle } from 'lucide-react';

type StatusConfig = {
  label: string;
  shortLabel: string;
  bgColor: string;
  textColor: string;
  dotColor: string;
  icon: React.ComponentType<{ className?: string }>;
  animate?: boolean;
};

const statusConfigs: Record<string, StatusConfig> = {
  connected: {
    label: 'Live',
    shortLabel: 'Live',
    bgColor: 'bg-positive-subtle',
    textColor: 'text-positive',
    dotColor: 'bg-positive',
    icon: Wifi,
    animate: true,
  },
  connecting: {
    label: 'Connecting...',
    shortLabel: 'Connecting',
    bgColor: 'bg-warning-subtle',
    textColor: 'text-warning',
    dotColor: 'bg-warning',
    icon: RefreshCw,
    animate: true,
  },
  reconnecting: {
    label: 'Reconnecting...',
    shortLabel: 'Reconnecting',
    bgColor: 'bg-warning-subtle',
    textColor: 'text-warning',
    dotColor: 'bg-warning',
    icon: RefreshCw,
    animate: true,
  },
  disconnected: {
    label: 'Disconnected',
    shortLabel: 'Offline',
    bgColor: 'bg-bg-tertiary',
    textColor: 'text-text-tertiary',
    dotColor: 'bg-text-quaternary',
    icon: WifiOff,
    animate: false,
  },
  error: {
    label: 'Connection Error',
    shortLabel: 'Error',
    bgColor: 'bg-negative-subtle',
    textColor: 'text-negative',
    dotColor: 'bg-negative',
    icon: AlertCircle,
    animate: false,
  },
};

interface ConnectionStatusProps {
  showLabel?: boolean;
  compact?: boolean;
  showReconnectInfo?: boolean;
  onClick?: () => void;
}

export function ConnectionStatus({
  showLabel = true,
  compact = false,
  showReconnectInfo = true,
  onClick,
}: ConnectionStatusProps) {
  const { status, reconnectAttempt, maxReconnectAttempts, reconnect } = useConnectionStatus();

  const config = statusConfigs[status] || statusConfigs.disconnected;
  const Icon = config.icon;

  const handleClick = () => {
    if (onClick) {
      onClick();
    } else if (status === 'disconnected' || status === 'error') {
      reconnect();
    }
  };

  const isClickable = status === 'disconnected' || status === 'error';
  const showReconnectAttempt = showReconnectInfo && status === 'reconnecting' && reconnectAttempt > 0;

  if (compact) {
    return (
      <button
        onClick={handleClick}
        disabled={!isClickable}
        className={`
          flex items-center justify-center w-8 h-8 rounded-lg transition-colors
          ${config.bgColor}
          ${isClickable ? 'cursor-pointer hover:opacity-80' : 'cursor-default'}
        `}
        title={`${config.label}${showReconnectAttempt ? ` (${reconnectAttempt}/${maxReconnectAttempts})` : ''}${isClickable ? ' - Click to reconnect' : ''}`}
      >
        <Icon
          className={`
            h-4 w-4 ${config.textColor}
            ${config.animate && status === 'reconnecting' ? 'animate-spin' : ''}
          `}
        />
      </button>
    );
  }

  return (
    <button
      onClick={handleClick}
      disabled={!isClickable}
      className={`
        flex items-center gap-2 px-3 py-1.5 rounded-full transition-all
        ${config.bgColor}
        ${isClickable ? 'cursor-pointer hover:opacity-80 active:scale-95' : 'cursor-default'}
      `}
      title={isClickable ? 'Click to reconnect' : undefined}
    >
      {/* Animated dot for connected state */}
      {status === 'connected' && (
        <div className="relative">
          <div className={`w-2 h-2 ${config.dotColor} rounded-full`} />
          <div className={`absolute inset-0 w-2 h-2 ${config.dotColor} rounded-full animate-ping opacity-75`} />
        </div>
      )}

      {/* Icon for other states */}
      {status !== 'connected' && (
        <Icon
          className={`
            h-3.5 w-3.5 ${config.textColor}
            ${config.animate && (status === 'connecting' || status === 'reconnecting') ? 'animate-spin' : ''}
          `}
        />
      )}

      {/* Label */}
      {showLabel && (
        <span className={`text-xs font-medium ${config.textColor}`}>
          {showReconnectAttempt
            ? `Reconnecting (${reconnectAttempt}/${maxReconnectAttempts})`
            : config.label}
        </span>
      )}
    </button>
  );
}

// Minimal dot indicator for very compact layouts
export function ConnectionDot() {
  const { status, reconnect } = useConnectionStatus();
  const config = statusConfigs[status] || statusConfigs.disconnected;
  const isClickable = status === 'disconnected' || status === 'error';

  return (
    <button
      onClick={isClickable ? reconnect : undefined}
      disabled={!isClickable}
      className={`
        relative w-2.5 h-2.5 rounded-full transition-all
        ${config.dotColor}
        ${isClickable ? 'cursor-pointer hover:scale-125' : 'cursor-default'}
      `}
      title={`${config.label}${isClickable ? ' - Click to reconnect' : ''}`}
    >
      {status === 'connected' && (
        <span className={`absolute inset-0 ${config.dotColor} rounded-full animate-ping opacity-75`} />
      )}
      {(status === 'connecting' || status === 'reconnecting') && (
        <span className={`absolute inset-0 ${config.dotColor} rounded-full animate-pulse`} />
      )}
    </button>
  );
}
