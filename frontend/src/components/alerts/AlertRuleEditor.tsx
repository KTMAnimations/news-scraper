'use client';

import { useState, useEffect } from 'react';
import { useForm, Controller } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import {
  Bell,
  X,
  Save,
  Trash2,
  ChevronDown,
  ChevronUp,
  AlertTriangle,
  Mail,
  Smartphone,
  TrendingUp,
  TrendingDown,
  Minus,
} from 'lucide-react';
import type { Alert, AlertCreate } from '@/types/user';
import { EVENT_TYPES } from '@/types/events';
import { cn } from '@/lib/utils';

const alertSchema = z.object({
  name: z.string().min(1, 'Alert name is required').max(100),
  ticker: z.string().optional(),
  event_types: z.array(z.string()).optional(),
  min_alpha_score: z.number().min(0).max(1).optional(),
  urgency_levels: z.array(z.string()).optional(),
  direction: z.string().optional(),
  delivery_method: z.enum(['push', 'email', 'both']).default('push'),
});

type AlertFormData = z.infer<typeof alertSchema>;

interface AlertRuleEditorProps {
  alert?: Alert;
  onSave: (data: AlertCreate) => Promise<void>;
  onDelete?: () => Promise<void>;
  onCancel: () => void;
  isLoading?: boolean;
  className?: string;
}

const URGENCY_LEVELS = ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW'] as const;

const DIRECTION_OPTIONS = [
  { value: 'BULLISH', label: 'Bullish', icon: TrendingUp, color: 'positive' },
  { value: 'BEARISH', label: 'Bearish', icon: TrendingDown, color: 'negative' },
  { value: 'NEUTRAL', label: 'Neutral', icon: Minus, color: 'text-secondary' },
] as const;

const DELIVERY_OPTIONS = [
  { value: 'push', label: 'Push', icon: Smartphone },
  { value: 'email', label: 'Email', icon: Mail },
  { value: 'both', label: 'Both', icon: Bell },
] as const;

export function AlertRuleEditor({
  alert,
  onSave,
  onDelete,
  onCancel,
  isLoading = false,
  className,
}: AlertRuleEditorProps) {
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [selectedEventTypes, setSelectedEventTypes] = useState<string[]>(
    alert?.event_types || []
  );
  const [selectedUrgencyLevels, setSelectedUrgencyLevels] = useState<string[]>(
    alert?.urgency_levels || []
  );

  const {
    register,
    handleSubmit,
    control,
    setValue,
    watch,
    formState: { errors, isDirty },
  } = useForm<AlertFormData>({
    resolver: zodResolver(alertSchema),
    defaultValues: {
      name: alert?.name || '',
      ticker: alert?.ticker || '',
      event_types: alert?.event_types || [],
      min_alpha_score: alert?.min_alpha_score,
      urgency_levels: alert?.urgency_levels || [],
      direction: alert?.direction || undefined,
      delivery_method: alert?.delivery_method || 'push',
    },
  });

  const watchedDirection = watch('direction');
  const watchedDeliveryMethod = watch('delivery_method');

  useEffect(() => {
    setValue('event_types', selectedEventTypes);
  }, [selectedEventTypes, setValue]);

  useEffect(() => {
    setValue('urgency_levels', selectedUrgencyLevels);
  }, [selectedUrgencyLevels, setValue]);

  const toggleEventType = (type: string) => {
    setSelectedEventTypes((prev) =>
      prev.includes(type) ? prev.filter((t) => t !== type) : [...prev, type]
    );
  };

  const toggleUrgencyLevel = (level: string) => {
    setSelectedUrgencyLevels((prev) =>
      prev.includes(level) ? prev.filter((l) => l !== level) : [...prev, level]
    );
  };

  const formatEventType = (type: string) => {
    return type
      .split('_')
      .map((word) => word.charAt(0) + word.slice(1).toLowerCase())
      .join(' ');
  };

  const onSubmit = async (data: AlertFormData) => {
    const cleanedData: AlertCreate = {
      name: data.name,
      ticker: data.ticker || undefined,
      event_types: data.event_types?.length ? data.event_types : undefined,
      min_alpha_score: data.min_alpha_score,
      urgency_levels: data.urgency_levels?.length ? data.urgency_levels : undefined,
      direction: data.direction || undefined,
      delivery_method: data.delivery_method,
    };
    await onSave(cleanedData);
  };

  return (
    <div className={cn('card p-6', className)}>
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-2">
          <Bell className="h-5 w-5 text-accent" />
          <h3 className="text-lg font-semibold text-text-primary">
            {alert ? 'Edit Alert Rule' : 'Create Alert Rule'}
          </h3>
        </div>
        <button
          onClick={onCancel}
          className="btn btn-ghost p-2"
          disabled={isLoading}
        >
          <X className="h-4 w-4" />
        </button>
      </div>

      <form onSubmit={handleSubmit(onSubmit)} className="space-y-5">
        {/* Alert Name */}
        <div>
          <label className="data-label block mb-2">Alert Name *</label>
          <input
            {...register('name')}
            type="text"
            placeholder="e.g., High Alpha Tesla Events"
            className={cn('input', errors.name && 'border-negative')}
            disabled={isLoading}
          />
          {errors.name && (
            <p className="text-xs text-negative mt-1">{errors.name.message}</p>
          )}
        </div>

        {/* Ticker Filter */}
        <div>
          <label className="data-label block mb-2">Ticker (Optional)</label>
          <input
            {...register('ticker')}
            type="text"
            placeholder="e.g., TSLA"
            className="input"
            disabled={isLoading}
            onChange={(e) => {
              register('ticker').onChange(e);
              e.target.value = e.target.value.toUpperCase();
            }}
          />
          <p className="text-xs text-text-quaternary mt-1">
            Leave empty to match all tickers
          </p>
        </div>

        {/* Direction Filter */}
        <div>
          <label className="data-label block mb-2">Direction</label>
          <div className="flex gap-2">
            {DIRECTION_OPTIONS.map(({ value, label, icon: Icon, color }) => (
              <button
                key={value}
                type="button"
                onClick={() =>
                  setValue('direction', watchedDirection === value ? undefined : value, {
                    shouldDirty: true,
                  })
                }
                disabled={isLoading}
                className={cn(
                  'flex-1 flex items-center justify-center gap-1.5 py-2.5 px-3 rounded-lg border transition-all text-sm font-medium',
                  watchedDirection === value
                    ? value === 'BULLISH'
                      ? 'bg-positive-subtle border-positive text-positive'
                      : value === 'BEARISH'
                      ? 'bg-negative-subtle border-negative text-negative'
                      : 'bg-bg-tertiary border-border-strong text-text-secondary'
                    : 'bg-bg-elevated border-border hover:border-border-strong text-text-secondary hover:text-text-primary'
                )}
              >
                <Icon className="h-4 w-4" />
                {label}
              </button>
            ))}
          </div>
        </div>

        {/* Event Types */}
        <div>
          <label className="data-label block mb-2">Event Types</label>
          <div className="flex flex-wrap gap-2 max-h-32 overflow-y-auto custom-scrollbar p-1">
            {EVENT_TYPES.map((type) => (
              <button
                key={type}
                type="button"
                onClick={() => toggleEventType(type)}
                disabled={isLoading}
                className={cn(
                  'px-3 py-1.5 rounded-lg border text-xs font-medium transition-all',
                  selectedEventTypes.includes(type)
                    ? 'bg-accent-subtle border-accent text-accent'
                    : 'bg-bg-elevated border-border hover:border-border-strong text-text-secondary hover:text-text-primary'
                )}
              >
                {formatEventType(type)}
              </button>
            ))}
          </div>
          <p className="text-xs text-text-quaternary mt-1">
            {selectedEventTypes.length === 0
              ? 'No filter - matches all event types'
              : `${selectedEventTypes.length} type(s) selected`}
          </p>
        </div>

        {/* Min Alpha Score */}
        <div>
          <Controller
            name="min_alpha_score"
            control={control}
            render={({ field }) => (
              <>
                <label className="data-label block mb-2">
                  Min Alpha Score:{' '}
                  {field.value !== undefined ? `${(field.value * 100).toFixed(0)}%` : 'Any'}
                </label>
                <input
                  type="range"
                  min="0"
                  max="100"
                  step="5"
                  value={field.value !== undefined ? field.value * 100 : 0}
                  onChange={(e) => {
                    const value = parseInt(e.target.value);
                    field.onChange(value > 0 ? value / 100 : undefined);
                  }}
                  disabled={isLoading}
                  className="w-full h-2 bg-bg-tertiary rounded-lg appearance-none cursor-pointer
                    [&::-webkit-slider-thumb]:appearance-none
                    [&::-webkit-slider-thumb]:w-4
                    [&::-webkit-slider-thumb]:h-4
                    [&::-webkit-slider-thumb]:rounded-full
                    [&::-webkit-slider-thumb]:bg-accent
                    [&::-webkit-slider-thumb]:cursor-pointer
                    [&::-webkit-slider-thumb]:shadow-md
                    [&::-webkit-slider-thumb]:hover:bg-accent-hover
                    [&::-moz-range-thumb]:w-4
                    [&::-moz-range-thumb]:h-4
                    [&::-moz-range-thumb]:rounded-full
                    [&::-moz-range-thumb]:bg-accent
                    [&::-moz-range-thumb]:cursor-pointer
                    [&::-moz-range-thumb]:border-0"
                />
                <div className="flex justify-between text-xs text-text-quaternary mt-1">
                  <span>0%</span>
                  <span>50%</span>
                  <span>100%</span>
                </div>
              </>
            )}
          />
        </div>

        {/* Delivery Method */}
        <div>
          <label className="data-label block mb-2">Delivery Method</label>
          <div className="flex gap-2">
            {DELIVERY_OPTIONS.map(({ value, label, icon: Icon }) => (
              <button
                key={value}
                type="button"
                onClick={() =>
                  setValue('delivery_method', value, { shouldDirty: true })
                }
                disabled={isLoading}
                className={cn(
                  'flex-1 flex items-center justify-center gap-1.5 py-2.5 px-3 rounded-lg border transition-all text-sm font-medium',
                  watchedDeliveryMethod === value
                    ? 'bg-accent-subtle border-accent text-accent'
                    : 'bg-bg-elevated border-border hover:border-border-strong text-text-secondary hover:text-text-primary'
                )}
              >
                <Icon className="h-4 w-4" />
                {label}
              </button>
            ))}
          </div>
        </div>

        {/* Advanced Options Toggle */}
        <button
          type="button"
          onClick={() => setShowAdvanced(!showAdvanced)}
          className="flex items-center gap-1 text-sm text-text-tertiary hover:text-text-secondary transition-colors"
        >
          {showAdvanced ? (
            <ChevronUp className="h-4 w-4" />
          ) : (
            <ChevronDown className="h-4 w-4" />
          )}
          Advanced Options
        </button>

        {/* Advanced Options */}
        {showAdvanced && (
          <div className="space-y-5 pl-4 border-l-2 border-border animate-fade-in">
            {/* Urgency Levels */}
            <div>
              <label className="data-label block mb-2">Urgency Levels</label>
              <div className="flex gap-2">
                {URGENCY_LEVELS.map((level) => (
                  <button
                    key={level}
                    type="button"
                    onClick={() => toggleUrgencyLevel(level)}
                    disabled={isLoading}
                    className={cn(
                      'px-3 py-1.5 rounded-lg border text-xs font-medium transition-all',
                      selectedUrgencyLevels.includes(level)
                        ? level === 'CRITICAL'
                          ? 'bg-negative-subtle border-negative text-negative'
                          : level === 'HIGH'
                          ? 'bg-warning-subtle border-warning text-warning'
                          : 'bg-accent-subtle border-accent text-accent'
                        : 'bg-bg-elevated border-border hover:border-border-strong text-text-secondary hover:text-text-primary'
                    )}
                  >
                    {level}
                  </button>
                ))}
              </div>
              <p className="text-xs text-text-quaternary mt-1">
                {selectedUrgencyLevels.length === 0
                  ? 'No filter - matches all urgency levels'
                  : `${selectedUrgencyLevels.length} level(s) selected`}
              </p>
            </div>
          </div>
        )}

        {/* Form Actions */}
        <div className="flex items-center justify-between pt-4 border-t border-border">
          {alert && onDelete ? (
            <button
              type="button"
              onClick={onDelete}
              disabled={isLoading}
              className="btn btn-ghost text-negative hover:bg-negative-subtle"
            >
              <Trash2 className="h-4 w-4" />
              Delete
            </button>
          ) : (
            <div />
          )}
          <div className="flex gap-2">
            <button
              type="button"
              onClick={onCancel}
              disabled={isLoading}
              className="btn btn-secondary"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isLoading || (!isDirty && !!alert)}
              className={cn(
                'btn btn-accent',
                (isLoading || (!isDirty && !!alert)) && 'opacity-50 cursor-not-allowed'
              )}
            >
              {isLoading ? (
                <>
                  <div className="h-4 w-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                  Saving...
                </>
              ) : (
                <>
                  <Save className="h-4 w-4" />
                  {alert ? 'Save Changes' : 'Create Alert'}
                </>
              )}
            </button>
          </div>
        </div>
      </form>
    </div>
  );
}
