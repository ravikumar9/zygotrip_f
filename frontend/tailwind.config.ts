import type { Config } from 'tailwindcss';

const config: Config = {
  content: [
    './app/**/*.{js,ts,jsx,tsx,mdx}',
    './components/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      colors: {
        // ── Primary: Goibibo vibrant red ───────────────────────────
        primary: {
          50:  '#fff0f0',
          100: '#ffd5d6',
          200: '#ffabac',
          300: '#ff8082',
          400: '#ff4a4f',
          500: '#EB2026',   // Goibibo core red
          600: '#c71a1f',   // hover/dark
          700: '#a61318',
          800: '#7c0d12',
          900: '#5c090d',
        },
        // ── Brand dark (navbar / hero background) ─────────────────
        brand: {
          dark: '#1a1a2e',
          mid:  '#16213e',
          blue: '#0f3460',
        },
        // ── Accent: coral-orange for secondary CTAs ────────────────
        accent: {
          50:  '#fff4ee',
          100: '#ffe4d0',
          200: '#ffc9a0',
          300: '#ffaa6f',
          400: '#ff8c45',
          500: '#FF6B35',
          600: '#e55a24',
          700: '#c24a18',
          800: '#9c3c12',
          900: '#7a2e0b',
        },
        // ── Success ───────────────────────────────────────────────
        success: {
          50:  '#f0fdf4',
          100: '#dcfce7',
          200: '#bbf7d0',
          300: '#86efac',
          400: '#4ade80',
          500: '#00a652',
          600: '#16a34a',
          700: '#15803d',
          800: '#166534',
          900: '#14532d',
        },
        // ── Warning ───────────────────────────────────────────────
        warning: {
          50:  '#fffbeb',
          100: '#fef3c7',
          200: '#fde68a',
          300: '#fcd34d',
          400: '#fbbf24',
          500: '#f5a623',
          600: '#d97706',
          700: '#b45309',
          800: '#92400e',
          900: '#78350f',
        },
        // ── Error ─────────────────────────────────────────────────
        error: {
          50:  '#fef2f2',
          100: '#fee2e2',
          200: '#fecaca',
          300: '#fca5a5',
          400: '#f87171',
          500: '#ef4444',
          600: '#dc2626',
          700: '#b91c1c',
          800: '#991b1b',
          900: '#7f1d1d',
        },
        // ── Neutral ───────────────────────────────────────────────
        neutral: {
          50:  '#f8f9fa',
          100: '#f1f5f9',
          200: '#e5e7eb',
          300: '#cbd5e1',
          400: '#94a3b8',
          500: '#6b7280',
          600: '#475569',
          700: '#334155',
          800: '#1e293b',
          900: '#1a1a2e',
        },
      },

      fontFamily: {
        sans:    ['Nunito', 'Inter', 'system-ui', '-apple-system', 'sans-serif'],
        heading: ['Poppins', 'Plus Jakarta Sans', 'Nunito', 'sans-serif'],
      },

      fontSize: {
        '2xs': ['0.625rem', { lineHeight: '1rem' }],
      },

      boxShadow: {
        'card':        '0 1px 3px 0 rgba(0,0,0,0.08), 0 1px 2px -1px rgba(0,0,0,0.08)',
        'card-hover':  '0 8px 24px rgba(0,0,0,0.12)',
        'modal':       '0 20px 40px rgba(0,0,0,0.18)',
        'nav':         '0 2px 20px rgba(0,0,0,0.15)',
        'booking':     '0 8px 32px rgba(0,0,0,0.12)',
        'search':      '0 -8px 40px rgba(0,0,0,0.3)',
        'field':       '0 2px 6px rgba(0,0,0,0.06)',
      },

      borderRadius: {
        'xl':  '0.75rem',
        '2xl': '1rem',
        '3xl': '1.5rem',
        '4xl': '2rem',
      },

      spacing: {
        '4.5': '1.125rem',
        '5.5': '1.375rem',
        '18':  '4.5rem',
        '22':  '5.5rem',
      },

      animation: {
        'fade-up':    'fadeUp 0.4s ease forwards',
        'fade-in':    'fadeIn 0.3s ease forwards',
        'slide-down': 'slideDown 0.2s ease forwards',
        'spin-slow':  'spin 2s linear infinite',
        'pulse-soft': 'pulseSoft 2s ease-in-out infinite',
        'slide-up':   'slideUp 0.3s ease forwards',
        'bounce-in':  'bounceIn 0.5s ease forwards',
        'shimmer':    'shimmer 1.5s ease-in-out infinite',
        'count-up':   'countUp 0.6s ease-out forwards',
      },

      keyframes: {
        fadeUp: {
          from: { opacity: '0', transform: 'translateY(16px)' },
          to:   { opacity: '1', transform: 'translateY(0)' },
        },
        fadeIn: {
          from: { opacity: '0' },
          to:   { opacity: '1' },
        },
        slideDown: {
          from: { opacity: '0', transform: 'translateY(-8px)' },
          to:   { opacity: '1', transform: 'translateY(0)' },
        },
        slideUp: {
          from: { opacity: '0', transform: 'translateY(12px)' },
          to:   { opacity: '1', transform: 'translateY(0)' },
        },
        pulseSoft: {
          '0%, 100%': { opacity: '1' },
          '50%':      { opacity: '0.7' },
        },
        bounceIn: {
          '0%':   { opacity: '0', transform: 'scale(0.9)' },
          '60%':  { opacity: '1', transform: 'scale(1.02)' },
          '100%': { transform: 'scale(1)' },
        },
        shimmer: {
          '0%':   { backgroundPosition: '-200% 0' },
          '100%': { backgroundPosition: '200% 0' },
        },
        countUp: {
          from: { opacity: '0', transform: 'translateY(8px)' },
          to:   { opacity: '1', transform: 'translateY(0)' },
        },
      },

      backgroundImage: {
        'hero-gradient':   'linear-gradient(135deg, #1a1a2e 0%, #16213e 40%, #0f3460 100%)',
        'cta-gradient':    'linear-gradient(135deg, #EB2026 0%, #FF6B35 100%)',
        'wallet-gradient': 'linear-gradient(135deg, #EB2026 0%, #c71a1f 100%)',
      },
    },
  },
  plugins: [],
};

export default config;
