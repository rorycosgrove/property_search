/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './src/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
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
