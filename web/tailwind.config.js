/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './src/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        atlas: {
          ink: '#16222f',
          mist: '#f6f6f2',
          sand: '#fefbf4',
          reef: '#0f766e',
          reefDeep: '#0b5f5a',
          amber: '#e49d37',
          fog: '#5f6d77',
        },
        brand: {
          50: '#eef8ff',
          100: '#d9eeff',
          200: '#bce3ff',
          300: '#8ed2ff',
          400: '#59b8ff',
          500: '#3399ff',
          600: '#1a7af5',
          700: '#1363e1',
          800: '#1650b6',
          900: '#18448f',
          950: '#142b57',
        },
      },
    },
  },
  plugins: [],
};
