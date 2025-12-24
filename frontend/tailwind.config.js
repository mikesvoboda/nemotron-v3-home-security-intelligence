/** @type {import('tailwindcss').Config} */
export default {
  content: [
    './index.html',
    './src/**/*.{js,ts,jsx,tsx}',
    './node_modules/@tremor/**/*.{js,ts,jsx,tsx}',
  ],
  theme: {
    extend: {
      colors: {
        // NVIDIA Theme - Dark Backgrounds
        background: '#0E0E0E',
        panel: '#1A1A1A',
        card: '#1E1E1E',

        // NVIDIA Green - Primary Brand Color
        primary: {
          DEFAULT: '#76B900',
          50: '#E8F5D9',
          100: '#D4EBB3',
          200: '#B8DD80',
          300: '#9CCF4D',
          400: '#89C226',
          500: '#76B900',
          600: '#619900',
          700: '#4C7900',
          800: '#375900',
          900: '#223A00',
        },

        // Risk Level Colors
        risk: {
          low: '#76B900',
          medium: '#FFB800',
          high: '#E74856',
        },

        // Text Colors
        text: {
          primary: '#FFFFFF',
          secondary: '#A0A0A0',
          muted: '#707070',
        },

        // Additional Grays for UI Elements
        gray: {
          950: '#0E0E0E',
          900: '#1A1A1A',
          850: '#1E1E1E',
          800: '#2A2A2A',
          700: '#3A3A3A',
          600: '#4A4A4A',
          500: '#707070',
          400: '#A0A0A0',
          300: '#C0C0C0',
          200: '#D0D0D0',
          100: '#E0E0E0',
          50: '#F0F0F0',
        },
      },

      // Custom Spacing for Dashboard Layout
      spacing: {
        18: '4.5rem',
        88: '22rem',
        128: '32rem',
      },

      // Font Families
      fontFamily: {
        sans: [
          'Inter',
          'system-ui',
          '-apple-system',
          'BlinkMacSystemFont',
          'Segoe UI',
          'Roboto',
          'sans-serif',
        ],
        mono: ['JetBrains Mono', 'Fira Code', 'Consolas', 'Monaco', 'Courier New', 'monospace'],
      },

      // Custom Border Radius
      borderRadius: {
        xl: '1rem',
        '2xl': '1.5rem',
      },

      // Box Shadows for Dark Theme
      boxShadow: {
        'dark-sm': '0 1px 2px 0 rgba(0, 0, 0, 0.5)',
        dark: '0 1px 3px 0 rgba(0, 0, 0, 0.6), 0 1px 2px -1px rgba(0, 0, 0, 0.5)',
        'dark-md': '0 4px 6px -1px rgba(0, 0, 0, 0.6), 0 2px 4px -2px rgba(0, 0, 0, 0.5)',
        'dark-lg': '0 10px 15px -3px rgba(0, 0, 0, 0.6), 0 4px 6px -4px rgba(0, 0, 0, 0.5)',
        'dark-xl': '0 20px 25px -5px rgba(0, 0, 0, 0.6), 0 8px 10px -6px rgba(0, 0, 0, 0.5)',
        'nvidia-glow': '0 0 20px rgba(118, 185, 0, 0.3)',
      },

      // Animation Durations
      transitionDuration: {
        250: '250ms',
        400: '400ms',
      },

      // Grid Template Columns for Dashboard
      gridTemplateColumns: {
        dashboard: 'repeat(auto-fit, minmax(300px, 1fr))',
        'camera-grid': 'repeat(auto-fit, minmax(280px, 1fr))',
      },

      // Custom Animation Keyframes
      keyframes: {
        'pulse-glow': {
          '0%, 100%': { boxShadow: '0 0 10px rgba(118, 185, 0, 0.2)' },
          '50%': { boxShadow: '0 0 20px rgba(118, 185, 0, 0.4)' },
        },
        'slide-in': {
          '0%': { transform: 'translateX(100%)', opacity: '0' },
          '100%': { transform: 'translateX(0)', opacity: '1' },
        },
        'fade-in': {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
      },

      animation: {
        'pulse-glow': 'pulse-glow 2s ease-in-out infinite',
        'slide-in': 'slide-in 0.3s ease-out',
        'fade-in': 'fade-in 0.2s ease-in',
      },
    },
  },
  plugins: [],
};
