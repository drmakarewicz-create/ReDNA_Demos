import type { Config } from 'tailwindcss';

const config: Config = {
  content: [
    './src/pages/**/*.{js,ts,jsx,tsx,mdx}',
    './src/components/**/*.{js,ts,jsx,tsx,mdx}',
    './src/app/**/*.{js,ts,jsx,tsx,mdx}'
  ],
  theme: {
    extend: {
      colors: {
        hc: {
          background: '#0b1120',
          surface: '#111827',
          accent: '#38bdf8'
        }
      }
    }
  },
  plugins: []
};

export default config;
