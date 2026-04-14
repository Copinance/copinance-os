# Documentation site

This site is built with [Nextra](https://nextra.site/) on Next.js. **Page content** lives in `docs/pages/` as MDX; navigation titles and order are set in `_meta.tsx` files per folder.

## What the docs cover

The docs track the `copinance_os` package:

- **Domain** contracts (models, ports, strategy protocols)
- **Data providers** — yfinance, FRED, SEC/EDGAR (`data.providers.sec`), QuantLib BSM Greeks (first- and higher-order on `OptionGreeks` when valid), and modular **`data/analytics/options`** analytics: `greeks/` + `positioning/` with `build_options_positioning` / `compute_options_positioning_context` (bias, GEX, vanna/charm, mispricing, moneyness, pin risk, surface/flow, …). Methodology is structured via `AnalysisMethodology` on result models. Repo-only integrator notes: [`docs/integration/options-positioning-library-integration.md`](integration/options-positioning-library-integration.md), [`docs/integration/llm-agent-features-integration-guide.md`](integration/llm-agent-features-integration-guide.md).
- **Core orchestration** — `ResearchOrchestrator`, `DefaultJobRunner`, `AnalysisExecutorFactory`, execution engine, pipeline tools, tool bundle discovery (`core.pipeline.tools.discovery`)
- **AI/LLM** — provider adapters (Gemini, OpenAI, Ollama), streaming, tool-calling loop
- **Infra** — DI container, plugin loading, settings
- **Interfaces/CLI** — `main` → `dispatch` (Typer vs natural-language root); `--json` and `--stream` flags; multi-turn conversation (library-only via `conversation_history`); **`analyze options`**: repeat `-e` / `--expiration` for multiple expiries (library: `expiration_dates` on `AnalyzeInstrumentRequest`); **`analyze positioning`** for deterministic aggregate surface metrics; library: optional **`positioning_window`** on `AnalyzeInstrumentRequest` for options runs
- **Literacy-tiered narration** — deterministic instrument/market/macro/question-driven envelopes adapt text output by `financial_literacy` tier while preserving stable machine fields for integrations

Deterministic finance stays in `data` and `domain`; LLMs explain and route, they do not replace pricing engines. The canonical package tree is in [Architecture](https://copinance.github.io/copinance-os/developer-guide/architecture#package-tree-source).

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
