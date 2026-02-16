"""MongoDB migrations. Add new domains in registry.py."""

from pr_flow_agents.storage.migrations.registry import REGISTRY, run_all, run_collection

__all__ = ["run_all", "run_collection", "REGISTRY"]
