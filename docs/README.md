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

All documentation files are located in the `docs/` directory:

```
docs/
├── pages/                 # Documentation pages (MDX format)
│   ├── index.mdx         # Homepage
│   ├── _meta.json        # Navigation configuration
│   ├── getting-started/  # Getting started guides
│   ├── user-guide/       # User documentation
│   ├── developer-guide/  # Developer documentation
│   └── api-reference/    # API documentation
├── package.json          # Dependencies and scripts
├── next.config.js        # Next.js and Nextra configuration
├── theme.config.tsx      # Theme customization
├── tsconfig.json         # TypeScript configuration
└── README.md             # This file
```

## Configuration

- `next.config.js` - Next.js and Nextra configuration
- `theme.config.tsx` - Theme customization
- `package.json` - Dependencies and scripts
- `tsconfig.json` - TypeScript configuration

The documentation is configured for GitHub Pages deployment with the base path `/copinance-os`. This is set in `next.config.js` and will automatically adjust based on the `NODE_ENV`.

## Customization

- **Theme**: Edit `theme.config.tsx` to customize colors, logo, footer, etc.
- **Navigation**: Edit `_meta.json` files in `pages/` directories to change the sidebar structure
- **Styling**: Nextra uses Tailwind CSS - you can add custom styles if needed

