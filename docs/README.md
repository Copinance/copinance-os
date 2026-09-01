# Documentation site

This site is built with [Nextra](https://nextra.site/) on Next.js. Page content lives in `docs/pages/` as MDX; sidebar titles and order are in `_meta.tsx` files per folder.

The site is the **product documentation** for the `copinance_os` package: how to install and run the CLI, how to embed the library, and how analysis (deterministic vs question-driven) actually works. Vision and “why” live in the repo [MANIFESTO](../MANIFESTO.md). Architecture and ports live under [Developer Guide](https://copinance.github.io/copinance-os/developer-guide/architecture).

Deterministic finance stays in `data` and `domain`. LLMs explain, route, and narrate; they do not replace pricing engines. LLM backends in-tree: **Gemini**, **OpenAI**, **Anthropic**, and **Ollama**.

## Local development

```bash
cd docs
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000). From the repo root you can use `make docs-serve`.

## Production build

```bash
cd docs
npm run build
```

Static output is written to `docs/out/`. GitHub Pages uses base path `/copinance-os` (`next.config.mjs`).

## Configuration files

| File | Purpose |
|------|---------|
| `next.config.mjs` | Next.js / Nextra, GitHub Pages base path |
| `theme.config.tsx` | Theme (logo, footer, search) |
| `package.json` | Scripts and dependencies |
| `tsconfig.json` | TypeScript |

Sidebar: `_meta.tsx` under `pages/` and each section folder.
