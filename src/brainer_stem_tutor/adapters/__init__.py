"""Real-LLM adapter scaffolding.

These adapters implement the *Protocol* shape that the in-process agents
already expect (SolverProtocol, TutorLLMProtocol, VisionLLMProtocol) so the
orchestrator works with either a mock or a real LLM by dependency injection
alone. They do NOT import `google-genai` / `google-adk` at module import
time so the rest of the package stays lightweight; the import is deferred
inside the constructor and the test suite skips them when the SDK is absent.
"""

from .gemini import GeminiSolverLLM, GeminiTutorLLM, GeminiVisionLLM
from .adk import build_adk_solver_agent_stub

__all__ = [
    "GeminiSolverLLM",
    "GeminiTutorLLM",
    "GeminiVisionLLM",
    "build_adk_solver_agent_stub",
]
