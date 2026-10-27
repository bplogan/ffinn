import type { Config } from 'tailwindcss'

const config: Config = {
  content: [
    './src/pages/**/*.{js,ts,jsx,tsx,mdx}',
    './src/components/**/*.{js,ts,jsx,tsx,mdx}',
    './src/app/**/*.{js,ts,jsx,tsx,mdx}',
    './src/lib/**/*.{js,ts,jsx,tsx}',
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        // Public-site tokens: RGB triplets set on .site in globals.css, so they flip with dark mode
        canvas:  'rgb(var(--canvas) / <alpha-value>)',
        surface: 'rgb(var(--surface) / <alpha-value>)',
        ink: {
          DEFAULT: 'rgb(var(--ink) / <alpha-value>)',
          soft:    'rgb(var(--ink-soft) / <alpha-value>)',
          mute:    'rgb(var(--ink-mute) / <alpha-value>)',
        },
        accent: {
          DEFAULT: 'rgb(var(--accent) / <alpha-value>)',
          soft:    'rgb(var(--accent-soft) / <alpha-value>)',
        },
        signal:  'rgb(var(--signal) / <alpha-value>)',
        caution: 'rgb(var(--caution) / <alpha-value>)',
        // Warm neutrals matching the paper/ink tokens, so every `gray-*` utility in the
        // portal follows the same palette (50 = canvas, 900 = dark surface, 950 = dark canvas).
        gray: {
          50:  '#f7f6f2',
          100: '#efeee9',
          200: '#e3e2dc',
          300: '#cfcec7',
          400: '#9a9ba3',
          500: '#686c77',
          600: '#4c4f58',
          700: '#35373e',
          800: '#202228',
          900: '#131519',
          950: '#0a0b0d',
        },
        brand: {
          25:  '#f2f7ff',
          50:  '#ecf3ff',
          100: '#dde9ff',
          200: '#c2d6ff',
          300: '#9cb9ff',
          400: '#7592ff',
          500: '#465fff',
          600: '#3641f5',
          700: '#2a31d8',
          800: '#252dae',
          900: '#262e89',
          950: '#171950',
        },
        error: {
          50:  '#fef2f2',
          100: '#fee2e2',
          200: '#fecaca',
          300: '#fca5a5',
          400: '#f87171',
          500: '#ef4444',
          600: '#dc2626',
          700: '#b91c1c',
          900: '#7f1d1d',
        },
        success: {
          50:  '#f0fdf4',
          100: '#dcfce7',
          200: '#bbf7d0',
          300: '#86efac',
          400: '#4ade80',
          500: '#22c55e',
          600: '#16a34a',
          700: '#15803d',
          900: '#14532d',
        },
        warning: {
          50:  '#fffbeb',
          100: '#fef3c7',
          200: '#fde68a',
          300: '#fcd34d',
          400: '#fbbf24',
          500: '#f59e0b',
          600: '#d97706',
          700: '#b45309',
          900: '#78350f',
        },
      },
      fontFamily: {
        sans: ['var(--font-inter)', 'system-ui', 'sans-serif'],
        display: ['var(--font-geist)', 'var(--font-inter)', 'system-ui', 'sans-serif'],
        serif: ['var(--font-serif)', 'Georgia', 'serif'],
        mono: ['var(--font-geist-mono)', 'ui-monospace', 'SFMono-Regular', 'Menlo', 'monospace'],
      },
      boxShadow: {
        sm:  '0px 1px 2px 0px rgba(10, 13, 18, 0.05)',
        md:  '0px 2px 4px -2px rgba(10, 13, 18, 0.06), 0px 4px 8px -2px rgba(10, 13, 18, 0.10)',
        lg:  '0px 4px 6px -2px rgba(10, 13, 18, 0.03), 0px 12px 16px -4px rgba(10, 13, 18, 0.08)',
        xl:  '0px 8px 8px -4px rgba(10, 13, 18, 0.03), 0px 20px 24px -4px rgba(10, 13, 18, 0.08)',
      },
    },
  },
  plugins: [],
}

export default config
