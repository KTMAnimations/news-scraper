'use client';

import { useState } from 'react';
import { Star, StarOff, Plus, RefreshCw, X } from 'lucide-react';
import { useWatchlist } from '@/hooks/useWatchlist';
import { cn } from '@/lib/utils';

interface WatchlistButtonProps {
  ticker: string;
  variant?: 'icon' | 'button' | 'compact';
  showLabel?: boolean;
  className?: string;
  onToggle?: (isWatched: boolean) => void;
}

export function WatchlistButton({
  ticker,
  variant = 'icon',
  showLabel = false,
  className,
  onToggle,
}: WatchlistButtonProps) {
  const { isWatched, toggleWatchlist, isAdding, isRemoving } = useWatchlist();
  const [showNoteModal, setShowNoteModal] = useState(false);
  const [note, setNote] = useState('');

  const watched = isWatched(ticker);
  const isLoading = isAdding || isRemoving;

  const handleClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    e.preventDefault();

    if (watched) {
      toggleWatchlist(ticker);
      onToggle?.(false);
    } else {
      // Show note modal for adding
      setShowNoteModal(true);
    }
  };

  const handleAddWithNote = () => {
    toggleWatchlist(ticker, note || undefined);
    onToggle?.(true);
    setShowNoteModal(false);
    setNote('');
  };

  const handleAddWithoutNote = () => {
    toggleWatchlist(ticker);
    onToggle?.(true);
    setShowNoteModal(false);
    setNote('');
  };

  if (variant === 'icon') {
    return (
      <>
        <button
          onClick={handleClick}
          disabled={isLoading}
          className={cn(
            'p-2 rounded-lg transition-colors',
            watched
              ? 'bg-warning-subtle text-warning hover:bg-warning/20'
              : 'hover:bg-hover text-text-tertiary hover:text-warning',
            isLoading && 'opacity-50 cursor-not-allowed',
            className
          )}
          title={watched ? 'Remove from watchlist' : 'Add to watchlist'}
        >
          {isLoading ? (
            <RefreshCw className="h-5 w-5 animate-spin" />
          ) : watched ? (
            <Star className="h-5 w-5 fill-current" />
          ) : (
            <StarOff className="h-5 w-5" />
          )}
        </button>

        {/* Note Modal */}
        {showNoteModal && (
          <AddNoteModal
            ticker={ticker}
            note={note}
            setNote={setNote}
            onAddWithNote={handleAddWithNote}
            onAddWithoutNote={handleAddWithoutNote}
            onClose={() => {
              setShowNoteModal(false);
              setNote('');
            }}
          />
        )}
      </>
    );
  }

  if (variant === 'compact') {
    return (
      <>
        <button
          onClick={handleClick}
          disabled={isLoading}
          className={cn(
            'flex items-center gap-1.5 px-2 py-1 rounded-md transition-colors text-xs font-medium',
            watched
              ? 'bg-warning-subtle text-warning'
              : 'bg-bg-tertiary text-text-secondary hover:bg-hover hover:text-warning',
            isLoading && 'opacity-50 cursor-not-allowed',
            className
          )}
        >
          {isLoading ? (
            <RefreshCw className="h-3 w-3 animate-spin" />
          ) : watched ? (
            <Star className="h-3 w-3 fill-current" />
          ) : (
            <Plus className="h-3 w-3" />
          )}
          {showLabel && (watched ? 'Watching' : 'Watch')}
        </button>

        {showNoteModal && (
          <AddNoteModal
            ticker={ticker}
            note={note}
            setNote={setNote}
            onAddWithNote={handleAddWithNote}
            onAddWithoutNote={handleAddWithoutNote}
            onClose={() => {
              setShowNoteModal(false);
              setNote('');
            }}
          />
        )}
      </>
    );
  }

  // Button variant
  return (
    <>
      <button
        onClick={handleClick}
        disabled={isLoading}
        className={cn(
          'btn flex items-center gap-2',
          watched ? 'btn-secondary' : 'btn-primary',
          isLoading && 'opacity-50 cursor-not-allowed',
          className
        )}
      >
        {isLoading ? (
          <RefreshCw className="h-4 w-4 animate-spin" />
        ) : watched ? (
          <Star className="h-4 w-4 fill-current text-warning" />
        ) : (
          <Plus className="h-4 w-4" />
        )}
        {watched ? 'Watching' : 'Add to Watchlist'}
      </button>

      {showNoteModal && (
        <AddNoteModal
          ticker={ticker}
          note={note}
          setNote={setNote}
          onAddWithNote={handleAddWithNote}
          onAddWithoutNote={handleAddWithoutNote}
          onClose={() => {
            setShowNoteModal(false);
            setNote('');
          }}
        />
      )}
    </>
  );
}

// Modal component for adding notes
interface AddNoteModalProps {
  ticker: string;
  note: string;
  setNote: (note: string) => void;
  onAddWithNote: () => void;
  onAddWithoutNote: () => void;
  onClose: () => void;
}

function AddNoteModal({
  ticker,
  note,
  setNote,
  onAddWithNote,
  onAddWithoutNote,
  onClose,
}: AddNoteModalProps) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center" onClick={onClose}>
      <div className="absolute inset-0 bg-black/50" />
      <div
        className="relative bg-bg-elevated border border-border rounded-2xl p-6 w-full max-w-md shadow-xl animate-scale-in"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between mb-5">
          <h2 className="text-lg font-semibold text-text-primary">
            Add <span className="text-accent">{ticker}</span> to Watchlist
          </h2>
          <button
            onClick={onClose}
            className="p-2 hover:bg-hover rounded-lg transition-colors"
          >
            <X className="h-4 w-4 text-text-tertiary" />
          </button>
        </div>

        <div className="mb-5">
          <label className="data-label mb-2 block">Notes (optional)</label>
          <textarea
            placeholder="Add any notes about why you're watching this ticker..."
            value={note}
            onChange={(e) => setNote(e.target.value)}
            className="input w-full min-h-[80px] resize-none"
            rows={3}
            autoFocus
          />
        </div>

        <div className="flex gap-3">
          <button onClick={onAddWithoutNote} className="btn btn-secondary flex-1">
            Add Without Note
          </button>
          <button onClick={onAddWithNote} className="btn btn-primary flex-1">
            Add to Watchlist
          </button>
        </div>
      </div>
    </div>
  );
}
