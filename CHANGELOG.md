# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Release Strategy

**Note:** This project is currently in active development with frequent architectural changes and improvements. As such, no package releases will be made until the project reaches a mature and stable state. All changes are tracked in the `[Unreleased]` section below. Once the project stabilizes, versioned releases will begin following Semantic Versioning.

## [Unreleased]

### Changed

- Enhanced CONTRIBUTING.md with commit message template reference, pull request template guidance, and comprehensive "Adding New Tools" section
- Rewrote MANIFESTO.md for improved clarity, structure, and messaging around the project's mission and vision
- Updated README.md section headers to remove emoji formatting for consistency
- Updated market regime detection documentation to include comprehensive guide for Market Regime Indicators Tool

### Added

- Hexagonal architecture with 21+ extension interfaces for data providers, analyzers, strategies, and workflows
- Research status tracking (pending, in_progress, completed, failed)
- Static workflow executor with predefined analysis pipelines
- Agentic workflow executor with AI-powered dynamic analysis and custom question support
- Fundamentals workflow for comprehensive stock fundamental analysis
- Research profile management with financial literacy levels (beginner, intermediate, advanced)
- Stock search by symbol or company name with multiple search types
- yfinance integration for market data and fundamentals
- SEC EDGAR integration for regulatory filings
- Multiple LLM provider support (Gemini, Ollama) with extensible architecture
- Market data tools for quotes and historical prices
- Fundamental data tools for financial statements, metrics, and SEC filings
- Intelligent caching system with local file backend to reduce API calls
- CLI interface with research, profile, stock, and cache management commands
- Interactive profile creation prompts for personalized analysis
- Comprehensive test suite with unit and integration tests
- Complete documentation with Nextra deployed to GitHub Pages
- Market regime detection tools with rule-based methodology:
  - Trend detection tool (bull/bear/neutral) using moving averages and volatility-scaled momentum
  - Volatility regime detection tool (high/normal/low) using rolling volatility analysis
  - Market cycle detection tool using Wyckoff methodology (accumulation/markup/distribution/markdown phases)
  - Extensible architecture supporting multiple detection methods (rule-based, statistical)
  - Market regime indicators tool providing VIX (volatility index), market breadth analysis, and sector rotation signals