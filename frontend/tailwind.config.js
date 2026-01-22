/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './src/pages/**/*.{js,ts,jsx,tsx,mdx}',
    './src/components/**/*.{js,ts,jsx,tsx,mdx}',
    './src/app/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      colors: {
        paper: 'hsl(var(--paper))',
        'paper-warm': 'hsl(var(--paper-warm))',
        ink: 'hsl(var(--ink))',
        'ink-muted': 'hsl(var(--ink-muted))',
        'ink-faint': 'hsl(var(--ink-faint))',
        accent: {
          DEFAULT: 'hsl(var(--accent))',
          light: 'hsl(var(--accent-light))',
          dark: 'hsl(var(--accent-dark))',
        },
        bullish: {
          DEFAULT: 'hsl(var(--bullish))',
          bg: 'hsl(var(--bullish-bg))',
        },
        bearish: {
          DEFAULT: 'hsl(var(--bearish))',
          bg: 'hsl(var(--bearish-bg))',
        },
        border: 'hsl(var(--border))',
        'border-strong': 'hsl(var(--border-strong))',
      },
      fontFamily: {
        sans: ['DM Sans', 'system-ui', 'sans-serif'],
        serif: ['Newsreader', 'Georgia', 'serif'],
        mono: ['JetBrains Mono', 'monospace'],
      },
      fontSize: {
        '2xs': ['0.6875rem', { lineHeight: '1rem' }],
      },
      boxShadow: {
        'card': '0 1px 2px hsl(var(--shadow-color) / 0.03), 0 4px 12px hsl(var(--shadow-color) / 0.04)',
        'card-hover': '0 2px 4px hsl(var(--shadow-color) / 0.04), 0 8px 24px hsl(var(--shadow-color) / 0.08)',
        'elevated': '0 2px 4px hsl(var(--shadow-color) / 0.04), 0 8px 24px hsl(var(--shadow-color) / 0.06)',
      },
      animation: {
        'fade-up': 'fade-up 0.4s ease-out forwards',
        'live-pulse': 'live-pulse 2s ease-in-out infinite',
      },
      keyframes: {
        'fade-up': {
          from: { opacity: '0', transform: 'translateY(12px)' },
          to: { opacity: '1', transform: 'translateY(0)' },
        },
        'live-pulse': {
          '0%, 100%': { opacity: '1', transform: 'scale(1)' },
          '50%': { opacity: '0.6', transform: 'scale(1.1)' },
        },
      },
    },
  },
  plugins: [],
};
