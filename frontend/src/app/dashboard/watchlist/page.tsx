'use client';

import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Star,
  Plus,
  Trash2,
  Edit2,
  X,
  Check,
  TrendingUp,
  TrendingDown,
  ExternalLink,
  RefreshCw,
  Clock,
} from 'lucide-react';
import { api } from '@/lib/api';
import { cn, formatRelativeTime } from '@/lib/utils';
import type { WatchlistItem } from '@/types/user';
import type { Event } from '@/types/events';

interface AddWatchlistModalProps {
  isOpen: boolean;
  onClose: () => void;
  onAdd: (ticker: string, notes?: string) => void;
  isLoading: boolean;
}

function AddWatchlistModal({
  isOpen,
  onClose,
  onAdd,
  isLoading,
}: AddWatchlistModalProps) {
  const [ticker, setTicker] = useState('');
  const [notes, setNotes] = useState('');

  if (!isOpen) return null;

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (ticker.trim()) {
      onAdd(ticker.trim().toUpperCase(), notes.trim() || undefined);
      setTicker('');
      setNotes('');
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/50" onClick={onClose} />
      <div className="relative bg-bg-elevated border border-border rounded-2xl p-6 w-full max-w-md shadow-xl animate-scale-in">
        <div className="flex items-center justify-between mb-5">
          <h2 className="text-lg font-semibold text-text-primary">
            Add to Watchlist
          </h2>
          <button
            onClick={onClose}
            className="p-2 hover:bg-hover rounded-lg transition-colors"
          >
            <X className="h-4 w-4 text-text-tertiary" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="data-label mb-2 block">Ticker Symbol</label>
            <input
              type="text"
              placeholder="e.g., AAPL"
              value={ticker}
              onChange={(e) => setTicker(e.target.value.toUpperCase())}
              className="input w-full"
              autoFocus
              required
            />
          </div>

          <div>
            <label className="data-label mb-2 block">Notes (optional)</label>
            <textarea
              placeholder="Add any notes about why you're watching this ticker..."
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              className="input w-full min-h-[80px] resize-none"
              rows={3}
            />
          </div>

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
              disabled={!ticker.trim() || isLoading}
              className="btn btn-primary flex-1 flex items-center justify-center gap-2"
            >
              {isLoading ? (
                <>
                  <RefreshCw className="h-4 w-4 animate-spin" />
                  Adding...
                </>
              ) : (
                <>
                  <Plus className="h-4 w-4" />
                  Add to Watchlist
                </>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

export default function WatchlistPage() {
  const queryClient = useQueryClient();
  const [showAddModal, setShowAddModal] = useState(false);
  const [editingItem, setEditingItem] = useState<string | null>(null);
  const [editNotes, setEditNotes] = useState('');
  const [selectedTicker, setSelectedTicker] = useState<string | null>(null);

  // Fetch watchlist
  const { data: watchlist = [], isLoading } = useQuery({
    queryKey: ['watchlist'],
    queryFn: () => api.getWatchlist(),
  });

  // Fetch events for selected ticker
  const { data: tickerEvents = [], isLoading: eventsLoading } = useQuery({
    queryKey: ['ticker-events', selectedTicker],
    queryFn: () => (selectedTicker ? api.getTickerEvents(selectedTicker, 20) : []),
    enabled: !!selectedTicker,
  });

  // Add mutation
  const addMutation = useMutation({
    mutationFn: ({ ticker, notes }: { ticker: string; notes?: string }) =>
      api.addToWatchlist(ticker, notes),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['watchlist'] });
      setShowAddModal(false);
    },
  });

  // Remove mutation
  const removeMutation = useMutation({
    mutationFn: (ticker: string) => api.removeFromWatchlist(ticker),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['watchlist'] });
      if (selectedTicker === removeMutation.variables) {
        setSelectedTicker(null);
      }
    },
  });

  const handleStartEdit = (item: WatchlistItem) => {
    setEditingItem(item.ticker);
    setEditNotes(item.notes || '');
  };

  const handleSaveEdit = async (ticker: string) => {
    // In a real app, this would update the notes via API
    // For now, we'll just clear the editing state
    setEditingItem(null);
    setEditNotes('');
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-text-primary mb-1 tracking-tight flex items-center gap-3">
            <span className="w-10 h-10 rounded-xl bg-warning-subtle flex items-center justify-center">
              <Star className="h-5 w-5 text-warning" />
            </span>
            Watchlist
          </h1>
          <p className="text-text-secondary">
            Track your favorite tickers and get personalized alerts
          </p>
        </div>
        <button
          onClick={() => setShowAddModal(true)}
          className="btn btn-primary flex items-center gap-2"
        >
          <Plus className="h-4 w-4" />
          Add Ticker
        </button>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="card-interactive rounded-2xl p-5">
          <p className="data-label mb-2">Watching</p>
          <p className="font-mono text-3xl font-bold text-text-primary">
            {watchlist.length}
          </p>
          <p className="text-xs text-text-tertiary mt-1">tickers</p>
        </div>
        <div className="card-interactive rounded-2xl p-5">
          <p className="data-label mb-2">Selected Ticker Events</p>
          <p className="font-mono text-3xl font-bold text-accent">
            {tickerEvents.length}
          </p>
          <p className="text-xs text-text-tertiary mt-1">
            {selectedTicker ? `for ${selectedTicker}` : 'select a ticker'}
          </p>
        </div>
        <div className="card-interactive rounded-2xl p-5">
          <p className="data-label mb-2">High Alpha</p>
          <p className="font-mono text-3xl font-bold text-positive">
            {tickerEvents.filter((e) => Math.abs(e.alpha_score || 0) >= 0.7).length}
          </p>
          <p className="text-xs text-text-tertiary mt-1">signals detected</p>
        </div>
      </div>

      {/* Main Content */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Watchlist */}
        <div className="card rounded-2xl overflow-hidden">
          <div className="p-5 border-b border-border">
            <h2 className="text-lg font-semibold text-text-primary">
              Your Watchlist
            </h2>
          </div>
          <div className="max-h-[500px] overflow-y-auto custom-scrollbar">
            {isLoading ? (
              <div className="p-8 text-center">
                <div className="w-8 h-8 skeleton rounded-lg mx-auto mb-3" />
                <p className="text-sm text-text-tertiary">Loading...</p>
              </div>
            ) : watchlist.length === 0 ? (
              <div className="p-12 text-center">
                <div className="w-14 h-14 rounded-2xl bg-warning-subtle mx-auto mb-4 flex items-center justify-center">
                  <Star className="h-6 w-6 text-warning" />
                </div>
                <p className="text-sm font-medium text-text-secondary mb-1">
                  No tickers yet
                </p>
                <p className="text-xs text-text-tertiary mb-4">
                  Add tickers to start tracking
                </p>
                <button
                  onClick={() => setShowAddModal(true)}
                  className="btn btn-primary text-sm"
                >
                  Add Your First Ticker
                </button>
              </div>
            ) : (
              watchlist.map((item) => (
                <div
                  key={item.ticker}
                  onClick={() => setSelectedTicker(item.ticker)}
                  className={cn(
                    'p-4 hover:bg-hover transition-colors cursor-pointer border-b border-border last:border-0',
                    selectedTicker === item.ticker && 'bg-bg-secondary'
                  )}
                >
                  <div className="flex items-center justify-between mb-2">
                    <span className="ticker-chip">{item.ticker}</span>
                    <div className="flex items-center gap-1">
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          handleStartEdit(item);
                        }}
                        className="p-1.5 hover:bg-hover rounded-lg transition-colors"
                        title="Edit notes"
                      >
                        <Edit2 className="h-3.5 w-3.5 text-text-tertiary" />
                      </button>
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          removeMutation.mutate(item.ticker);
                        }}
                        className="p-1.5 hover:bg-negative-subtle rounded-lg transition-colors"
                        title="Remove"
                      >
                        <Trash2 className="h-3.5 w-3.5 text-negative" />
                      </button>
                    </div>
                  </div>

                  {editingItem === item.ticker ? (
                    <div className="mt-2" onClick={(e) => e.stopPropagation()}>
                      <textarea
                        value={editNotes}
                        onChange={(e) => setEditNotes(e.target.value)}
                        className="input w-full text-xs min-h-[60px] resize-none"
                        placeholder="Add notes..."
                      />
                      <div className="flex gap-2 mt-2">
                        <button
                          onClick={() => setEditingItem(null)}
                          className="btn btn-secondary text-xs py-1 px-2"
                        >
                          Cancel
                        </button>
                        <button
                          onClick={() => handleSaveEdit(item.ticker)}
                          className="btn btn-primary text-xs py-1 px-2"
                        >
                          Save
                        </button>
                      </div>
                    </div>
                  ) : item.notes ? (
                    <p className="text-xs text-text-tertiary line-clamp-2">
                      {item.notes}
                    </p>
                  ) : (
                    <p className="text-xs text-text-quaternary italic">
                      No notes
                    </p>
                  )}

                  <p className="text-2xs text-text-quaternary mt-2 flex items-center gap-1">
                    <Clock className="h-2.5 w-2.5" />
                    Added {formatRelativeTime(item.added_at)}
                  </p>
                </div>
              ))
            )}
          </div>
        </div>

        {/* Ticker Events */}
        <div className="lg:col-span-2 card rounded-2xl overflow-hidden">
          <div className="p-5 border-b border-border">
            <h2 className="text-lg font-semibold text-text-primary">
              {selectedTicker ? (
                <>
                  Events for <span className="text-accent">{selectedTicker}</span>
                </>
              ) : (
                'Ticker Events'
              )}
            </h2>
          </div>
          <div className="max-h-[500px] overflow-y-auto custom-scrollbar">
            {!selectedTicker ? (
              <div className="p-12 text-center">
                <div className="w-14 h-14 rounded-2xl bg-bg-tertiary mx-auto mb-4 flex items-center justify-center">
                  <Star className="h-6 w-6 text-text-quaternary" />
                </div>
                <p className="text-sm font-medium text-text-secondary mb-1">
                  Select a ticker
                </p>
                <p className="text-xs text-text-tertiary">
                  Click on a ticker to see its recent events
                </p>
              </div>
            ) : eventsLoading ? (
              <div className="p-8 text-center">
                <div className="w-8 h-8 skeleton rounded-lg mx-auto mb-3" />
                <p className="text-sm text-text-tertiary">Loading events...</p>
              </div>
            ) : tickerEvents.length === 0 ? (
              <div className="p-12 text-center">
                <div className="w-14 h-14 rounded-2xl bg-bg-tertiary mx-auto mb-4 flex items-center justify-center">
                  <span className="text-2xl">📰</span>
                </div>
                <p className="text-sm font-medium text-text-secondary mb-1">
                  No recent events
                </p>
                <p className="text-xs text-text-tertiary">
                  No events found for {selectedTicker}
                </p>
              </div>
            ) : (
              tickerEvents.map((event: Event) => (
                <div
                  key={event.id}
                  className="p-5 hover:bg-hover transition-colors border-b border-border last:border-0"
                >
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-2">
                      <span className="badge badge-neutral text-xs">
                        {event.event_type.replace(/_/g, ' ')}
                      </span>
                      <span
                        className={cn(
                          'flex items-center gap-1 text-xs font-medium',
                          event.direction === 'BULLISH'
                            ? 'text-positive'
                            : event.direction === 'BEARISH'
                            ? 'text-negative'
                            : 'text-text-tertiary'
                        )}
                      >
                        {event.direction === 'BULLISH' ? (
                          <TrendingUp className="h-3 w-3" />
                        ) : event.direction === 'BEARISH' ? (
                          <TrendingDown className="h-3 w-3" />
                        ) : null}
                        {event.direction}
                      </span>
                    </div>
                    <span className="text-xs text-text-tertiary">
                      {formatRelativeTime(event.event_time)}
                    </span>
                  </div>
                  <p className="text-sm text-text-primary font-medium mb-2">
                    {event.headline}
                  </p>
                  {event.summary && (
                    <p className="text-xs text-text-tertiary line-clamp-2 mb-2">
                      {event.summary}
                    </p>
                  )}
                  <div className="flex items-center justify-between">
                    <span className="text-xs text-text-quaternary">
                      {event.source_name}
                    </span>
                    {event.alpha_score !== undefined && (
                      <div className="flex items-center gap-1">
                        <span
                          className={cn(
                            'font-mono text-sm font-bold',
                            Math.abs(event.alpha_score) >= 0.7
                              ? 'text-accent'
                              : 'text-text-secondary'
                          )}
                        >
                          {(event.alpha_score * 100).toFixed(0)}
                        </span>
                        <span className="data-label">alpha</span>
                      </div>
                    )}
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      </div>

      {/* Add Modal */}
      <AddWatchlistModal
        isOpen={showAddModal}
        onClose={() => setShowAddModal(false)}
        onAdd={(ticker, notes) => addMutation.mutate({ ticker, notes })}
        isLoading={addMutation.isPending}
      />
    </div>
  );
}
