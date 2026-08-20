import type { Config } from 'tailwindcss';

export default {
  content: ['./src/**/*.{js,ts,jsx,tsx,mdx}'],
  theme: {
    extend: {
      colors: {
        brand: {
          blue: '#3b82f6',
          purple: '#7c3aed',
          navy: '#0f172a',
        },
      },
    },
  },
  plugins: [],
} satisfies Config;
