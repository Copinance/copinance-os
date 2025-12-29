"""Google Gemini LLM provider implementation."""

import asyncio
import json
import re
from decimal import Decimal
from typing import Any, cast

import structlog

try:
    import google.genai as genai

    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False
    genai = None  # type: ignore[assignment]

from copinanceos.domain.ports.tools import Tool
from copinanceos.infrastructure.analyzers.llm.providers.base import LLMProvider
from copinanceos.infrastructure.tools.tool_executor import ToolExecutor

logger = structlog.get_logger(__name__)


class GeminiProvider(LLMProvider):
    """Google Gemini LLM provider implementation.

    This provider uses Google's Gemini API for text generation.
    Configure using the COPINANCEOS_GEMINI_API_KEY environment variable.

    Example:
        ```python
        from copinanceos.infrastructure.analyzers.llm.providers import GeminiProvider

        provider = GeminiProvider(api_key="your-api-key")
        response = await provider.generate_text("Analyze this stock...")
        ```
    """

    def __init__(
        self,
        api_key: str | None = None,
        model_name: str = "gemini-1.5-pro",
        temperature: float = 0.7,
        max_output_tokens: int | None = None,
    ) -> None:
        """Initialize Gemini provider.

        Args:
            api_key: Gemini API key. If not provided, will try to get from environment.
            model_name: Gemini model to use (default: "gemini-1.5-pro")
                       Options: gemini-2.5-flash, gemini-1.5-pro, gemini-1.5-flash, gemini-pro
                       All support function calling for agentic workflows
            temperature: Default temperature for generation
            max_output_tokens: Default max output tokens
        """
        self._api_key = api_key
        self._model_name = model_name
        self._default_temperature = temperature
        self._default_max_output_tokens = max_output_tokens
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

    def _call_gemini_api(self, prompt: str, config: dict[str, Any] | None = None) -> Any:
        """Call Gemini API with the given prompt and config.

        Args:
            prompt: The prompt to send
            config: Optional generation config

        Returns:
            Gemini API response
        """
        loop = asyncio.get_event_loop()

        def _generate() -> Any:
            if config:
                try:
                    gen_config = genai.types.GenerateContentConfig(**config)
                    return self._client.models.generate_content(
                        model=self._model_name,
                        contents=prompt,
                        config=gen_config,
                    )
                except (AttributeError, TypeError):
                    # Fallback to dict config
                    return self._client.models.generate_content(
                        model=self._model_name,
                        contents=prompt,
                        config=config,
                    )
            else:
                return self._client.models.generate_content(
                    model=self._model_name,
                    contents=prompt,
                )

        return loop.run_in_executor(None, _generate)

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
            text = await self.generate_text(
                prompt=prompt,
                system_prompt=system_prompt,
                temperature=temperature,
                max_tokens=max_tokens,
                **kwargs,
            )
            return {
                "text": text,
                "tool_calls": [],
                "iterations": 1,
            }

        # Create tool executor
        executor = ToolExecutor(tools)

        # Combine prompts (caller manages prompt content)
        full_prompt = prompt
        if system_prompt:
            full_prompt = f"{system_prompt}\n\n{prompt}"

        # Prepare config
        config = self._build_generation_config(temperature, max_tokens, **kwargs)

        # Multi-turn conversation with tool calling
        tool_calls_made: list[dict[str, Any]] = []
        current_prompt = full_prompt
        response_text = ""
        # Track recent tool calls for loop detection
        recent_tool_calls: list[tuple[str, tuple[tuple[str, Any], ...]]] = []
        max_recent_history = 3  # Check last 3 calls for loops

        for iteration in range(max_iterations):
            try:
                logger.debug(
                    "Gemini tool calling iteration",
                    iteration=iteration + 1,
                    max_iterations=max_iterations,
                )

                # Generate response with current prompt (caller manages prompt content)
                response = await self._call_gemini_api(current_prompt, config)
                response_text = self._extract_response_text(response)

                # Parse tool calls from response
                function_calls = self._parse_tool_calls_from_response(response_text, executor)

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

                # Execute function calls
                for func_call in function_calls:
                    tool_name = func_call["name"]
                    tool_args = func_call.get("args", {})

                    logger.info("Executing tool", tool_name=tool_name, args=tool_args)
                    tool_result = await executor.execute_tool(tool_name, **tool_args)

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
                        if tool_result.data is None:
                            is_empty_result = True
                        elif tool_result.data == [] or tool_result.data == {}:
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
                                    "Please use the correct stock symbol from the original question. "
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

                    # Append tool result to prompt in generic JSON format
                    # Caller is responsible for prompt structure and formatting
                    serializable_data = self._make_json_serializable(result_data)
                    tool_result_json = json.dumps(serializable_data, indent=2)
                    current_prompt = (
                        f"{current_prompt}\n\nTool execution result:\n{tool_result_json}"
                    )

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
                            stop_message = (
                                "IMPORTANT: Stop making tool calls now. "
                                "The tool returned empty results or was called with invalid parameters. "
                                "Provide your final answer based on any data you have received, "
                                "or explain that you cannot answer the question with the available tools."
                            )
                            current_prompt = f"{current_prompt}\n\n{stop_message}"

            except Exception as e:
                logger.error(
                    "Error in tool calling iteration",
                    error=str(e),
                    iteration=iteration + 1,
                )
                # Try to continue or break
                if iteration == 0:
                    # First iteration failed, fallback to regular generation
                    logger.warning("Tool calling failed, falling back to regular generation")
                    text = await self.generate_text(
                        prompt=prompt,
                        system_prompt=system_prompt,
                        temperature=temperature,
                        max_tokens=max_tokens,
                        **kwargs,
                    )
                    return {
                        "text": text,
                        "tool_calls": [],
                        "iterations": 1,
                    }
                break

        return {
            "text": response_text,
            "tool_calls": tool_calls_made,
            "iterations": iteration + 1,
        }
