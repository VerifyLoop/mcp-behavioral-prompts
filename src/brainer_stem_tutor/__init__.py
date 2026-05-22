"""Brainer STEM Tutor — solver + socratic tutor + vision + eval stack.

Layout:
- shared: pydantic schemas, logging, settings used by every layer
- solver: structured solver agent that verifies its own answers
- tutor: socratic agent + anti-leak moderator + follow policy
- vision: image -> bounding boxes + LaTeX pipeline
- orchestrator: in-process router that glues the three agents together
- eval: benchmark harness with simulated student and metrics
"""

__version__ = "0.1.0"
