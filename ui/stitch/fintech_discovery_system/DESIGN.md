---
name: Fintech Discovery System
colors:
  surface: '#f8f9fa'
  surface-dim: '#d9dadb'
  surface-bright: '#f8f9fa'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#f3f4f5'
  surface-container: '#edeeef'
  surface-container-high: '#e7e8e9'
  surface-container-highest: '#e1e3e4'
  on-surface: '#191c1d'
  on-surface-variant: '#3c4a3c'
  inverse-surface: '#2e3132'
  inverse-on-surface: '#f0f1f2'
  outline: '#6c7b6a'
  outline-variant: '#bbcbb8'
  surface-tint: '#006e2a'
  primary: '#006e2a'
  on-primary: '#ffffff'
  primary-container: '#00c853'
  on-primary-container: '#004c1b'
  inverse-primary: '#3ce36a'
  secondary: '#586062'
  on-secondary: '#ffffff'
  secondary-container: '#dae1e3'
  on-secondary-container: '#5d6466'
  tertiary: '#5b5e66'
  on-tertiary: '#ffffff'
  tertiary-container: '#aaadb6'
  on-tertiary-container: '#3d4148'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#69ff87'
  primary-fixed-dim: '#3ce36a'
  on-primary-fixed: '#002108'
  on-primary-fixed-variant: '#00531e'
  secondary-fixed: '#dde4e6'
  secondary-fixed-dim: '#c1c8ca'
  on-secondary-fixed: '#161d1f'
  on-secondary-fixed-variant: '#41484a'
  tertiary-fixed: '#dfe2eb'
  tertiary-fixed-dim: '#c3c6cf'
  on-tertiary-fixed: '#181c22'
  on-tertiary-fixed-variant: '#43474e'
  background: '#f8f9fa'
  on-background: '#191c1d'
  surface-variant: '#e1e3e4'
typography:
  display:
    fontFamily: manrope
    fontSize: 48px
    fontWeight: '800'
    lineHeight: '1.2'
    letterSpacing: -0.02em
  headline-lg:
    fontFamily: manrope
    fontSize: 32px
    fontWeight: '700'
    lineHeight: 40px
    letterSpacing: -0.01em
  headline-lg-mobile:
    fontFamily: manrope
    fontSize: 24px
    fontWeight: '700'
    lineHeight: 32px
  headline-md:
    fontFamily: manrope
    fontSize: 24px
    fontWeight: '600'
    lineHeight: 32px
  body-lg:
    fontFamily: inter
    fontSize: 18px
    fontWeight: '400'
    lineHeight: 28px
  body-md:
    fontFamily: inter
    fontSize: 16px
    fontWeight: '400'
    lineHeight: 24px
  body-sm:
    fontFamily: inter
    fontSize: 14px
    fontWeight: '400'
    lineHeight: 20px
  label-md:
    fontFamily: hankenGrotesk
    fontSize: 14px
    fontWeight: '600'
    lineHeight: 16px
    letterSpacing: 0.05em
  label-sm:
    fontFamily: hankenGrotesk
    fontSize: 12px
    fontWeight: '500'
    lineHeight: 14px
  data-tabular:
    fontFamily: inter
    fontSize: 16px
    fontWeight: '600'
    lineHeight: 24px
rounded:
  sm: 0.25rem
  DEFAULT: 0.5rem
  md: 0.75rem
  lg: 1rem
  xl: 1.5rem
  full: 9999px
spacing:
  base: 4px
  xs: 4px
  sm: 8px
  md: 16px
  lg: 24px
  xl: 32px
  xxl: 48px
  gutter: 16px
  margin-mobile: 16px
  margin-desktop: 32px
  max-width: 1200px
---

## Brand & Style

The design system is built on the pillars of **Trust, Clarity, and Velocity**. It targets a modern generation of investors who value speed without sacrificing precision. The aesthetic is a hybrid of **Minimalist Modernism** and **Glassmorphism**, specifically tailored to make complex financial data feel approachable and breathable.

The personality is professional yet energetic. It utilizes a "data-first" hierarchy where the interface recedes to allow financial metrics and growth trends to take center stage. Key stylistic signatures include:
- **Precision Grids:** Subtle, non-intrusive grid lines that evoke a sense of mathematical accuracy.
- **Luminous Accents:** Use of high-vibrancy greens to signify growth and action.
- **Dynamic Layering:** In dark mode, depth is communicated through translucent glass surfaces, while light mode relies on crisp, high-contrast structural definition.

## Colors

The palette is designed for high legibility and instant recognition of financial status. 

**Light Theme:** Utilizes `#F8F9FA` for secondary surfaces to create a soft, paper-like feel that reduces eye strain. Primary actions use the iconic "Groww Green" (`#00C853`), providing a punchy contrast against the white base. Charcoal (`#2D3436`) is reserved for primary text to ensure accessibility standards are exceeded.

**Dark Theme:** Shifts to a deep navy/charcoal foundation (`#0D1117`). Surfaces leverage a slightly lighter `#161B22` with varying opacities for glassmorphic effects. The green shifts toward a neon variant (`#00E676`) to maintain vibrance against the dark background. 

**Semantic Usage:** Green is strictly reserved for "positive growth," "success," and "primary CTAs." Red is used sparingly for "negative trends" and "destructive actions" to prevent visual fatigue.

## Typography

This design system employs a three-font strategy to balance character and utility:
1. **Manrope** is used for headlines and displays to provide a refined, modern, and balanced personality.
2. **Inter** is the workhorse for body copy and data, chosen for its exceptional legibility and neutral tone. 
3. **Hanken Grotesk** is utilized for labels and UI metadata, offering a sharp, contemporary edge that feels "fintech-native."

**Technical Note:** All numerical data must use `tnum` (tabular figures) to ensure that stock prices and fund values align vertically in lists and tables, facilitating faster scanning.

## Layout & Spacing

The system follows a strict **8px grid** for vertical rhythm and a **fluid-to-fixed** hybrid grid for horizontal layouts.

- **Desktop:** 12-column grid with a maximum content width of 1200px. Gutters are fixed at 24px.
- **Mobile:** 4-column fluid grid with 16px side margins. 
- **The Data Grid:** A subtle, animated background grid (1px lines, 40px squares) should be visible behind main dashboard views. In light mode, use `#F0F0F0` lines; in dark mode, use `#1C2128` lines.

Spacing should be used to group related financial instruments. For instance, a stock's name and its ticker symbol use `xs` spacing, while the price and its daily change use `sm` spacing.

## Elevation & Depth

Visual hierarchy is established differently across themes to maximize the specific strengths of light and dark UI:

**Light Mode:**
- **Level 0 (Base):** White background with the subtle data-grid.
- **Level 1 (Cards):** Soft-gray `#F8F9FA` surfaces with a 1px border (`#E1E4E8`).
- **Level 2 (Active/Hover):** "Crisp Shadows" — `0px 4px 12px rgba(0, 0, 0, 0.05)`. This creates a floating effect without feeling heavy.

**Dark Mode:**
- **Level 0 (Base):** Deep Navy `#0D1117`.
- **Level 1 (Cards):** Glassmorphic surfaces with a `backdrop-filter: blur(12px)` and a semi-transparent border (`rgba(255, 255, 255, 0.1)`).
- **Level 2 (Active/Active Glow):** Active states utilize a soft green outer glow (`0px 0px 20px rgba(0, 200, 83, 0.2)`) to signify the focused financial asset.

## Shapes

The design system uses a "Standard Rounded" approach to feel friendly yet precise.

- **Primary Containers (Cards):** `12px` (rounded-lg) for main dashboard modules.
- **Secondary UI (Inputs, Buttons):** `8px` (default) for standard interactive elements.
- **Small Elements (Chips, Tags):** `pill` (rounded-full) to distinguish them from actionable buttons.

Avoid sharp corners to maintain a "consumer-friendly" investment vibe, but do not exceed 16px to prevent the interface from appearing too casual or toy-like.

## Components

### Buttons
- **Primary:** Solid Groww Green with white text. On hover, a subtle scale-up (1.02x) and increased shadow.
- **Secondary:** Transparent background with a 1.5px border matching the primary text color.
- **Ghost:** No border or background; text-only, used for "See All" or "View More" actions.

### Cards & Discovery
- **Stock Card:** Features a sparkline (simplified chart). In dark mode, the sparkline should have a slight glow effect.
- **Glass Card:** Used specifically in dark mode for overlays and modal drawers, leveraging the 12px blur.

### Form Inputs
- **Search:** The "Fast Discovery" bar should be prominent, with a persistent search icon.
- **Inputs:** Use floating labels. Focus state is indicated by a 2px Groww Green border and a soft green outer glow.

### Data Visualizations
- **Charts:** Line charts should use a 2px stroke width. Areas under the curve should have a vertical gradient fading from Groww Green to transparent.
- **Chips:** Used for sector categorization (e.g., "Tech," "Energy"). Use low-saturation background tints of the primary colors to keep them subordinate.

### Feedback
- **Success State:** A subtle green pulse animation around the transaction success icon.
- **Loading:** A custom animated grid-pulse that matches the background grid system.