import type { Config } from "tailwindcss"
import tailwindAnimate from "tailwindcss-animate"

const config = {
  darkMode: ["class"],
  important: true,
  content: [

    
    "./pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
	],
  prefix: "",
  theme: {
  	container: {
  		center: true,
  		padding: {
  			DEFAULT: '1rem',
  			sm: '1.5rem',
  			lg: '2rem',
  		},
  		screens: {
  			'2xl': '1400px'
  		}
  	},
  	extend: {
  		fontFamily: {
  			sans: ['var(--font-dm-sans)', 'system-ui', 'sans-serif'],
  			// Base visual nova (styles/pe.css). Algarismos sempre em Montserrat.
  			'pe-texto': ['"PE Numeros"', '"PE Atkinson"', '"Atkinson Hyperlegible"', 'system-ui', 'sans-serif'],
  			'pe-titulo': ['"PE Montserrat"', 'system-ui', 'sans-serif'],
  		},
  		fontSize: {
  			'pe-titulo-xl': ['56px', { lineHeight: '60px', letterSpacing: '-0.02em', fontWeight: '700' }],
  			'pe-titulo-l': ['40px', { lineHeight: '46px', letterSpacing: '-0.015em', fontWeight: '700' }],
  			'pe-titulo-m': ['28px', { lineHeight: '34px', letterSpacing: '-0.01em', fontWeight: '700' }],
  			'pe-titulo-s': ['20px', { lineHeight: '26px', fontWeight: '600' }],
  			'pe-voz': ['24px', { lineHeight: '34px', fontWeight: '300' }],
  			'pe-corpo-l': ['18px', { lineHeight: '28px' }],
  			'pe-corpo': ['16px', { lineHeight: '26px' }],
  			'pe-rotulo': ['15px', { lineHeight: '20px', fontWeight: '600' }],
  			'pe-legenda': ['14px', { lineHeight: '20px' }],
  		},
  		boxShadow: {
  			'pe-1': '0 1px 2px rgba(0, 0, 102, 0.08)',
  			'pe-2': '0 8px 24px rgba(0, 0, 102, 0.12)',
  		},
  		colors: {
  			pe: {
  				'azul-marca': '#000066',
  				'azul-vivo': '#2f46e8',
  				realce: '#ffc72c',
  				'realce-suave': '#fff1c2',
  				fundo: '#ffffff',
  				'fundo-suave': '#f2f3fa',
  				'fundo-forte': '#e3e5f4',
  				tinta: '#14143f',
  				'tinta-suave': '#54577a',
  				'sobre-marca': '#ffffff',
  				linha: '#cfd2e6',
  				'linha-forte': '#7479a3',
  				certo: '#007268',
  				'certo-suave': '#d9f2ee',
  				errado: '#c2330f',
  				'errado-suave': '#fde4dc',
  				vida: '#e5385a',
  			},
  			background: 'hsl(var(--background))',
  			foreground: 'hsl(var(--foreground))',
  			'primary-black': '#1A232E',
  			'secondary-white': '#c7c7c7',
  			card: {
  				DEFAULT: 'hsl(var(--card))',
  				foreground: 'hsl(var(--card-foreground))'
  			},
  			popover: {
  				DEFAULT: 'hsl(var(--popover))',
  				foreground: 'hsl(var(--popover-foreground))'
  			},
  			muted: {
  				DEFAULT: 'hsl(var(--muted))',
  				foreground: 'hsl(var(--muted-foreground))'
  			},
  			accent: {
  				DEFAULT: 'hsl(var(--accent))',
  				foreground: 'hsl(var(--accent-foreground))'
  			},
  			destructive: {
  				DEFAULT: 'hsl(var(--destructive))',
  				foreground: 'hsl(var(--destructive-foreground))'
  			},
  			blue: {
  				'1': '#0E78F9'
  			},
  			sky: {
  				'1': '#C9DDFF',
  				'2': '#ECF0FF',
  				'3': '#F5FCFF'
  			},
  			orange: {
  				'1': '#FF742E'
  			},
  			purple: {
  				'1': '#830EF9'
  			},
  			yellow: {
  				'1': '#F9A90E'
  			},
  			border: 'hsl(var(--border))',
  			input: 'hsl(var(--input))',
  			ring: 'hsl(var(--ring))',
  			chart: {
  				'1': 'hsl(var(--chart-1))',
  				'2': 'hsl(var(--chart-2))',
  				'3': 'hsl(var(--chart-3))',
  				'4': 'hsl(var(--chart-4))',
  				'5': 'hsl(var(--chart-5))'
  			},
  			sidebar: {
  				DEFAULT: 'hsl(var(--sidebar-background))',
  				foreground: 'hsl(var(--sidebar-foreground))',
  				primary: 'hsl(var(--sidebar-primary))',
  				'primary-foreground': 'hsl(var(--sidebar-primary-foreground))',
  				accent: 'hsl(var(--sidebar-accent))',
  				'accent-foreground': 'hsl(var(--sidebar-accent-foreground))',
  				border: 'hsl(var(--sidebar-border))',
  				ring: 'hsl(var(--sidebar-ring))'
  			},
  			customgreys: {
  				primarybg: '#1B1C22',
  				secondarybg: '#25262F',
  				darkGrey: '#17181D',
  				darkerGrey: '#3d3d3d',
  				dirtyGrey: '#6e6e6e'
  			},
  			primary: {
  				'50': '#fdfdff',
  				'100': '#f7f7ff',
  				'200': '#ececff',
  				'300': '#ddddfe',
  				'400': '#cacafe',
  				'500': '#b3b3fd',
  				'600': '#9898fd',
  				'700': '#7878fc',
  				'750': '#5a5be6',
  				'800': '#0404be',
  				'900': '#020255',
  				'950': '#010132',
  				DEFAULT: 'hsl(var(--primary))',
  				foreground: 'hsl(var(--primary-foreground))'
  			},
  			secondary: {
  				'50': '#fcfefe',
  				'100': '#f3fbfa',
  				'200': '#e5f7f4',
  				'300': '#d0f1ec',
  				'400': '#b6e9e1',
  				'500': '#96dfd4',
  				'600': '#70d3c4',
  				'700': '#44c5b2',
  				'800': '#227064',
  				'900': '#123933',
  				'950': '#0c2723',
  				DEFAULT: 'hsl(var(--secondary))',
  				foreground: 'hsl(var(--secondary-foreground))'
  			}
  		},
  		borderRadius: {
  			'pe-sm': '6px',
  			'pe-md': '12px',
  			// O canto do balão do logótipo: três cantos redondos e um recto (em baixo à esquerda).
  			'pe-fala': '28px 28px 28px 0',
  			// O aluno fala do outro lado: canto recto em baixo à direita.
  			'pe-fala-aluno': '28px 28px 0 28px',
  			'pe-fala-m': '20px 20px 20px 0',
  			'pe-fala-s': '12px 12px 12px 0',
  			lg: 'var(--radius)',
  			md: 'calc(var(--radius) - 2px)',
  			sm: 'calc(var(--radius) - 4px)'
  		},
  		keyframes: {
  			'accordion-down': {
  				from: {
  					height: '0'
  				},
  				to: {
  					height: 'var(--radix-accordion-content-height)'
  				}
  			},
  			'accordion-up': {
  				from: {
  					height: 'var(--radix-accordion-content-height)'
  				},
  				to: {
  					height: '0'
  				}
  			},
  
  		},
  		animation: {
  			'accordion-down': 'accordion-down 0.2s ease-out',
  			'accordion-up': 'accordion-up 0.2s ease-out',
  		
  		},
  		transitionTimingFunction: {
  			'out-flex': 'cubic-bezier(0.05, 0.6, 0.4, 0.9)'
  		},
  	
  	}
  },
  plugins: [tailwindAnimate],
} satisfies Config

export default config
