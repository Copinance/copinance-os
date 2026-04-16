"""Logging configuration using structlog."""

from __future__ import annotations

import logging
import sys
from typing import TYPE_CHECKING, Any, cast

import structlog

from copinance_os.infra.config import Settings

if TYPE_CHECKING:
    from structlog.dev import ConsoleRenderer

# Third-party libraries that emit DEBUG trace (HTTP, SQL, parser rules, SDK request dumps).
# Root may be DEBUG (COPINANCEOS_LOG_LEVEL); keep vendor noise at WARNING unless you
# reconfigure these loggers yourself.
_NOISY_STD_LIB_LOGGER_NAMES = (
    "yfinance",
    "peewee",
    "urllib3",
    "urllib3.connectionpool",
    "httpx",
    "httpcore",
    "curl_cffi",
    "hpack",
    # openai: ``openai._base_client`` logs full "Request options" dict at DEBUG
    "openai",
    # markdown_it: rules_block (e.g. fence) log "entering fence: StateBlock(...)" at DEBUG
    "markdown_it",
    # edgar / edgartools: SEC statement normalization (many ``log.debug`` skips per call)
    "edgar",
    # httpxthrottlecache (edgar HTTP): DEBUG when normalizing deprecated Hishel-File cache mode
    "httpxthrottlecache",
)


class _FollowingStderrHandler(logging.Handler):
    """Emit each record to the current ``sys.stderr`` (Rich ``Live``/``Status``-safe).

    We avoid subclassing ``StreamHandler`` with a dynamic ``stream`` property: stdlib
    types declare ``stream`` as a fixed attribute, which makes mypy reject a property
    override. A plain ``Handler`` that always writes via ``sys.stderr`` matches runtime
    behaviour (including following Rich's ``FileProxy`` when stderr is redirected).
    """

    terminator = "\n"

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = self.format(record)
            sys.stderr.write(msg + self.terminator)
            self.flush()
        except RecursionError:
            raise
        except Exception:
            self.handleError(record)

    def flush(self) -> None:
        self.acquire()
        try:
            sys.stderr.flush()
        finally:
            self.release()


def _quiet_noisy_stdlib_loggers() -> None:
    for name in _NOISY_STD_LIB_LOGGER_NAMES:
        logging.getLogger(name).setLevel(logging.WARNING)
    # stdlib asyncio logs "Using selector: KqueueSelector" at DEBUG on loop startup
    logging.getLogger("asyncio").setLevel(logging.INFO)


class _PaddedAfterBracketLevelFormatter:
    """Colored ``[level]`` like structlog, then ASCII spaces so plain width matches the widest tag."""

    __slots__ = ("_level_styles", "_reset", "_target_plain_len")

    def __init__(
        self,
        level_styles: dict[str, str],
        reset_style: str,
        *,
        target_plain_len: int,
    ) -> None:
        self._level_styles = level_styles
        self._reset = reset_style
        self._target_plain_len = target_plain_len

    def __call__(self, key: str, value: object) -> str:
        level = cast(str, value)
        plain = f"[{level}]"
        style = self._level_styles.get(level, "")
        colored = f"[{style}{level}{self._reset}]"
        width = max(self._target_plain_len, len(plain))
        return colored + " " * (width - len(plain))


def _console_renderer_with_aligned_level_column(*, colors: bool) -> ConsoleRenderer:
    """ConsoleRenderer with tight ``[info]`` text and trailing pad for column alignment."""
    from structlog.dev import Column, ConsoleRenderer, LogLevelColumnFormatter  # noqa: PLC0415

    renderer = ConsoleRenderer(colors=colors, pad_level=False)
    columns = list(renderer.columns)
    for idx, col in enumerate(columns):
        if col.key != "level":
            continue
        old = col.formatter
        if not isinstance(old, LogLevelColumnFormatter) or not old.level_styles:
            break
        target_plain = max(len(f"[{k}]") for k in old.level_styles)
        columns[idx] = Column(
            "level",
            _PaddedAfterBracketLevelFormatter(
                old.level_styles,
                old.reset_style,
                target_plain_len=target_plain,
            ),
        )
        break
    renderer.columns = columns
    return renderer


def configure_logging(settings: Settings) -> None:
    """Configure structured logging."""
    log_level = getattr(logging, settings.log_level.upper(), logging.INFO)

    # Stderr: keeps stdout clean for ``--json`` / pipes, and follows Rich's stderr
    # proxy during ``console.status`` so log lines do not splice into the spinner.
    logging.basicConfig(
        format="%(message)s",
        level=log_level,
        handlers=[_FollowingStderrHandler()],
    )
    _quiet_noisy_stdlib_loggers()

    # Configure structlog
    processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
    ]

    if settings.log_format == "json":
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(_console_renderer_with_aligned_level_column(colors=True))

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> Any:
    """Get a structured logger."""
    return structlog.get_logger(name)
