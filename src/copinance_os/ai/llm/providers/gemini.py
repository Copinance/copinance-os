"""Google Gemini LLM provider implementation."""

import asyncio
import json
import re
from collections.abc import AsyncGenerator, Awaitable, Callable
from decimal import Decimal
from typing import Any, cast

import structlog

try:
    import google.genai as genai

    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False
    genai = None  # type: ignore[assignment]

from copinance_os.ai.llm.providers.base import LLMProvider
from copinance_os.ai.llm.streaming import LLMTextStreamEvent, TextStreamingMode
from copinance_os.ai.llm.tool_loop_streaming import (
    generate_turn_text_with_stream,
    maybe_emit_tool_round_rollback,
)
from copinance_os.core.execution_engine.question_driven_tool_summary import (
    build_partial_synthesis_message,
    is_tool_call_json_text,
)
from copinance_os.core.pipeline.tools.tool_executor import ToolExecutor
from copinance_os.core.progress.emit import maybe_emit_progress
from copinance_os.domain.models.agent_progress import IterationStartedEvent
from copinance_os.domain.models.llm_conversation import LLMConversationTurn
from copinance_os.domain.ports.progress import ProgressSink
from copinance_os.domain.ports.tools import Tool

logger = structlog.get_logger(__name__)


class GeminiProvider(LLMProvider):
    """Google Gemini LLM provider implementation.

    This provider uses Google's Gemini API for text generation.

    For CLI usage, configure using the COPINANCEOS_GEMINI_API_KEY environment variable.
    For library integration, provide LLMConfig with api_key parameter.

    Example:
        ```python
        from copinance_os.ai.llm.providers import GeminiProvider

        # Direct instantiation
        provider = GeminiProvider(api_key="your-api-key")
        response = await provider.generate_text("Analyze this instrument...")

        # Using LLMConfig (recommended for library integration)
        from copinance_os.ai.llm.config import LLMConfig
        from copinance_os.ai.llm.providers.factory import LLMProviderFactory

        llm_config = LLMConfig(provider="gemini", api_key="your-api-key")
        provider = LLMProviderFactory.create_provider("gemini", llm_config=llm_config)
        ```
    """

    def __init__(
        self,
        api_key: str | None = None,
        model_name: str = "gemini-1.5-pro",
        temperature: float = 0.7,
        max_output_tokens: int | None = None,
        *,
        text_streaming_mode: TextStreamingMode = "auto",
        disable_native_text_stream: bool = False,
    ) -> None:
        """Initialize Gemini provider.

        Args:
            api_key: Gemini API key. Required for cloud usage.
            model_name: Gemini model to use (default: "gemini-1.5-pro")
                       Options: gemini-2.5-flash, gemini-1.5-pro, gemini-1.5-flash, gemini-pro
                       All support function calling for question-driven analysis
            temperature: Default temperature for generation
            max_output_tokens: Default max output tokens
            text_streaming_mode: Default mode for :meth:`generate_text_stream`
            disable_native_text_stream: If True, API streaming is disabled (buffered only).
        """
        self._api_key = api_key
        self._model_name = model_name
        self._default_temperature = temperature
        self._default_max_output_tokens = max_output_tokens
        self._text_streaming_mode: TextStreamingMode = text_streaming_mode
        self._disable_native_text_stream = disable_native_text_stream
        self._client: Any = None

        if GEMINI_AVAILABLE and api_key:
            try:
                self._client = genai.Client(api_key=api_key)
                self._model_name = model_name
                logger.info("Initialized Gemini provider", model=model_name)
            except Exception as e:
                logger.warning("Failed to initialize Gemini client", error=str(e))
        else:
            logger.warning(
                "Gemini not available",
                gemini_available=GEMINI_AVAILABLE,
                api_key_provided=api_key is not None,
            )

    async def generate_text(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        **kwargs: Any,
    ) -> str:
        """Generate text using Gemini.

        Args:
            prompt: The user prompt/query
            system_prompt: Optional system prompt (prepended to prompt)
            temperature: Sampling temperature (uses default if not provided)
            max_tokens: Maximum tokens to generate (uses default if not provided)
            **kwargs: Additional parameters (e.g., top_p, top_k)

        Returns:
            Generated text response

        Raises:
            RuntimeError: If Gemini is not available or not configured
            Exception: If the API call fails
        """
        if not GEMINI_AVAILABLE:
            raise RuntimeError("google-genai package is not installed")

        if not self._api_key:
            raise RuntimeError("Gemini API key is not configured")

        if self._client is None:
            raise RuntimeError("Gemini client is not initialized")

        # Combine system prompt and user prompt
        full_prompt = prompt
        if system_prompt:
            full_prompt = f"{system_prompt}\n\n{prompt}"

        # Prepare generation config
        config = self._build_generation_config(temperature, max_tokens, **kwargs)

        try:
            logger.debug(
                "Generating text with Gemini",
                model=self._model_name,
                prompt_length=len(full_prompt),
            )

            response = await self._call_gemini_api(full_prompt, config)
            return self._extract_response_text(response)

        except Exception as e:
            logger.error("Gemini API call failed", error=str(e))
            raise

    async def is_available(self) -> bool:
        """Check if Gemini provider is available and configured.

        Returns:
            True if Gemini is available and configured, False otherwise
        """
        if not GEMINI_AVAILABLE:
            return False

        if not self._api_key:
            return False

        if self._client is None:
            return False

        # Try a simple test call
        try:
            test_response = await self.generate_text("test", temperature=0.1, max_tokens=10)
            return bool(test_response)
        except Exception as e:
            logger.debug("Gemini availability check failed", error=str(e))
            return False

    def get_provider_name(self) -> str:
        """Get the name of the LLM provider.

        Returns:
            "gemini"
        """
        return "gemini"

    def get_model_name(self) -> str | None:
        """Get the model name being used by this provider.

        Returns:
            Model name (e.g., "gemini-1.5-pro") or None if not configured
        """
        return self._model_name

    def supports_native_text_stream(self) -> bool:
        return (
            bool(GEMINI_AVAILABLE and self._api_key and self._client is not None)
            and not self._disable_native_text_stream
        )

    @staticmethod
    def _delta_from_cumulative_fragment(piece: str, acc_ref: list[str]) -> str:
        """Turn a (possibly cumulative) stream fragment into an incremental delta."""
        if not piece:
            return ""
        acc = acc_ref[0]
        if piece.startswith(acc):
            delta = piece[len(acc) :]
            acc_ref[0] = piece
            return delta
        acc_ref[0] = acc + piece
        return piece

    def _sync_generate_content_stream(
        self, contents: str | list[Any], config: dict[str, Any]
    ) -> Any:
        """Synchronous streaming iterator from the Gemini client (run in a worker thread)."""
        if not GEMINI_AVAILABLE or genai is None:
            raise RuntimeError("google-genai package is not installed")
        if config:
            try:
                gen_config = genai.types.GenerateContentConfig(**config)
                return self._client.models.generate_content_stream(
                    model=self._model_name,
                    contents=contents,
                    config=gen_config,
                )
            except (AttributeError, TypeError):
                return self._client.models.generate_content_stream(
                    model=self._model_name,
                    contents=contents,
                    config=config,
                )
        return self._client.models.generate_content_stream(
            model=self._model_name,
            contents=contents,
        )

    async def _iter_native_text_stream(
        self,
        prompt: str,
        system_prompt: str | None,
        temperature: float | None,
        max_tokens: int | None,
        **kwargs: Any,
    ) -> AsyncGenerator[LLMTextStreamEvent, None]:
        if not GEMINI_AVAILABLE:
            raise RuntimeError("google-genai package is not installed")
        if not self._api_key or self._client is None:
            raise RuntimeError("Gemini client is not initialized")

        full_prompt = prompt
        if system_prompt:
            full_prompt = f"{system_prompt}\n\n{prompt}"

        config = self._build_generation_config(temperature, max_tokens, **kwargs)
        loop = asyncio.get_running_loop()
        queue: asyncio.Queue[tuple[str, Any]] = asyncio.Queue(maxsize=512)
        acc_ref = [""]

        def worker() -> None:
            try:
                stream = self._sync_generate_content_stream(full_prompt, config)
                last_usage: dict[str, int] | None = None
                for chunk in stream:
                    last_usage = self._extract_usage(chunk)
                    piece = self._extract_response_text(chunk)
                    delta = self._delta_from_cumulative_fragment(piece, acc_ref)
                    if delta:
                        asyncio.run_coroutine_threadsafe(queue.put(("d", delta)), loop).result()
                usage_out = last_usage if last_usage and any(last_usage.values()) else None
                asyncio.run_coroutine_threadsafe(queue.put(("done", usage_out)), loop).result()
            except Exception as e:
                asyncio.run_coroutine_threadsafe(queue.put(("err", e)), loop).result()

        task = asyncio.create_task(asyncio.to_thread(worker))
        try:
            while True:
                kind, payload = await queue.get()
                if kind == "d" and payload:
                    yield LLMTextStreamEvent(
                        kind="text_delta",
                        text_delta=payload,
                        native_streaming=True,
                    )
                elif kind == "done":
                    yield LLMTextStreamEvent(
                        kind="done",
                        native_streaming=True,
                        usage=payload,
                    )
                    break
                elif kind == "err":
                    raise payload
        finally:
            await task

    def _extract_response_text(self, response: Any) -> str:
        """Extract text from Gemini API response.

        Handles different response structures from the google-genai library.

        Args:
            response: Gemini API response object

        Returns:
            Extracted text, or empty string if extraction fails
        """
        if response is None:
            logger.warning("Empty response from Gemini")
            return ""

        # Try direct text attribute
        if hasattr(response, "text") and response.text:
            return cast(str, response.text)

        # Try candidates structure
        if hasattr(response, "candidates") and response.candidates:
            candidate = response.candidates[0]
            if hasattr(candidate, "content"):
                content = candidate.content
                if hasattr(content, "parts") and content.parts:
                    # Collect all text parts
                    text_parts = []
                    for part in content.parts:
                        if hasattr(part, "text") and part.text:
                            text_parts.append(part.text)
                        elif part:
                            text_parts.append(str(part))
                    if text_parts:
                        return "".join(text_parts)
                elif hasattr(content, "text"):
                    return cast(str, content.text)

        # Try to convert response to string
        response_str = str(response)
        if response_str and response_str != "None":
            return response_str

        logger.warning("Could not extract text from Gemini response", response_type=type(response))
        return ""

    def _extract_usage(self, response: Any) -> dict[str, int]:
        """Extract token usage from Gemini API response if available.

        Returns dict with input_tokens, output_tokens, total_tokens (0 if not available).
        """
        out: dict[str, int] = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
        if response is None:
            return out
        um = getattr(response, "usage_metadata", None)
        if um is None:
            return out
        out["input_tokens"] = (
            getattr(um, "prompt_token_count", None) or getattr(um, "prompt_tokens", None) or 0
        )
        out["output_tokens"] = (
            getattr(um, "candidates_token_count", None)
            or getattr(um, "completion_tokens", None)
            or 0
        )
        out["total_tokens"] = (
            getattr(um, "total_token_count", None)
            or getattr(um, "total_tokens", None)
            or (out["input_tokens"] + out["output_tokens"])
        )
        return out

    def _build_generation_config(
        self,
        temperature: float | None = None,
        max_tokens: int | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Build generation config dictionary.

        Args:
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            **kwargs: Additional parameters

        Returns:
            Configuration dictionary
        """
        config: dict[str, Any] = {}

        if temperature is not None:
            config["temperature"] = temperature
        elif self._default_temperature is not None:
            config["temperature"] = self._default_temperature

        if max_tokens is not None:
            config["max_output_tokens"] = max_tokens
        elif self._default_max_output_tokens is not None:
            config["max_output_tokens"] = self._default_max_output_tokens

        config.update(kwargs)
        return config

    async def _call_gemini_api(
        self, contents: str | list[Any], config: dict[str, Any] | None = None
    ) -> Any:
        """Call Gemini with a string or multi-turn ``contents`` list."""

        def _generate() -> Any:
            if config:
                try:
                    gen_config = genai.types.GenerateContentConfig(**config)
                    return self._client.models.generate_content(
                        model=self._model_name,
                        contents=contents,
                        config=gen_config,
                    )
                except (AttributeError, TypeError):
                    return self._client.models.generate_content(
                        model=self._model_name,
                        contents=contents,
                        config=config,
                    )
            return self._client.models.generate_content(
                model=self._model_name,
                contents=contents,
            )

        return await asyncio.to_thread(_generate)

    @staticmethod
    def _gemini_build_contents(
        prior: list[LLMConversationTurn] | None, user_prompt: str
    ) -> list[Any]:
        """Map prior turns + current user task to Gemini ``Content`` list (user / model roles)."""
        if not GEMINI_AVAILABLE or genai is None:
            raise RuntimeError("google-genai package is not installed")
        contents: list[Any] = []
        for t in prior or []:
            g_role = "user" if t.role == "user" else "model"
            contents.append(
                genai.types.Content(
                    role=g_role,
                    parts=[genai.types.Part.from_text(text=t.content)],
                )
            )
        contents.append(
            genai.types.Content(
                role="user",
                parts=[genai.types.Part.from_text(text=user_prompt)],
            )
        )
        return contents

    async def _gemini_stream_tool_turn(
        self,
        contents: list[Any],
        config: dict[str, Any],
        on_stream_event: Callable[[LLMTextStreamEvent], Awaitable[None]],
    ) -> str:
        """Single tool-loop generation with native streaming over ``contents``."""
        if not GEMINI_AVAILABLE:
            raise RuntimeError("google-genai package is not installed")
        if not self._api_key or self._client is None:
            raise RuntimeError("Gemini client is not initialized")

        loop = asyncio.get_running_loop()
        queue: asyncio.Queue[tuple[str, Any]] = asyncio.Queue(maxsize=512)
        acc_ref = [""]

        def worker() -> None:
            try:
                stream = self._sync_generate_content_stream(contents, config)
                last_usage: dict[str, int] | None = None
                for chunk in stream:
                    last_usage = self._extract_usage(chunk)
                    piece = self._extract_response_text(chunk)
                    delta = self._delta_from_cumulative_fragment(piece, acc_ref)
                    if delta:
                        asyncio.run_coroutine_threadsafe(queue.put(("d", delta)), loop).result()
                usage_out = last_usage if last_usage and any(last_usage.values()) else None
                asyncio.run_coroutine_threadsafe(queue.put(("done", usage_out)), loop).result()
            except Exception as e:
                asyncio.run_coroutine_threadsafe(queue.put(("err", e)), loop).result()

        task = asyncio.create_task(asyncio.to_thread(worker))
        parts: list[str] = []
        try:
            while True:
                kind, payload = await queue.get()
                if kind == "d" and payload:
                    parts.append(payload)
                    await on_stream_event(
                        LLMTextStreamEvent(
                            kind="text_delta",
                            text_delta=payload,
                            native_streaming=True,
                        )
                    )
                elif kind == "done":
                    break
                elif kind == "err":
                    raise payload
        finally:
            await task
        return "".join(parts)

    @staticmethod
    def _make_json_serializable(obj: Any) -> Any:
        """Recursively convert objects to JSON-serializable types.

        Args:
            obj: Object to convert

        Returns:
            JSON-serializable version of the object
        """
        if isinstance(obj, Decimal):
            return float(obj)
        if isinstance(obj, dict):
            return {k: GeminiProvider._make_json_serializable(v) for k, v in obj.items()}
        if isinstance(obj, (list, tuple)):
            return [GeminiProvider._make_json_serializable(item) for item in obj]
        if hasattr(obj, "model_dump"):  # Pydantic models
            return GeminiProvider._make_json_serializable(obj.model_dump())
        if hasattr(obj, "__dict__"):
            return GeminiProvider._make_json_serializable(obj.__dict__)

        # Test if already serializable
        try:
            json.dumps(obj)
            return obj
        except (TypeError, ValueError):
            return str(obj)

    def _convert_tool_to_gemini_function(self, tool: Tool) -> dict[str, Any]:
        """Convert a Tool to Gemini function declaration format.

        Args:
            tool: Tool to convert

        Returns:
            Gemini function declaration dict
        """
        schema = tool.get_schema()
        return {
            "name": schema.name,
            "description": schema.description,
            "parameters": schema.parameters,
        }

    def _parse_tool_calls_from_response(
        self, response_text: str, executor: ToolExecutor
    ) -> list[dict[str, Any]]:
        """Parse tool calls from LLM response text.

        Args:
            response_text: Response text from LLM
            executor: Tool executor for validation

        Returns:
            List of parsed tool calls with name and args
        """
        function_calls = []
        json_patterns = [
            r'\{[^{}]*"tool"[^{}]*\}',  # Simple pattern
            r'\{[^{}]*"tool"[^{}]*"args"[^{}]*\}',  # With args
            r'\{"tool":\s*"[^"]+",\s*"args":\s*\{[^}]*\}\}',  # More specific
        ]

        for pattern in json_patterns:
            json_matches = re.finditer(pattern, response_text, re.DOTALL)
            for json_match in json_matches:
                try:
                    action_data = json.loads(json_match.group())
                    tool_name = action_data.get("tool")
                    tool_args = action_data.get("args", {})
                    if tool_name and tool_name in executor.list_tools():
                        function_calls.append({"name": tool_name, "args": tool_args})
                        logger.debug(
                            "Parsed tool call from response", tool=tool_name, pattern=pattern
                        )
                except (json.JSONDecodeError, KeyError):
                    continue

            if function_calls:
                break  # Found tool calls, no need to try other patterns

        return function_calls

    def _get_tool_schema_info(
        self, tool_name: str, executor: ToolExecutor
    ) -> dict[str, Any] | None:
        """Get structured tool schema information.

        Args:
            tool_name: Name of the tool
            executor: Tool executor to get tool schema

        Returns:
            Dictionary with tool schema information, or None if tool not found
        """
        tool = executor.get_tool(tool_name)
        if not tool:
            return None

        schema = tool.get_schema()
        param_info = schema.parameters.get("properties", {})
        required = schema.parameters.get("required", [])

        return {
            "name": schema.name,
            "description": schema.description,
            "parameters": {
                name: {
                    "type": param_schema.get("type", ""),
                    "description": param_schema.get("description", ""),
                    "required": name in required,
                    "enum": param_schema.get("enum"),
                    "default": param_schema.get("default"),
                }
                for name, param_schema in param_info.items()
            },
            "required": required,
        }

    async def generate_with_tools(
        self,
        prompt: str,
        tools: list[Tool] | None = None,
        system_prompt: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        max_iterations: int = 5,
        *,
        stream: bool = False,
        on_stream_event: Callable[[LLMTextStreamEvent], Awaitable[None]] | None = None,
        prior_conversation: list[LLMConversationTurn] | None = None,
        progress_sink: ProgressSink | None = None,
        run_id: str | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Generate text with optional tool usage using Gemini function calling.

        Args:
            prompt: The user prompt/query
            tools: Optional list of tools available to the LLM
            system_prompt: Optional system prompt for context
            temperature: Sampling temperature (0.0 to 1.0)
            max_tokens: Maximum tokens to generate
            max_iterations: Maximum number of tool call iterations
            **kwargs: Additional parameters

        Returns:
            Dictionary with text, tool_calls, and iterations

        Raises:
            RuntimeError: If Gemini is not available
            NotImplementedError: If tools are provided but Gemini doesn't support them
        """
        if not GEMINI_AVAILABLE:
            raise RuntimeError("google-genai package is not installed")

        if not self._api_key or self._client is None:
            raise RuntimeError("Gemini client is not initialized")

        # If no tools, fallback to regular generation
        if tools is None or len(tools) == 0:
            text = await generate_turn_text_with_stream(
                self,
                prompt=prompt,
                system_prompt=system_prompt,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=stream,
                on_stream_event=on_stream_event,
                **kwargs,
            )
            return {
                "text": text,
                "tool_calls": [],
                "iterations": 1,
                "synthesis_status": "complete",
                "llm_synthesis_error": None,
            }

        # Create tool executor
        executor = ToolExecutor(tools, progress_sink=progress_sink, run_id=run_id)

        # Native multi-turn: prior user/model turns + current user task; system via config
        base_cfg = self._build_generation_config(temperature, max_tokens, **kwargs)
        config = dict(base_cfg)
        if system_prompt:
            config["systemInstruction"] = system_prompt

        tool_calls_made: list[dict[str, Any]] = []
        contents: list[Any] = self._gemini_build_contents(prior_conversation, prompt)
        response_text = ""
        usage_total: dict[str, int] = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
        # Track recent tool calls for loop detection
        recent_tool_calls: list[tuple[str, tuple[tuple[str, Any], ...]]] = []
        max_recent_history = 3  # Check last 3 calls for loops
        iteration_error: Exception | None = None

        for iteration in range(max_iterations):
            try:
                if progress_sink is not None and run_id is not None:
                    await maybe_emit_progress(
                        progress_sink,
                        IterationStartedEvent(
                            run_id=run_id,
                            iteration=iteration + 1,
                            max_iterations=max_iterations,
                        ),
                    )
                logger.debug(
                    "Gemini tool calling iteration",
                    iteration=iteration + 1,
                    max_iterations=max_iterations,
                )

                # Generate with Gemini multi-turn contents (prior turns + in-loop model/user)
                if stream and on_stream_event:
                    response_text = await self._gemini_stream_tool_turn(
                        contents, config, on_stream_event
                    )
                else:
                    response = await self._call_gemini_api(contents, config)
                    response_text = self._extract_response_text(response)
                    u = self._extract_usage(response)
                    for k in usage_total:
                        usage_total[k] += u.get(k, 0)

                # Parse tool calls from response
                function_calls = self._parse_tool_calls_from_response(response_text, executor)

                await maybe_emit_tool_round_rollback(
                    stream=stream,
                    on_stream_event=on_stream_event,
                    had_tool_calls=bool(function_calls),
                )

                # If no function calls found, we're done
                if not function_calls:
                    break

                # Check for loops: same tool call repeated (before execution)
                loop_detected = False
                for func_call in function_calls:
                    tool_name_check = func_call["name"]
                    tool_args_check = func_call.get("args", {})
                    # Create signature: (tool_name, tuple of sorted (key, value) pairs)
                    sorted_items_check = tuple(sorted(tool_args_check.items()))
                    call_signature_check: tuple[str, tuple[tuple[str, Any], ...]] = (
                        tool_name_check,
                        sorted_items_check,
                    )

                    # Check if this exact call was made recently
                    if call_signature_check in recent_tool_calls:
                        logger.warning(
                            "Detected tool call loop - same call repeated",
                            tool_name=tool_name_check,
                            args=tool_args_check,
                            iteration=iteration + 1,
                        )
                        loop_detected = True
                        break

                # If we detected a loop, stop iterating
                if loop_detected:
                    logger.warning(
                        "Stopping iteration due to detected loop",
                        iteration=iteration + 1,
                    )
                    break

                # Execute function calls; then append model + user(tool feedback) for Gemini turns
                tool_feedback_parts: list[str] = []
                stop_suffix: str | None = None
                for call_idx, func_call in enumerate(function_calls):
                    tool_name = func_call["name"]
                    tool_args = func_call.get("args", {})

                    logger.info("Executing tool", tool_name=tool_name, args=tool_args)
                    tool_result = await executor.execute_tool(
                        tool_name,
                        progress_iteration=iteration + 1,
                        progress_call_index=call_idx,
                        **tool_args,
                    )

                    # Track this call for loop detection
                    sorted_items = tuple(sorted(tool_args.items()))
                    call_signature: tuple[str, tuple[tuple[str, Any], ...]] = (
                        tool_name,
                        sorted_items,
                    )
                    recent_tool_calls.append(call_signature)
                    # Keep only recent history
                    if len(recent_tool_calls) > max_recent_history:
                        recent_tool_calls.pop(0)

                    # Serialize response data for storage
                    response_data = None
                    if tool_result.success and tool_result.data is not None:
                        # Serialize data, potentially truncating very large responses
                        serialized_data = self._make_json_serializable(tool_result.data)
                        # Truncate large lists (e.g., historical data with 1000+ points)
                        if isinstance(serialized_data, list) and len(serialized_data) > 100:
                            response_data = {
                                "_truncated": True,
                                "_total_items": len(serialized_data),
                                "_items_shown": 100,
                                "data": serialized_data[:100],
                                "note": f"Response truncated: showing first 100 of {len(serialized_data)} items",
                            }
                        else:
                            response_data = serialized_data

                    tool_calls_made.append(
                        {
                            "tool": tool_name,
                            "args": tool_args,
                            "success": tool_result.success,
                            "error": tool_result.error,
                            "response": response_data,
                            "metadata": (
                                self._make_json_serializable(tool_result.metadata)
                                if tool_result.metadata
                                else None
                            ),
                        }
                    )

                    # Check for empty results or invalid parameters that might indicate the LLM is stuck
                    is_empty_result = False
                    has_invalid_params = False

                    if tool_result.success:
                        # Check for obviously invalid parameters
                        invalid_symbols = [
                            "UNKNOWN",
                            "UNKNOWN_COMPANY",
                            "UNKNOWN_SYMBOL",
                            "N/A",
                            "NULL",
                        ]
                        if any(
                            str(v).upper() in invalid_symbols
                            for v in tool_args.values()
                            if isinstance(v, str)
                        ):
                            has_invalid_params = True
                            logger.warning(
                                "Tool called with invalid parameters",
                                tool_name=tool_name,
                                args=tool_args,
                            )

                        # Check if result is empty
                        if (
                            tool_result.data is None
                            or tool_result.data == []
                            or tool_result.data == {}
                        ):
                            is_empty_result = True
                        elif isinstance(tool_result.data, dict):
                            # Check if dict has no meaningful data
                            has_data = any(
                                v not in ([], {}, None, "", 0) for v in tool_result.data.values()
                            )
                            if not has_data:
                                is_empty_result = True

                    # Prepare result data for next iteration (generic JSON format)
                    if not tool_result.success:
                        error_msg = tool_result.error or "Unknown error"
                        # Include tool schema info for parameter validation errors
                        tool_schema = None
                        if (
                            "must be one of" in error_msg
                            or "Missing required parameter" in error_msg
                        ):
                            tool_schema = self._get_tool_schema_info(tool_name, executor)

                        result_data = {
                            "tool": tool_name,
                            "success": False,
                            "error": error_msg,
                        }
                        if tool_schema:
                            result_data["tool_schema"] = tool_schema
                    else:
                        result_data = {
                            "tool": tool_name,
                            "success": True,
                            "data": tool_result.data,
                        }
                        # Add warning if result is empty or has invalid params
                        if is_empty_result or has_invalid_params:
                            warning_msg = ""
                            if has_invalid_params:
                                warning_msg = (
                                    "Tool was called with invalid parameters (e.g., UNKNOWN_COMPANY_SYMBOL). "
                                    "Please use the correct instrument symbol from the original question. "
                                )
                            if is_empty_result:
                                warning_msg += (
                                    "Tool returned empty result. "
                                    "This may indicate invalid parameters or no data available. "
                                )
                                # Use suggestion from tool metadata if available
                                if tool_result.metadata and "suggestion" in tool_result.metadata:
                                    warning_msg += tool_result.metadata["suggestion"]
                            # Suggest stopping after multiple attempts unless metadata indicates otherwise
                            should_suggest_stop = True
                            if tool_result.metadata and tool_result.metadata.get(
                                "allow_retry", False
                            ):
                                should_suggest_stop = False
                            if should_suggest_stop:
                                warning_msg += "Consider stopping and providing a final answer based on available information."
                            result_data["warning"] = warning_msg
                            logger.warning(
                                "Tool issue detected",
                                tool_name=tool_name,
                                args=tool_args,
                                empty_result=is_empty_result,
                                invalid_params=has_invalid_params,
                            )

                    # Collect tool result JSON for the following user turn
                    serializable_data = self._make_json_serializable(result_data)
                    tool_result_json = json.dumps(serializable_data, indent=2)
                    tool_feedback_parts.append(f"Tool execution result:\n{tool_result_json}")

                    # If we got empty results or invalid params, suggest stopping to avoid loops
                    # But respect tool metadata that indicates retry is allowed
                    should_stop = (is_empty_result or has_invalid_params) and iteration >= 1
                    if should_stop:
                        # Check if tool metadata allows retry
                        allow_retry = tool_result.metadata and tool_result.metadata.get(
                            "allow_retry", False
                        )
                        if not allow_retry:
                            logger.info(
                                "Issue detected - suggesting LLM should stop",
                                tool_name=tool_name,
                                empty_result=is_empty_result,
                                invalid_params=has_invalid_params,
                            )
                            stop_suffix = (
                                "IMPORTANT: Stop making tool calls now. "
                                "The tool returned empty results or was called with invalid parameters. "
                                "Provide your final answer based on any data you have received, "
                                "or explain that you cannot answer the question with the available tools."
                            )

                if tool_feedback_parts and GEMINI_AVAILABLE and genai is not None:
                    contents.append(
                        genai.types.Content(
                            role="model",
                            parts=[genai.types.Part.from_text(text=response_text)],
                        )
                    )
                    user_blob = "\n\n".join(tool_feedback_parts)
                    if stop_suffix:
                        user_blob = f"{user_blob}\n\n{stop_suffix}"
                    contents.append(
                        genai.types.Content(
                            role="user",
                            parts=[genai.types.Part.from_text(text=user_blob)],
                        )
                    )

            except Exception as e:
                iteration_error = e
                logger.error(
                    "Error in tool calling iteration",
                    error=str(e),
                    iteration=iteration + 1,
                )
                # Try to continue or break
                if iteration == 0:
                    # First iteration failed, fallback to regular generation
                    logger.warning("Tool calling failed, falling back to regular generation")
                    text = await generate_turn_text_with_stream(
                        self,
                        prompt=prompt,
                        system_prompt=system_prompt,
                        temperature=temperature,
                        max_tokens=max_tokens,
                        stream=stream,
                        on_stream_event=on_stream_event,
                        **kwargs,
                    )
                    return {
                        "text": text,
                        "tool_calls": [],
                        "iterations": 1,
                        "synthesis_status": "complete",
                        "llm_synthesis_error": None,
                    }
                break

        text_out = response_text
        synthesis_status = "complete"
        llm_synthesis_error: str | None = None
        partial_reason: str | None = None

        if tool_calls_made:
            if iteration_error is not None:
                synthesis_status = "partial"
                llm_synthesis_error = str(iteration_error)
                partial_reason = "LLM request failed after tools ran"
            elif is_tool_call_json_text(response_text):
                synthesis_status = "partial"
                partial_reason = (
                    "Tool-calling loop ended before a natural-language answer "
                    "(output still looked like a tool call, or the loop stopped early)."
                )
            elif not (response_text or "").strip():
                synthesis_status = "partial"
                partial_reason = (
                    "No final natural-language answer after tool calls (empty assistant text). "
                    "The loop may have stopped after repeated identical tool calls, or the last "
                    "model turn only requested tools."
                )

        if synthesis_status == "partial" and partial_reason:
            text_out = build_partial_synthesis_message(
                reason=partial_reason,
                error_detail=llm_synthesis_error,
                tool_calls=tool_calls_made,
            )
            logger.warning(
                "Question-driven synthesis incomplete; substituted deterministic tool summary",
                synthesis_status=synthesis_status,
                tool_calls_count=len(tool_calls_made),
            )

        result: dict[str, Any] = {
            "text": text_out,
            "tool_calls": tool_calls_made,
            "iterations": iteration + 1,
            "synthesis_status": synthesis_status,
            "llm_synthesis_error": llm_synthesis_error,
        }
        if any(usage_total.values()):
            result["llm_usage"] = dict(usage_total)
        return result
