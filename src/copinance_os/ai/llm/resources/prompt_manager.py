"""Prompt manager for loading and formatting LLM prompts.

Library clients can inject their own prompt templates. If none are provided,
Copinance OS uses built-in default templates from package data.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from importlib import resources
from pathlib import Path
from typing import Any, cast

import structlog

logger = structlog.get_logger(__name__)

# Package reference for loading default prompts
_PACKAGE = "copinance_os.ai.llm.resources"

# Well-known prompt names (use these keys when providing custom templates)
ANALYZE_QUESTION_DRIVEN_PROMPT_NAME = "analyze_question_driven"


class PromptManager:
    """Manages LLM prompt templates with optional client overrides.

    Templates are identified by name (e.g. ``analyze_question_driven``) and each
    has ``system_prompt`` and ``user_prompt`` strings. Templates support
    variable substitution using ``{variable_name}``.

    Resolution order when a prompt is requested:
    1. In-memory overlay (if provided in ``templates``)
    2. File in ``resources_dir`` (if provided)
    3. Package defaults (if ``use_package_data`` is True)

    Use ``PromptManager()`` for defaults only, or pass ``templates`` and/or
    ``resources_dir`` to customize. When using as a library, pass
    ``prompt_templates`` or ``prompt_manager`` to ``get_container()``.
    """

    def __init__(
        self,
        *,
        templates: dict[str, dict[str, str]] | None = None,
        resources_dir: Path | None = None,
        use_package_data: bool = True,
    ) -> None:
        """Initialize the prompt manager.

        Args:
            templates: Optional in-memory overlay. Keys are prompt names
                (e.g. ``analyze_question_driven``), values are dicts with
                ``system_prompt`` and ``user_prompt``. Used first when
                resolving a prompt; missing names fall back to resources_dir
                or package data.
            resources_dir: Optional directory containing custom prompt JSON
                files (e.g. ``analyze_question_driven.json``). Checked after
                ``templates``, before package data.
            use_package_data: If True, fall back to built-in package prompts
                for any name not found in templates or resources_dir.
        """
        self._templates = dict(templates) if templates else {}
        self._resources_dir = Path(resources_dir) if resources_dir else None
        self._use_package_data = use_package_data
        self._prompts_cache: dict[str, dict[str, str]] = {}

        if self._resources_dir:
            logger.info(
                "Prompt manager initialized",
                resources_dir=str(self._resources_dir),
                use_package_data=use_package_data,
                overlay_keys=list(self._templates.keys()) or None,
            )
        else:
            logger.info(
                "Prompt manager initialized",
                use_package_data=use_package_data,
                overlay_keys=list(self._templates.keys()) or None,
            )

    def _load_prompt_file(self, prompt_name: str) -> dict[str, str]:
        """Load prompt data for a name (overlay → resources_dir → package)."""
        if prompt_name in self._prompts_cache:
            return self._prompts_cache[prompt_name]

        # 1. In-memory overlay
        if prompt_name in self._templates:
            data = self._templates[prompt_name]
            self._validate_prompt_data(data, prompt_name)
            self._prompts_cache[prompt_name] = dict(data)
            logger.debug("Loaded prompt from overlay", prompt_name=prompt_name)
            return self._prompts_cache[prompt_name]

        # 2. resources_dir file
        if self._resources_dir:
            custom_file = self._resources_dir / f"{prompt_name}.json"
            if custom_file.exists():
                try:
                    with custom_file.open(encoding="utf-8") as f:
                        prompt_data = cast(dict[str, str], json.load(f))
                    self._validate_prompt_data(prompt_data, prompt_name)
                    self._prompts_cache[prompt_name] = prompt_data
                    logger.debug(
                        "Loaded prompt from resources_dir",
                        prompt_name=prompt_name,
                        path=str(custom_file),
                    )
                    return prompt_data
                except (json.JSONDecodeError, ValueError) as e:
                    logger.warning(
                        "Failed to load prompt from resources_dir, falling back",
                        prompt_name=prompt_name,
                        error=str(e),
                    )

        # 3. Package data
        if self._use_package_data:
            try:
                prompt_data = self._load_from_package(prompt_name)
                self._prompts_cache[prompt_name] = prompt_data
                logger.debug("Loaded prompt from package", prompt_name=prompt_name)
                return prompt_data
            except FileNotFoundError:
                pass

        raise FileNotFoundError(
            f"Prompt '{prompt_name}' not found. "
            f"Checked: overlay, resources_dir={self._resources_dir}, use_package_data={self._use_package_data}"
        )

    def _load_from_package(self, prompt_name: str) -> dict[str, str]:
        """Load prompt from package data using importlib.resources."""
        try:
            resource_path = resources.files(_PACKAGE) / f"{prompt_name}.json"
            with (
                resources.as_file(resource_path) as prompt_file,
                Path(prompt_file).open(encoding="utf-8") as f,
            ):
                prompt_data = cast(dict[str, str], json.load(f))
            self._validate_prompt_data(prompt_data, prompt_name)
            return prompt_data
        except (FileNotFoundError, ModuleNotFoundError, AttributeError) as e:
            raise FileNotFoundError(f"Prompt file '{prompt_name}.json' not found in package") from e
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in package prompt '{prompt_name}.json': {e}") from e

    def _validate_prompt_data(self, prompt_data: dict[str, Any], prompt_name: str) -> None:
        """Validate prompt structure (must have system_prompt and user_prompt)."""
        if not isinstance(prompt_data, dict):
            raise ValueError(f"Prompt '{prompt_name}' must be a JSON object")
        if "system_prompt" not in prompt_data or "user_prompt" not in prompt_data:
            raise ValueError(
                f"Prompt '{prompt_name}' must contain 'system_prompt' and 'user_prompt'"
            )

    def get_prompt(
        self,
        prompt_name: str,
        **kwargs: Any,
    ) -> tuple[str, str]:
        """Return (system_prompt, user_prompt) with variables substituted.

        Args:
            prompt_name: Name of the prompt (e.g. ``analyze_question_driven``).
            **kwargs: Variables to substitute in the templates (e.g. question,
                tools_description, financial_literacy).

        Returns:
            Tuple of (system_prompt, user_prompt) with ``{key}`` replaced by
            kwargs.

        Example:
            >>> pm = PromptManager()
            >>> system, user = pm.get_prompt(
            ...     "analyze_question_driven",
            ...     question="What is the P/E of AAPL?",
            ...     tools_description="...",
            ...     tool_examples="...",
            ...     financial_literacy="intermediate",
            ... )
        """
        prompt_data = self._load_prompt_file(prompt_name)
        # Provide default for common template variables when not passed
        kwargs = dict(kwargs)
        kwargs.setdefault("current_date", datetime.now(UTC).strftime("%Y-%m-%d"))
        system_prompt = prompt_data["system_prompt"].format(**kwargs)
        user_prompt = prompt_data["user_prompt"].format(**kwargs)
        return system_prompt, user_prompt

    def get_system_prompt(self, prompt_name: str, **kwargs: Any) -> str:
        """Return only the system prompt with variables substituted."""
        prompt_data = self._load_prompt_file(prompt_name)
        kwargs = dict(kwargs)
        kwargs.setdefault("current_date", datetime.now(UTC).strftime("%Y-%m-%d"))
        return prompt_data["system_prompt"].format(**kwargs)

    def get_user_prompt(self, prompt_name: str, **kwargs: Any) -> str:
        """Return only the user prompt with variables substituted."""
        prompt_data = self._load_prompt_file(prompt_name)
        kwargs = dict(kwargs)
        kwargs.setdefault("current_date", datetime.now(UTC).strftime("%Y-%m-%d"))
        return prompt_data["user_prompt"].format(**kwargs)
