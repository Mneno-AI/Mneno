"""CLI integration template installation helpers."""

from mneno.cli.integrations.installer import (
    ExistingTargetError,
    InstallationPlan,
    install_agent_template,
    plan_agent_installation,
)
from mneno.cli.integrations.templates import SUPPORTED_AGENTS

__all__ = [
    "SUPPORTED_AGENTS",
    "ExistingTargetError",
    "InstallationPlan",
    "install_agent_template",
    "plan_agent_installation",
]
