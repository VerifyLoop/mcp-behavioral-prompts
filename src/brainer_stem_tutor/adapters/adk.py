"""Google ADK adapter scaffolding (2026 pattern).

ADK 2026 wraps StdioServerParameters inside StdioConnectionParams to gain
timeout + lifecycle control. We expose a single factory that builds an
LlmAgent ready to talk to the same MCP tool servers we ship under
`brainer_stem_tutor.solver.mcp_tools`.

The factory imports `google.adk` LAZILY so the package keeps working in
environments without ADK installed (tests, slim deploys). Trying to call
the factory without ADK on the path raises ImportError with a clear hint.

References:
- https://google.github.io/adk-docs/tools-custom/mcp-tools/
- https://github.com/google/adk-python (2026 layout)
"""
from __future__ import annotations


def build_adk_solver_agent_stub(
    *,
    model: str = "gemini-2.5-flash",
    python_interpreter_args: list[str] | None = None,
    timeout_seconds: int = 30,
):
    """Return an ADK `LlmAgent` wired with the MCP Python interpreter tool.

    This is the SCAFFOLD: the integration test in
    tests/adapters/test_adk_stub.py asserts the function raises a clear
    ImportError when ADK is not installed, and lays out what a real call
    would look like so a future developer can swap the stub for the real
    `from google.adk.agents import LlmAgent` block without changing the
    surrounding code.
    """
    try:
        from google.adk.agents import LlmAgent  # type: ignore
        from google.adk.tools.mcp_tool import McpToolset  # type: ignore
        from google.adk.tools.mcp_tool.mcp_session_manager import (  # type: ignore
            StdioConnectionParams,
        )
        from mcp import StdioServerParameters  # type: ignore
    except ImportError as exc:  # pragma: no cover - exercised in test
        raise ImportError(
            "Google ADK is not installed in this environment. "
            "Install with `pip install google-adk` to enable the real "
            "Gemini-backed solver. The adapter is structured so swapping "
            "from mocks to ADK requires no changes to call sites."
        ) from exc

    args = python_interpreter_args or ["mcp-python-interpreter"]
    toolset = McpToolset(
        connection_params=StdioConnectionParams(
            server_params=StdioServerParameters(command="uvx", args=args),
            timeout=timeout_seconds,
        )
    )
    return LlmAgent(
        name="brainer_stem_solver",
        model=model,
        tools=[toolset],
    )
