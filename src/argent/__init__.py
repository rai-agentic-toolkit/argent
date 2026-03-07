"""Argent — Agentic Runtime Gateway.

Deterministic, middleware-driven execution wrapper for AI agents.

Public API surface — import all core types directly from ``argent``:

    from argent import Pipeline, AgentContext, RequestBudget, SqlAstValidator

"""

# Pipeline — Epic 1
# Budget — Epic 3
from argent.budget.budget import RequestBudget
from argent.budget.exceptions import BudgetExhaustedError, ToolRecursionError, ToolTimeoutError
from argent.budget.executor import ToolExecutor

# Ingress — Epic 2
from argent.ingress.exceptions import NestingDepthError, PayloadTooLargeError
from argent.ingress.parser import SinglePassParser
from argent.ingress.validators import ByteSizeValidator, DepthLimitValidator
from argent.pipeline.context import AgentContext, ExecutionState
from argent.pipeline.pipeline import Pipeline, SecurityValidator
from argent.pipeline.telemetry import Telemetry

# Security — Epic 5
from argent.security.exceptions import SecurityViolationError
from argent.security.sql_validator import SqlAstValidator

# Trimmer — Epic 4
from argent.trimmer.base import Trimmer
from argent.trimmer.calculator import ContextBudgetCalculator
from argent.trimmer.json_trimmer import JsonArrayTrimmer, JsonDictTrimmer
from argent.trimmer.markdown import MarkdownTableTrimmer
from argent.trimmer.traceback import PythonTracebackTrimmer

__version__ = "0.1.0"

__all__ = [
    "AgentContext",
    "BudgetExhaustedError",
    "ByteSizeValidator",
    "ContextBudgetCalculator",
    "DepthLimitValidator",
    "ExecutionState",
    "JsonArrayTrimmer",
    "JsonDictTrimmer",
    "MarkdownTableTrimmer",
    "NestingDepthError",
    "PayloadTooLargeError",
    "Pipeline",
    "PythonTracebackTrimmer",
    "RequestBudget",
    "SecurityValidator",
    "SecurityViolationError",
    "SinglePassParser",
    "SqlAstValidator",
    "Telemetry",
    "ToolExecutor",
    "ToolRecursionError",
    "ToolTimeoutError",
    "Trimmer",
]
