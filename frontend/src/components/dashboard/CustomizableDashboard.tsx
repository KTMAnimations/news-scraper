'use client';

import { useState, useCallback, useMemo } from 'react';
import { Responsive, WidthProvider, Layout } from 'react-grid-layout';
import { Settings, RotateCcw, Lock, Unlock, X, Eye, EyeOff } from 'lucide-react';
import { useLayoutStore, DEFAULT_LAYOUTS, DEFAULT_WIDGETS, type WidgetType } from '@/store/layoutStore';
import {
  StatsWidget,
  EventFeedWidget,
  HighAlphaWidget,
  WatchlistWidget,
  SentimentChartWidget,
} from './DashboardWidgets';
import { cn } from '@/lib/utils';

// Import react-grid-layout styles
import 'react-grid-layout/css/styles.css';
import 'react-resizable/css/styles.css';

const ResponsiveGridLayout = WidthProvider(Responsive);

// Widget component mapping
const WIDGET_COMPONENTS: Record<WidgetType, React.ComponentType> = {
  stats: StatsWidget,
  eventFeed: EventFeedWidget,
  highAlpha: HighAlphaWidget,
  watchlist: WatchlistWidget,
  sentimentChart: SentimentChartWidget,
};

// Widget wrapper component
interface WidgetWrapperProps {
  id: string;
  title: string;
  isEditMode: boolean;
  children: React.ReactNode;
  onRemove?: () => void;
}

function WidgetWrapper({ id, title, isEditMode, children, onRemove }: WidgetWrapperProps) {
  return (
    <div className={cn(
      'h-full relative group',
      isEditMode && 'ring-2 ring-dashed ring-border-strong rounded-2xl'
    )}>
      {isEditMode && (
        <div className="absolute top-2 left-2 right-2 z-10 flex items-center justify-between bg-bg-elevated/90 backdrop-blur-sm rounded-lg px-3 py-1.5 opacity-0 group-hover:opacity-100 transition-opacity">
          <span className="text-xs font-medium text-text-secondary cursor-move">
            {title}
          </span>
          {onRemove && (
            <button
              onClick={onRemove}
              className="p-1 hover:bg-negative-subtle rounded text-text-tertiary hover:text-negative transition-colors"
              title="Hide widget"
            >
              <EyeOff className="h-3 w-3" />
            </button>
          )}
        </div>
      )}
      {children}
    </div>
  );
}

// Settings panel for showing/hiding widgets
interface WidgetSettingsPanelProps {
  isOpen: boolean;
  onClose: () => void;
}

function WidgetSettingsPanel({ isOpen, onClose }: WidgetSettingsPanelProps) {
  const { widgets, toggleWidgetVisibility, resetToDefault } = useLayoutStore();

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center" onClick={onClose}>
      <div className="absolute inset-0 bg-black/50" />
      <div
        className="relative bg-bg-elevated border border-border rounded-2xl p-6 w-full max-w-md shadow-xl animate-scale-in"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between mb-5">
          <h2 className="text-lg font-semibold text-text-primary">Dashboard Settings</h2>
          <button
            onClick={onClose}
            className="p-2 hover:bg-hover rounded-lg transition-colors"
          >
            <X className="h-4 w-4 text-text-tertiary" />
          </button>
        </div>

        <div className="space-y-3 mb-6">
          <p className="data-label">Visible Widgets</p>
          {widgets.map((widget) => (
            <button
              key={widget.id}
              onClick={() => toggleWidgetVisibility(widget.id)}
              className={cn(
                'w-full flex items-center justify-between p-3 rounded-xl border transition-colors',
                widget.visible
                  ? 'border-accent bg-accent-subtle'
                  : 'border-border hover:border-border-strong'
              )}
            >
              <span className={cn(
                'text-sm font-medium',
                widget.visible ? 'text-accent' : 'text-text-secondary'
              )}>
                {widget.title}
              </span>
              {widget.visible ? (
                <Eye className="h-4 w-4 text-accent" />
              ) : (
                <EyeOff className="h-4 w-4 text-text-quaternary" />
              )}
            </button>
          ))}
        </div>

        <div className="flex gap-3">
          <button
            onClick={() => {
              resetToDefault();
              onClose();
            }}
            className="btn btn-secondary flex-1 flex items-center justify-center gap-2"
          >
            <RotateCcw className="h-4 w-4" />
            Reset to Default
          </button>
          <button onClick={onClose} className="btn btn-primary flex-1">
            Done
          </button>
        </div>
      </div>
    </div>
  );
}

export function CustomizableDashboard() {
  const {
    layouts,
    widgets,
    isEditMode,
    setEditMode,
    updateLayout,
    toggleWidgetVisibility,
    resetToDefault,
  } = useLayoutStore();

  const [showSettings, setShowSettings] = useState(false);

  // Filter visible widgets
  const visibleWidgets = useMemo(() => {
    return widgets.filter((w) => w.visible);
  }, [widgets]);

  // Filter layouts to only include visible widgets
  const filteredLayouts = useMemo(() => {
    const visibleIds = new Set(visibleWidgets.map((w) => w.id));
    const result: { [key: string]: Layout[] } = {};

    Object.entries(layouts).forEach(([breakpoint, layout]) => {
      result[breakpoint] = layout.filter((item) => visibleIds.has(item.i));
    });

    return result;
  }, [layouts, visibleWidgets]);

  // Handle layout changes
  const handleLayoutChange = useCallback(
    (currentLayout: Layout[], allLayouts: { [key: string]: Layout[] }) => {
      Object.entries(allLayouts).forEach(([breakpoint, layout]) => {
        updateLayout(breakpoint, layout);
      });
    },
    [updateLayout]
  );

  // Render widget by type
  const renderWidget = useCallback((widgetId: string) => {
    const widget = widgets.find((w) => w.id === widgetId);
    if (!widget) return null;

    const WidgetComponent = WIDGET_COMPONENTS[widget.type];
    if (!WidgetComponent) return null;

    return (
      <WidgetWrapper
        id={widget.id}
        title={widget.title}
        isEditMode={isEditMode}
        onRemove={isEditMode ? () => toggleWidgetVisibility(widget.id) : undefined}
      >
        <WidgetComponent />
      </WidgetWrapper>
    );
  }, [widgets, isEditMode, toggleWidgetVisibility]);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-text-primary mb-1 tracking-tight">Dashboard</h1>
          <p className="text-text-secondary">
            Real-time sentiment signals for micro-cap securities
          </p>
        </div>
        <div className="flex items-center gap-2">
          {isEditMode && (
            <>
              <button
                onClick={() => setShowSettings(true)}
                className="btn btn-secondary flex items-center gap-2"
              >
                <Settings className="h-4 w-4" />
                Widgets
              </button>
              <button
                onClick={resetToDefault}
                className="btn btn-secondary flex items-center gap-2"
              >
                <RotateCcw className="h-4 w-4" />
                Reset
              </button>
            </>
          )}
          <button
            onClick={() => setEditMode(!isEditMode)}
            className={cn(
              'btn flex items-center gap-2',
              isEditMode ? 'btn-primary' : 'btn-secondary'
            )}
          >
            {isEditMode ? (
              <>
                <Lock className="h-4 w-4" />
                Lock Layout
              </>
            ) : (
              <>
                <Unlock className="h-4 w-4" />
                Customize
              </>
            )}
          </button>
        </div>
      </div>

      {/* Edit mode banner */}
      {isEditMode && (
        <div className="bg-accent-subtle border border-accent/30 rounded-xl p-4 flex items-center justify-between animate-fade-in">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-accent/20 flex items-center justify-center">
              <Settings className="h-4 w-4 text-accent" />
            </div>
            <div>
              <p className="text-sm font-medium text-accent">Customization Mode</p>
              <p className="text-xs text-accent/70">
                Drag widgets to rearrange, resize from corners, or hide from settings
              </p>
            </div>
          </div>
          <button
            onClick={() => setEditMode(false)}
            className="text-xs text-accent hover:text-accent-hover font-medium"
          >
            Done Editing
          </button>
        </div>
      )}

      {/* Grid Layout */}
      <ResponsiveGridLayout
        className="layout"
        layouts={filteredLayouts}
        breakpoints={{ lg: 1200, md: 996, sm: 768 }}
        cols={{ lg: 12, md: 10, sm: 6 }}
        rowHeight={60}
        isDraggable={isEditMode}
        isResizable={isEditMode}
        onLayoutChange={handleLayoutChange}
        draggableHandle=".cursor-move"
        containerPadding={[0, 0]}
        margin={[16, 16]}
      >
        {visibleWidgets.map((widget) => (
          <div key={widget.id} className="overflow-hidden">
            {renderWidget(widget.id)}
          </div>
        ))}
      </ResponsiveGridLayout>

      {/* Widget Settings Panel */}
      <WidgetSettingsPanel
        isOpen={showSettings}
        onClose={() => setShowSettings(false)}
      />
    </div>
  );
}
