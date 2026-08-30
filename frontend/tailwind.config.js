/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        brand: {
          50: '#eff6ff',
          100: '#dbeafe',
          200: '#bfdbfe',
          300: '#93c5fd',
          400: '#60a5fa',
          500: '#2563eb',
          600: '#1d4ed8',
          700: '#1e40af',
          800: '#1e3a5f',
          900: '#0f172a',
        }
      },
      fontSize: {
        'kiosk-sm': ['1.25rem', { lineHeight: '1.75rem' }],
        'kiosk-base': ['1.5rem', { lineHeight: '2rem' }],
        'kiosk-lg': ['2rem', { lineHeight: '2.5rem' }],
        'kiosk-xl': ['2.5rem', { lineHeight: '3rem' }],
        'kiosk-2xl': ['3rem', { lineHeight: '3.5rem' }],
      }
    },
  },
  plugins: [],
}
