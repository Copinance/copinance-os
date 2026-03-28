# Documentation site

This site is built with [Nextra](https://nextra.site/) on Next.js. **Page content** lives in `docs/pages/` as MDX; navigation titles and order are set in `_meta.tsx` files per folder.

## Philosophy (what the docs describe)

The docs track the **`copinance_os`** package: **domain** contracts, **data** providers (including **SEC/EDGAR** via `edgartools` under `data.providers.sec`) and analytics, **core** orchestration (`ResearchOrchestrator`, execution engine, pipeline tools), **ai/llm** for explanation and tool use, **infra** for DI, and **interfaces/cli**. Deterministic finance stays in data and domain; LLMs explain and route, they do not replace pricing engines.

## Local development

```bash
cd docs
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

## Production build

```bash
cd docs
npm run build
```

Static output is written to `docs/out/`.

## Configuration files

| File | Purpose |
|------|---------|
| `next.config.mjs` | Next.js / Nextra, base path for GitHub Pages (`/copinance-os`) |
| `theme.config.tsx` | Theme (logo, footer, search) |
| `package.json` | Scripts and dependencies |
| `tsconfig.json` | TypeScript |

## Customization

- **Theme**: `theme.config.tsx`
- **Sidebar**: `_meta.tsx` under `pages/` and subfolders
- **Styling**: Nextra uses Tailwind CSS
