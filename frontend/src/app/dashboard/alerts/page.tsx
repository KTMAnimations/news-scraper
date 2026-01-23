'use client';

import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Bell,
  Plus,
  Trash2,
  Edit2,
  X,
  Check,
  Power,
  TrendingUp,
  TrendingDown,
  Mail,
  Smartphone,
  RefreshCw,
  Clock,
  Zap,
} from 'lucide-react';
import { api } from '@/lib/api';
import { cn, formatRelativeTime } from '@/lib/utils';
import type { Alert, AlertCreate } from '@/types/user';
import { EVENT_TYPES } from '@/types/events';

interface AlertFormData {
  name: string;
  ticker?: string;
  event_types: string[];
  min_alpha_score?: number;
  urgency_levels: string[];
  direction?: string;
  delivery_method: 'push' | 'email' | 'both';
}

interface AlertModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSave: (data: AlertCreate) => void;
  isLoading: boolean;
  initialData?: Alert;
}

function AlertModal({
  isOpen,
  onClose,
  onSave,
  isLoading,
  initialData,
}: AlertModalProps) {
  const [formData, setFormData] = useState<AlertFormData>({
    name: initialData?.name || '',
    ticker: initialData?.ticker || '',
    event_types: initialData?.event_types || [],
    min_alpha_score: initialData?.min_alpha_score
      ? initialData.min_alpha_score * 100
      : undefined,
    urgency_levels: initialData?.urgency_levels || [],
    direction: initialData?.direction || '',
    delivery_method: initialData?.delivery_method || 'push',
  });

  if (!isOpen) return null;

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onSave({
      name: formData.name,
      ticker: formData.ticker || undefined,
      event_types: formData.event_types.length ? formData.event_types : undefined,
      min_alpha_score: formData.min_alpha_score
        ? formData.min_alpha_score / 100
        : undefined,
      urgency_levels: formData.urgency_levels.length
        ? formData.urgency_levels
        : undefined,
      direction: formData.direction || undefined,
      delivery_method: formData.delivery_method,
    });
  };

  const toggleEventType = (type: string) => {
    setFormData((prev) => ({
      ...prev,
      event_types: prev.event_types.includes(type)
        ? prev.event_types.filter((t) => t !== type)
        : [...prev.event_types, type],
    }));
  };

  const toggleUrgency = (level: string) => {
    setFormData((prev) => ({
      ...prev,
      urgency_levels: prev.urgency_levels.includes(level)
        ? prev.urgency_levels.filter((l) => l !== level)
        : [...prev.urgency_levels, level],
    }));
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center overflow-y-auto py-8">
      <div className="absolute inset-0 bg-black/50" onClick={onClose} />
      <div className="relative bg-bg-elevated border border-border rounded-2xl p-6 w-full max-w-lg shadow-xl animate-scale-in mx-4">
        <div className="flex items-center justify-between mb-5">
          <h2 className="text-lg font-semibold text-text-primary">
            {initialData ? 'Edit Alert' : 'Create Alert'}
          </h2>
          <button
            onClick={onClose}
            className="p-2 hover:bg-hover rounded-lg transition-colors"
          >
            <X className="h-4 w-4 text-text-tertiary" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="space-y-5">
          {/* Alert Name */}
          <div>
            <label className="data-label mb-2 block">Alert Name</label>
            <input
              type="text"
              placeholder="e.g., High Alpha FDA Events"
              value={formData.name}
              onChange={(e) =>
                setFormData((prev) => ({ ...prev, name: e.target.value }))
              }
              className="input w-full"
              required
            />
          </div>

          {/* Ticker (Optional) */}
          <div>
            <label className="data-label mb-2 block">
              Ticker <span className="text-text-quaternary">(optional)</span>
            </label>
            <input
              type="text"
              placeholder="e.g., AAPL (leave empty for all tickers)"
              value={formData.ticker}
              onChange={(e) =>
                setFormData((prev) => ({
                  ...prev,
                  ticker: e.target.value.toUpperCase(),
                }))
              }
              className="input w-full"
            />
          </div>

          {/* Direction */}
          <div>
            <label className="data-label mb-2 block">Direction</label>
            <div className="flex gap-2">
              {['', 'BULLISH', 'BEARISH'].map((dir) => (
                <button
                  key={dir || 'any'}
                  type="button"
                  onClick={() =>
                    setFormData((prev) => ({ ...prev, direction: dir }))
                  }
                  className={cn(
                    'flex-1 flex items-center justify-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium transition-colors',
                    formData.direction === dir
                      ? dir === 'BULLISH'
                        ? 'bg-positive-subtle text-positive'
                        : dir === 'BEARISH'
                        ? 'bg-negative-subtle text-negative'
                        : 'bg-text-primary text-bg-primary'
                      : 'bg-bg-tertiary text-text-secondary hover:bg-hover'
                  )}
                >
                  {dir === 'BULLISH' ? (
                    <TrendingUp className="h-3.5 w-3.5" />
                  ) : dir === 'BEARISH' ? (
                    <TrendingDown className="h-3.5 w-3.5" />
                  ) : null}
                  {dir || 'Any'}
                </button>
              ))}
            </div>
          </div>

          {/* Min Alpha Score */}
          <div>
            <label className="data-label mb-2 block">
              Minimum Alpha Score{' '}
              <span className="text-text-quaternary">(optional)</span>
            </label>
            <input
              type="number"
              min="0"
              max="100"
              step="10"
              placeholder="e.g., 70"
              value={formData.min_alpha_score || ''}
              onChange={(e) =>
                setFormData((prev) => ({
                  ...prev,
                  min_alpha_score: e.target.value
                    ? Number(e.target.value)
                    : undefined,
                }))
              }
              className="input w-full"
            />
          </div>

          {/* Urgency Levels */}
          <div>
            <label className="data-label mb-2 block">Urgency Levels</label>
            <div className="flex flex-wrap gap-2">
              {['CRITICAL', 'HIGH', 'MEDIUM', 'LOW'].map((level) => (
                <button
                  key={level}
                  type="button"
                  onClick={() => toggleUrgency(level)}
                  className={cn(
                    'px-3 py-1.5 rounded-lg text-xs font-medium transition-colors',
                    formData.urgency_levels.includes(level)
                      ? level === 'CRITICAL'
                        ? 'bg-negative text-white'
                        : level === 'HIGH'
                        ? 'bg-warning text-white'
                        : level === 'MEDIUM'
                        ? 'bg-accent text-white'
                        : 'bg-text-secondary text-white'
                      : 'bg-bg-tertiary text-text-secondary hover:bg-hover'
                  )}
                >
                  {level}
                </button>
              ))}
            </div>
          </div>

          {/* Event Types */}
          <div>
            <label className="data-label mb-2 block">
              Event Types{' '}
              <span className="text-text-quaternary">(leave empty for all)</span>
            </label>
            <div className="flex flex-wrap gap-1.5 max-h-32 overflow-y-auto">
              {EVENT_TYPES.map((type) => (
                <button
                  key={type}
                  type="button"
                  onClick={() => toggleEventType(type)}
                  className={cn(
                    'px-2 py-1 rounded text-2xs font-medium transition-colors',
                    formData.event_types.includes(type)
                      ? 'bg-accent text-white'
                      : 'bg-bg-tertiary text-text-tertiary hover:bg-hover'
                  )}
                >
                  {type.replace(/_/g, ' ')}
                </button>
              ))}
            </div>
          </div>

          {/* Delivery Method */}
          <div>
            <label className="data-label mb-2 block">Delivery Method</label>
            <div className="flex gap-2">
              {[
                { value: 'push', label: 'Push', icon: Smartphone },
                { value: 'email', label: 'Email', icon: Mail },
                { value: 'both', label: 'Both', icon: Bell },
              ].map(({ value, label, icon: Icon }) => (
                <button
                  key={value}
                  type="button"
                  onClick={() =>
                    setFormData((prev) => ({
                      ...prev,
                      delivery_method: value as 'push' | 'email' | 'both',
                    }))
                  }
                  className={cn(
                    'flex-1 flex items-center justify-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium transition-colors',
                    formData.delivery_method === value
                      ? 'bg-text-primary text-bg-primary'
                      : 'bg-bg-tertiary text-text-secondary hover:bg-hover'
                  )}
                >
                  <Icon className="h-3.5 w-3.5" />
                  {label}
                </button>
              ))}
            </div>
          </div>

          {/* Actions */}
          <div className="flex gap-3 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="btn btn-secondary flex-1"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={!formData.name.trim() || isLoading}
              className="btn btn-primary flex-1 flex items-center justify-center gap-2"
            >
              {isLoading ? (
                <>
                  <RefreshCw className="h-4 w-4 animate-spin" />
                  Saving...
                </>
              ) : (
                <>
                  <Check className="h-4 w-4" />
                  {initialData ? 'Update Alert' : 'Create Alert'}
                </>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

export default function AlertsPage() {
  const queryClient = useQueryClient();
  const [showModal, setShowModal] = useState(false);
  const [editingAlert, setEditingAlert] = useState<Alert | null>(null);

  // Fetch alerts
  const { data: alerts = [], isLoading } = useQuery({
    queryKey: ['alerts'],
    queryFn: () => api.getAlerts(),
  });

  // Create mutation
  const createMutation = useMutation({
    mutationFn: (data: AlertCreate) => api.createAlert(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['alerts'] });
      setShowModal(false);
    },
  });

  // Update mutation
  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: Partial<AlertCreate> }) =>
      api.updateAlert(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['alerts'] });
      setEditingAlert(null);
    },
  });

  // Delete mutation
  const deleteMutation = useMutation({
    mutationFn: (id: string) => api.deleteAlert(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['alerts'] });
    },
  });

  // Toggle active mutation
  const toggleMutation = useMutation({
    mutationFn: ({ id, is_active }: { id: string; is_active: boolean }) =>
      api.updateAlert(id, { is_active }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['alerts'] });
    },
  });

  const activeAlerts = alerts.filter((a) => a.is_active);
  const inactiveAlerts = alerts.filter((a) => !a.is_active);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-text-primary mb-1 tracking-tight flex items-center gap-3">
            <span className="w-10 h-10 rounded-xl bg-accent-subtle flex items-center justify-center">
              <Bell className="h-5 w-5 text-accent" />
            </span>
            Alerts
          </h1>
          <p className="text-text-secondary">
            Configure custom alerts for market events
          </p>
        </div>
        <button
          onClick={() => setShowModal(true)}
          className="btn btn-primary flex items-center gap-2"
        >
          <Plus className="h-4 w-4" />
          Create Alert
        </button>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="card-interactive rounded-2xl p-5">
          <div className="flex items-center gap-3">
            <div className="w-12 h-12 rounded-xl bg-positive-subtle flex items-center justify-center">
              <Power className="h-5 w-5 text-positive" />
            </div>
            <div>
              <p className="data-label mb-1">Active Alerts</p>
              <p className="font-mono text-3xl font-bold text-positive">
                {activeAlerts.length}
              </p>
            </div>
          </div>
        </div>

        <div className="card-interactive rounded-2xl p-5">
          <div className="flex items-center gap-3">
            <div className="w-12 h-12 rounded-xl bg-bg-tertiary flex items-center justify-center">
              <Power className="h-5 w-5 text-text-tertiary" />
            </div>
            <div>
              <p className="data-label mb-1">Paused Alerts</p>
              <p className="font-mono text-3xl font-bold text-text-tertiary">
                {inactiveAlerts.length}
              </p>
            </div>
          </div>
        </div>

        <div className="card-interactive rounded-2xl p-5">
          <div className="flex items-center gap-3">
            <div className="w-12 h-12 rounded-xl bg-accent-subtle flex items-center justify-center">
              <Zap className="h-5 w-5 text-accent" />
            </div>
            <div>
              <p className="data-label mb-1">Triggered Today</p>
              <p className="font-mono text-3xl font-bold text-accent">
                {alerts.filter((a) => a.last_triggered_at && new Date(a.last_triggered_at).toDateString() === new Date().toDateString()).length}
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Alerts List */}
      <div className="card rounded-2xl overflow-hidden">
        <div className="p-5 border-b border-border">
          <h2 className="text-lg font-semibold text-text-primary">
            Your Alerts
          </h2>
        </div>

        {isLoading ? (
          <div className="p-8 text-center">
            <div className="w-8 h-8 skeleton rounded-lg mx-auto mb-3" />
            <p className="text-sm text-text-tertiary">Loading alerts...</p>
          </div>
        ) : alerts.length === 0 ? (
          <div className="p-12 text-center">
            <div className="w-14 h-14 rounded-2xl bg-accent-subtle mx-auto mb-4 flex items-center justify-center">
              <Bell className="h-6 w-6 text-accent" />
            </div>
            <p className="text-sm font-medium text-text-secondary mb-1">
              No alerts configured
            </p>
            <p className="text-xs text-text-tertiary mb-4">
              Create your first alert to get notified about market events
            </p>
            <button
              onClick={() => setShowModal(true)}
              className="btn btn-primary text-sm"
            >
              Create Your First Alert
            </button>
          </div>
        ) : (
          <div className="divide-y divide-border">
            {alerts.map((alert) => (
              <div
                key={alert.id}
                className={cn(
                  'p-5 transition-colors',
                  !alert.is_active && 'opacity-60'
                )}
              >
                <div className="flex items-start justify-between mb-3">
                  <div className="flex items-center gap-3">
                    <button
                      onClick={() =>
                        toggleMutation.mutate({
                          id: alert.id,
                          is_active: !alert.is_active,
                        })
                      }
                      className={cn(
                        'w-10 h-10 rounded-xl flex items-center justify-center transition-colors',
                        alert.is_active
                          ? 'bg-positive-subtle'
                          : 'bg-bg-tertiary'
                      )}
                    >
                      <Power
                        className={cn(
                          'h-5 w-5',
                          alert.is_active ? 'text-positive' : 'text-text-tertiary'
                        )}
                      />
                    </button>
                    <div>
                      <h3 className="font-medium text-text-primary">
                        {alert.name}
                      </h3>
                      <div className="flex items-center gap-2 mt-1">
                        {alert.ticker && (
                          <span className="ticker-chip text-xs">
                            {alert.ticker}
                          </span>
                        )}
                        {alert.direction && (
                          <span
                            className={cn(
                              'flex items-center gap-1 text-xs font-medium px-2 py-0.5 rounded',
                              alert.direction === 'BULLISH'
                                ? 'bg-positive-subtle text-positive'
                                : 'bg-negative-subtle text-negative'
                            )}
                          >
                            {alert.direction === 'BULLISH' ? (
                              <TrendingUp className="h-3 w-3" />
                            ) : (
                              <TrendingDown className="h-3 w-3" />
                            )}
                            {alert.direction}
                          </span>
                        )}
                        {alert.min_alpha_score && (
                          <span className="badge badge-accent text-xs">
                            α ≥ {(alert.min_alpha_score * 100).toFixed(0)}
                          </span>
                        )}
                      </div>
                    </div>
                  </div>

                  <div className="flex items-center gap-1">
                    <button
                      onClick={() => setEditingAlert(alert)}
                      className="p-2 hover:bg-hover rounded-lg transition-colors"
                      title="Edit"
                    >
                      <Edit2 className="h-4 w-4 text-text-tertiary" />
                    </button>
                    <button
                      onClick={() => deleteMutation.mutate(alert.id)}
                      className="p-2 hover:bg-negative-subtle rounded-lg transition-colors"
                      title="Delete"
                    >
                      <Trash2 className="h-4 w-4 text-negative" />
                    </button>
                  </div>
                </div>

                <div className="flex flex-wrap items-center gap-3 text-xs text-text-tertiary">
                  {/* Event Types */}
                  {alert.event_types && alert.event_types.length > 0 && (
                    <div className="flex items-center gap-1">
                      <span>Types:</span>
                      <span className="text-text-secondary">
                        {alert.event_types.length > 2
                          ? `${alert.event_types.slice(0, 2).join(', ')} +${alert.event_types.length - 2}`
                          : alert.event_types.join(', ')}
                      </span>
                    </div>
                  )}

                  {/* Urgency */}
                  {alert.urgency_levels && alert.urgency_levels.length > 0 && (
                    <div className="flex items-center gap-1">
                      <span>Urgency:</span>
                      <span className="text-text-secondary">
                        {alert.urgency_levels.join(', ')}
                      </span>
                    </div>
                  )}

                  {/* Delivery */}
                  <div className="flex items-center gap-1">
                    {alert.delivery_method === 'push' && (
                      <Smartphone className="h-3 w-3" />
                    )}
                    {alert.delivery_method === 'email' && (
                      <Mail className="h-3 w-3" />
                    )}
                    {alert.delivery_method === 'both' && (
                      <>
                        <Smartphone className="h-3 w-3" />
                        <Mail className="h-3 w-3" />
                      </>
                    )}
                  </div>

                  {/* Last triggered */}
                  {alert.last_triggered_at && (
                    <div className="flex items-center gap-1 ml-auto">
                      <Clock className="h-3 w-3" />
                      Last: {formatRelativeTime(alert.last_triggered_at)}
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Create Modal */}
      <AlertModal
        isOpen={showModal}
        onClose={() => setShowModal(false)}
        onSave={(data) => createMutation.mutate(data)}
        isLoading={createMutation.isPending}
      />

      {/* Edit Modal */}
      {editingAlert && (
        <AlertModal
          isOpen={true}
          onClose={() => setEditingAlert(null)}
          onSave={(data) =>
            updateMutation.mutate({ id: editingAlert.id, data })
          }
          isLoading={updateMutation.isPending}
          initialData={editingAlert}
        />
      )}
    </div>
  );
}
