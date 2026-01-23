import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { Layout } from 'react-grid-layout';

// Widget types available on the dashboard
export type WidgetType =
  | 'stats'
  | 'eventFeed'
  | 'highAlpha'
  | 'watchlist'
  | 'sentimentChart';

export interface WidgetConfig {
  id: string;
  type: WidgetType;
  title: string;
  visible: boolean;
}

// Default layout configuration for lg breakpoint
export const DEFAULT_LAYOUTS: { [key: string]: Layout[] } = {
  lg: [
    { i: 'stats', x: 0, y: 0, w: 12, h: 2, minW: 4, minH: 2, static: false },
    { i: 'eventFeed', x: 0, y: 2, w: 8, h: 8, minW: 4, minH: 4, static: false },
    { i: 'highAlpha', x: 8, y: 2, w: 4, h: 8, minW: 3, minH: 4, static: false },
    { i: 'watchlist', x: 0, y: 10, w: 6, h: 5, minW: 3, minH: 3, static: false },
    { i: 'sentimentChart', x: 6, y: 10, w: 6, h: 5, minW: 3, minH: 3, static: false },
  ],
  md: [
    { i: 'stats', x: 0, y: 0, w: 10, h: 2, minW: 4, minH: 2, static: false },
    { i: 'eventFeed', x: 0, y: 2, w: 6, h: 8, minW: 4, minH: 4, static: false },
    { i: 'highAlpha', x: 6, y: 2, w: 4, h: 8, minW: 3, minH: 4, static: false },
    { i: 'watchlist', x: 0, y: 10, w: 5, h: 5, minW: 3, minH: 3, static: false },
    { i: 'sentimentChart', x: 5, y: 10, w: 5, h: 5, minW: 3, minH: 3, static: false },
  ],
  sm: [
    { i: 'stats', x: 0, y: 0, w: 6, h: 2, minW: 2, minH: 2, static: false },
    { i: 'eventFeed', x: 0, y: 2, w: 6, h: 8, minW: 3, minH: 4, static: false },
    { i: 'highAlpha', x: 0, y: 10, w: 6, h: 6, minW: 3, minH: 4, static: false },
    { i: 'watchlist', x: 0, y: 16, w: 6, h: 5, minW: 3, minH: 3, static: false },
    { i: 'sentimentChart', x: 0, y: 21, w: 6, h: 5, minW: 3, minH: 3, static: false },
  ],
};

// Default widget configurations
export const DEFAULT_WIDGETS: WidgetConfig[] = [
  { id: 'stats', type: 'stats', title: 'Statistics', visible: true },
  { id: 'eventFeed', type: 'eventFeed', title: 'Latest Events', visible: true },
  { id: 'highAlpha', type: 'highAlpha', title: 'High Alpha Signals', visible: true },
  { id: 'watchlist', type: 'watchlist', title: 'Watchlist', visible: true },
  { id: 'sentimentChart', type: 'sentimentChart', title: 'Sentiment Overview', visible: true },
];

interface LayoutState {
  // Layout configuration per breakpoint
  layouts: { [key: string]: Layout[] };

  // Widget configurations
  widgets: WidgetConfig[];

  // Edit mode
  isEditMode: boolean;

  // Actions
  setLayouts: (layouts: { [key: string]: Layout[] }) => void;
  updateLayout: (breakpoint: string, layout: Layout[]) => void;
  setWidgets: (widgets: WidgetConfig[]) => void;
  toggleWidgetVisibility: (widgetId: string) => void;
  setEditMode: (isEditMode: boolean) => void;
  resetToDefault: () => void;
}

export const useLayoutStore = create<LayoutState>()(
  persist(
    (set) => ({
      // Initial state
      layouts: DEFAULT_LAYOUTS,
      widgets: DEFAULT_WIDGETS,
      isEditMode: false,

      // Actions
      setLayouts: (layouts) => set({ layouts }),

      updateLayout: (breakpoint, layout) => {
        set((state) => ({
          layouts: {
            ...state.layouts,
            [breakpoint]: layout,
          },
        }));
      },

      setWidgets: (widgets) => set({ widgets }),

      toggleWidgetVisibility: (widgetId) => {
        set((state) => ({
          widgets: state.widgets.map((w) =>
            w.id === widgetId ? { ...w, visible: !w.visible } : w
          ),
        }));
      },

      setEditMode: (isEditMode) => set({ isEditMode }),

      resetToDefault: () =>
        set({
          layouts: DEFAULT_LAYOUTS,
          widgets: DEFAULT_WIDGETS,
        }),
    }),
    {
      name: 'dashboard-layout',
    }
  )
);

// Selector hooks
export const useLayouts = () => useLayoutStore((state) => state.layouts);
export const useWidgets = () => useLayoutStore((state) => state.widgets);
export const useIsEditMode = () => useLayoutStore((state) => state.isEditMode);
