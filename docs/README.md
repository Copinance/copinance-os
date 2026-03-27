# Documentation

This project uses [Nextra](https://nextra.site/) for documentation, built on Next.js.

## Quick Start

1. **Navigate to the docs directory:**
   ```bash
   cd docs
   ```

2. **Install dependencies:**
   ```bash
   npm install
   ```

3. **Run development server:**
   ```bash
   npm run dev
   ```
   Open [http://localhost:3000](http://localhost:3000) in your browser.

## Building for Production

```bash
cd docs
npm run build
```

The static site will be generated in the `docs/out/` directory.

## Project Structure

Documentation lives under `docs/pages/` in MDX. Sidebar order and titles are set in `_meta.tsx` files in each section.

```
docs/
├── pages/
│   ├── index.mdx              # Introduction
│   ├── _meta.tsx              # Root nav: Getting Started, User Guide, Tools, Analytics, Developer, API Reference
│   ├── getting-started/      # Installation, Quick Start, Configuration, Using as a Library
│   ├── user-guide/           # CLI Reference, Analysis Modes
│   ├── tools/                 # Overview (analysis + data-provider tools), analysis/market-regime, analysis/macro-indicators, data-providers
│   ├── analytics/             # BSM & Greeks, options chain metadata (assumptions, provider inputs)
│   ├── developer-guide/      # Architecture, Extending, Testing
│   └── api-reference/        # Overview, Data Provider Interfaces
├── next.config.mjs
├── theme.config.tsx
├── package.json
├── tsconfig.json
└── README.md
```

## Configuration

- `next.config.mjs` - Next.js and Nextra configuration
- `theme.config.tsx` - Theme customization
- `package.json` - Dependencies and scripts
- `tsconfig.json` - TypeScript configuration

The documentation is configured for GitHub Pages deployment with the base path `/copinance-os`. This is set in `next.config.mjs` and adjusts automatically based on `NODE_ENV`.

## Customization

- **Theme**: Edit `theme.config.tsx` to customize colors, logo, footer, etc.
- **Navigation**: Edit `_meta.tsx` files in `pages/` directories to change the sidebar structure
- **Styling**: Nextra uses Tailwind CSS - you can add custom styles if needed
