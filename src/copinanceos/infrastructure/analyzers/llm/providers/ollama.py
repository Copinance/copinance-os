"""Ollama local LLM provider implementation."""

import json
from typing import TYPE_CHECKING, Any

import structlog

if TYPE_CHECKING:
    import httpx  # noqa: F401

try:
    import httpx

    HTTPX_AVAILABLE = True
    HTTPStatusError: type[httpx.HTTPStatusError] | None = httpx.HTTPStatusError
except ImportError:
    HTTPX_AVAILABLE = False
    httpx = None  # type: ignore[assignment]
    HTTPStatusError = None

from copinanceos.domain.ports.tools import Tool
from copinanceos.infrastructure.analyzers.llm.providers.base import LLMProvider
from copinanceos.infrastructure.tools.tool_executor import ToolExecutor

logger = structlog.get_logger(__name__)


class OllamaProvider(LLMProvider):
    """Ollama local LLM provider implementation.

    This provider uses Ollama for running LLMs locally.
    Configure using COPINANCEOS_OLLAMA_BASE_URL and COPINANCEOS_OLLAMA_MODEL environment variables.

    Example:
        ```python
        from copinanceos.infrastructure.analyzers.llm.providers import OllamaProvider

        provider = OllamaProvider(base_url="http://localhost:11434", model_name="llama2")
        response = await provider.generate_text("Analyze this stock...")
        ```
    """

    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        model_name: str = "llama2",
        temperature: float = 0.7,
        max_output_tokens: int | None = None,
    ) -> None:
        """Initialize Ollama provider.

        Args:
            base_url: Ollama API base URL (default: "http://localhost:11434")
            model_name: Ollama model to use (default: "llama2")
            temperature: Default temperature for generation
            max_output_tokens: Default max output tokens
        """
        self._base_url = base_url.rstrip("/")
        self._model_name = model_name
        self._default_temperature = temperature
        self._default_max_output_tokens = max_output_tokens
        self._client: httpx.AsyncClient | None = None

        if HTTPX_AVAILABLE and httpx is not None:
            try:
                self._client = httpx.AsyncClient(base_url=self._base_url, timeout=300.0)
                logger.info("Initialized Ollama provider", model=model_name, base_url=base_url)
            except Exception as e:
                logger.warning("Failed to initialize Ollama client", error=str(e))
        else:
            logger.warning("httpx package is not installed, Ollama provider will not work")

    async def generate_text(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        **kwargs: Any,
    ) -> str:
        """Generate text using Ollama.

        Args:
            prompt: The user prompt/query
            system_prompt: Optional system prompt (prepended to prompt)
            temperature: Sampling temperature (uses default if not provided)
            max_tokens: Maximum tokens to generate (uses default if not provided)
            **kwargs: Additional parameters (e.g., top_p, top_k)

        Returns:
            Generated text response

        Raises:
            RuntimeError: If httpx is not available or Ollama is not configured
            Exception: If the API call fails
        """
        if not HTTPX_AVAILABLE:
            raise RuntimeError("httpx package is not installed")

        if self._client is None:
            raise RuntimeError("Ollama client is not initialized")

        # Combine system prompt and user prompt
        full_prompt = prompt
        if system_prompt:
            full_prompt = f"{system_prompt}\n\n{prompt}"

        # Prepare request payload
        payload: dict[str, Any] = {
            "model": self._model_name,
            "prompt": full_prompt,
            "stream": False,
        }

        # Set temperature
        if temperature is not None:
            payload["options"] = {"temperature": temperature}
        elif self._default_temperature is not None:
            payload["options"] = {"temperature": self._default_temperature}

        # Set max tokens (num_predict in Ollama)
        if max_tokens is not None:
            if "options" not in payload:
                payload["options"] = {}
            payload["options"]["num_predict"] = max_tokens
        elif self._default_max_output_tokens is not None:
            if "options" not in payload:
                payload["options"] = {}
            payload["options"]["num_predict"] = self._default_max_output_tokens

        # Add any additional kwargs to options
        if kwargs:
            if "options" not in payload:
                payload["options"] = {}
            payload["options"].update(kwargs)

        try:
            logger.debug(
                "Generating text with Ollama",
                model=self._model_name,
                prompt_length=len(full_prompt),
            )

            response = await self._client.post("/api/generate", json=payload)

            # Check for errors before raising status
            if response.status_code != 200:
                try:
                    error_result = response.json()
                    if "error" in error_result:
                        error_msg = error_result["error"]
                        # Check if it's a model not found error
                        if "not found" in error_msg.lower() or "model" in error_msg.lower():
                            # Try to get list of available models for better error message
                            available_models = []
                            try:
                                tags_response = await self._client.get("/api/tags")
                                if tags_response.status_code == 200:
                                    tags_data = tags_response.json()
                                    available_models = [
                                        model.get("name", "")
                                        for model in tags_data.get("models", [])
                                    ]
                            except Exception:
                                pass  # Ignore errors when fetching available models

                            models_hint = ""
                            if available_models:
                                models_hint = (
                                    f"\nAvailable models: {', '.join(available_models[:5])}"
                                )
                                if len(available_models) > 5:
                                    models_hint += f" (and {len(available_models) - 5} more)"

                            raise RuntimeError(
                                f"Ollama model '{self._model_name}' not found.{models_hint}\n"
                                f"To install this model, run: ollama pull {self._model_name}\n"
                                f"To list all available models: ollama list\n"
                                f"Ollama error: {error_msg}"
                            )
                except (json.JSONDecodeError, KeyError):
                    pass  # Fall through to raise_for_status
                except RuntimeError:
                    raise  # Re-raise RuntimeError from model not found

            response.raise_for_status()
            result = response.json()

            # Extract response text
            if "response" in result:
                return str(result["response"])
            elif "text" in result:
                return str(result["text"])
            else:
                logger.warning("Unexpected Ollama response format", response=result)
                return str(result)

        except Exception as e:
            # Check if it's an httpx error (only if httpx is available)
            if HTTPX_AVAILABLE and httpx is not None and isinstance(e, httpx.HTTPError):
                error_msg = str(e)
                # Provide helpful error messages for common issues
                if (
                    HTTPStatusError is not None
                    and isinstance(e, HTTPStatusError)
                    and e.response.status_code == 404
                ):
                    error_msg = (
                        f"Ollama API endpoint not found (404). "
                        f"This usually means:\n"
                        f"  1. Ollama is not running - start it with: ollama serve\n"
                        f"  2. The base URL is incorrect - check COPINANCEOS_OLLAMA_BASE_URL\n"
                        f"  3. The model '{self._model_name}' doesn't exist - pull it with: ollama pull {self._model_name}\n"
                        f"Original error: {str(e)}"
                    )
                logger.error(
                    "Ollama API call failed",
                    error=error_msg,
                    base_url=self._base_url,
                    model=self._model_name,
                )
                raise RuntimeError(f"Ollama API call failed: {error_msg}") from e
            logger.error("Unexpected error in Ollama provider", error=str(e))
            raise

    async def is_available(self) -> bool:
        """Check if Ollama provider is available and configured.

        Returns:
            True if Ollama is available and configured, False otherwise
        """
        if not HTTPX_AVAILABLE:
            return False

        if self._client is None:
            return False

        # Try a simple test call
        try:
            test_response = await self._client.get("/api/tags")
            test_response.raise_for_status()
            return True
        except Exception as e:
            logger.debug("Ollama availability check failed", error=str(e))
            return False

    def get_provider_name(self) -> str:
        """Get the name of the LLM provider.

        Returns:
            "ollama"
        """
        return "ollama"

    def get_model_name(self) -> str | None:
        """Get the model name being used by this provider.

        Returns:
            Model name (e.g., "llama2") or None if not configured
        """
        return self._model_name

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
        """Generate text with optional tool usage using Ollama.

        Note: Ollama's function calling support varies by model. This implementation
        uses a ReAct-style approach where the caller manages prompt content (including
        tool descriptions and instructions). The LLM generates JSON tool calls that
        are parsed and executed.

        Args:
            prompt: The user prompt/query (caller manages prompt content)
            tools: Optional list of tools available to the LLM
            system_prompt: Optional system prompt for context (caller manages prompt content)
            temperature: Sampling temperature (0.0 to 1.0)
            max_tokens: Maximum tokens to generate
            max_iterations: Maximum number of tool call iterations
            **kwargs: Additional parameters

        Returns:
            Dictionary with text, tool_calls, and iterations

        Raises:
            RuntimeError: If Ollama is not available
        """
        if not HTTPX_AVAILABLE or self._client is None:
            raise RuntimeError("Ollama client is not initialized")

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
                    "Ollama tool calling iteration",
                    iteration=iteration + 1,
                    max_iterations=max_iterations,
                )

                # Generate response with current prompt (caller manages prompt content)
                response_text = await self.generate_text(
                    prompt=current_prompt,
                    system_prompt=None,  # Caller manages system prompt in current_prompt
                    temperature=temperature,
                    max_tokens=max_tokens,
                    **kwargs,
                )

                # Try to parse tool call from response
                # Look for JSON tool call in response (support multiple formats)
                # Format 1: {"action": "tool_name", "parameters": {...}}
                # Format 2: {"tool": "tool_name", "args": {...}}

                # Helper function to extract JSON objects from text
                def extract_json_objects(text: str) -> list[dict[str, Any]]:
                    """Extract JSON objects from text, handling nested braces."""
                    objects = []
                    # Find all potential JSON object starts
                    start_positions = []
                    for i, char in enumerate(text):
                        if char == "{":
                            start_positions.append(i)

                    # Try to parse JSON starting from each {
                    for start in start_positions:
                        # Try to find matching closing brace
                        brace_count = 0
                        for i in range(start, len(text)):
                            if text[i] == "{":
                                brace_count += 1
                            elif text[i] == "}":
                                brace_count -= 1
                                if brace_count == 0:
                                    # Found complete JSON object
                                    try:
                                        json_str = text[start : i + 1]
                                        parsed = json.loads(json_str)
                                        if isinstance(parsed, dict):
                                            objects.append(parsed)
                                    except json.JSONDecodeError:
                                        pass
                                    break
                    return objects

                # Helper function to make objects JSON serializable
                def make_json_serializable(obj: Any) -> Any:
                    """Recursively convert objects to JSON-serializable format."""
                    if isinstance(obj, dict):
                        return {k: make_json_serializable(v) for k, v in obj.items()}
                    elif isinstance(obj, list):
                        return [make_json_serializable(item) for item in obj]
                    elif hasattr(obj, "model_dump"):  # Pydantic models
                        return obj.model_dump()
                    elif hasattr(obj, "__dict__"):  # Other objects with __dict__
                        return make_json_serializable(obj.__dict__)
                    elif isinstance(obj, (int, float, str, bool, type(None))):
                        return obj
                    else:
                        # Convert to string for other types (e.g., Decimal)
                        try:
                            return float(obj) if hasattr(obj, "__float__") else str(obj)
                        except (ValueError, TypeError):
                            return str(obj)

                # Extract all JSON objects from response
                json_objects = extract_json_objects(response_text)

                # Parse tool calls from response
                function_calls: list[dict[str, Any]] = []
                for obj in json_objects:
                    tool_name = obj.get("tool") or obj.get("action")
                    tool_params = obj.get("args") or obj.get("parameters")

                    if tool_name and (tool_params is not None):
                        # Validate that it's a valid tool name
                        if tool_name in executor.list_tools():
                            function_calls.append({"name": tool_name, "args": tool_params})
                            logger.debug("Found tool call in response", tool=tool_name)

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
                    # Note: make_json_serializable is defined above in this function
                    response_data = None
                    if tool_result.success and tool_result.data is not None:
                        # Serialize data, potentially truncating very large responses
                        serialized_data = make_json_serializable(tool_result.data)
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
                                make_json_serializable(tool_result.metadata)
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
                        result_data = {
                            "tool": tool_name,
                            "success": False,
                            "error": error_msg,
                        }
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
                    serializable_data = make_json_serializable(result_data)
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

            except RuntimeError as e:
                # If it's a RuntimeError from generate_text (e.g., Ollama not available),
                # provide helpful message and stop iterating
                error_msg = str(e)
                if "404" in error_msg or "not found" in error_msg.lower():
                    logger.error(
                        "Ollama service unavailable - stopping tool calling",
                        error=error_msg,
                        iteration=iteration + 1,
                        hint="Make sure Ollama is running: ollama serve",
                    )
                else:
                    logger.error(
                        "Error in tool calling iteration",
                        error=error_msg,
                        iteration=iteration + 1,
                    )
                break
            except Exception as e:
                logger.error(
                    "Error in tool calling iteration", error=str(e), iteration=iteration + 1
                )
                break

        return {
            "text": response_text,
            "tool_calls": tool_calls_made,
            "iterations": iteration + 1,
        }
