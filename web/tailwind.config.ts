import type { Config } from 'tailwindcss';

// Tokens follow docs/design/README.md §2 (names) with the values of the current "TROP · Sprawdź" boards
// (light zgrai theme, docs/design/canvas/assets/rp-zg.css + the board inline styles). The CSS variables live in
// app/globals.css, so a dark "phosphor" theme (rp.css) can be switched with [data-theme="phosphor"].
const v = (name: string) => `rgb(var(--${name}) / <alpha-value>)`;

const config: Config = {
  content: ['./app/**/*.{ts,tsx}', './components/**/*.{ts,tsx}', './lib/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        // flat keys → bg-bg1, border-line1, text-tx2 (design §2 bg.{0..4} / line.{1..3} / tx.{1..3})
        bg0: v('bg0'), bg1: v('bg1'), bg2: v('bg2'), bg3: v('bg3'), bg4: v('bg4'),
        line1: v('line1'), line2: v('line2'), line3: v('line3'),
        tx1: v('tx1'), tx2: v('tx2'), tx3: v('tx3'), tx4: v('tx4'),
        ink: v('ink'),
        ev: {
          tracking: v('ev-tracking'), kit: v('ev-kit'), infra: v('ev-infra'), content: v('ev-content'),
          persons: v('ev-persons'), visual: v('ev-visual'), ad: v('ev-ad'), media: v('ev-media'),
        },
        state: {
          g: v('st-g'), gdim: v('st-gdim'), amber: v('st-amber'), adim: v('st-adim'), red: v('st-red'), rdim: v('st-rdim'),
          cyan: v('st-cyan'), cdim: v('st-cdim'), violet: v('st-violet'), vdim: v('st-vdim'),
        },
        bot: {
          zwiadowca: '#2563EB', tropiciel: '#F97316', czytelnik: '#14B8A6', notariusz: '#8B5CF6', archiwista: '#EC4899', sedzia: '#0A0A0A',
        },
      },
      fontFamily: {
        head: ['var(--font-geist-sans)', 'Geist', 'Inter', 'system-ui', 'sans-serif'],
        sans: ['var(--font-geist-sans)', 'Geist', 'Inter', 'system-ui', 'sans-serif'],
        mono: ['var(--font-geist-mono)', 'Geist Mono', 'ui-monospace', 'monospace'],
      },
      borderRadius: { card: '22px', panel: '28px', field: '14px' },
      boxShadow: {
        card: '0 1px 2px rgba(0,0,0,.04), 0 16px 40px rgba(0,0,0,.07)',
        soft: '0 1px 2px rgba(0,0,0,.04), 0 8px 24px rgba(0,0,0,.05)',
        dark: '0 16px 40px rgba(0,0,0,.18)',
      },
      keyframes: {
        pop: { from: { opacity: '0', transform: 'translateY(8px)' }, to: { opacity: '1', transform: 'none' } },
        pulsedot: { '0%': { boxShadow: '0 0 0 0 rgba(34,197,94,.45)' }, '100%': { boxShadow: '0 0 0 8px rgba(34,197,94,0)' } },
      },
      animation: { pop: 'pop .4s ease', pulsedot: 'pulsedot 1.6s ease-out infinite' },
    },
  },
  plugins: [],
};
export default config;
