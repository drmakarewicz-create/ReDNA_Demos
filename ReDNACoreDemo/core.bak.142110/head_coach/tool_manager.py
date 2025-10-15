"""
Head Coach Tool Manager (Evergreen 1 scaffold).

Loads tool definitions from the registry, exposes light-weight accessors, and
records activation telemetry when tools are invoked.
"""

from __future__ import annotations

import importlib
import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

REGISTRY_PATH = Path(__file__).with_name("tool_registry.json")


@dataclass
class ToolDefinition:
    tool_id: str
    name: str
    description: str
    category: str
    status: str
    module: str
    class_name: str
    capabilities: List[str]
    integration_points: Dict[str, Any]


class ToolManager:
    def __init__(self, registry_path: Optional[Path] = None):
        self.registry_path = registry_path or REGISTRY_PATH
        self._registry = self._load_registry()
        self._instances: Dict[str, Any] = {}

    def list_tools(self, status: Optional[str] = "active") -> List[ToolDefinition]:
        tools = [
            ToolDefinition(
                tool_id=entry["tool_id"],
                name=entry["name"],
                description=entry.get("description", ""),
                category=entry.get("category", "general"),
                status=entry.get("status", "inactive"),
                module=entry["module"],
                class_name=entry["class"],
                capabilities=list(entry.get("capabilities", [])),
                integration_points=dict(entry.get("integration_points", {})),
            )
            for entry in self._registry.get("tools", [])
        ]
        if status is not None:
            tools = [tool for tool in tools if tool.status == status]
        return tools

    def get_tool(self, tool_id: str, *, user_id: Optional[str] = None) -> Any:
        if tool_id in self._instances:
            return self._instances[tool_id]

        entry = next(
            (item for item in self._registry.get("tools", []) if item["tool_id"] == tool_id),
            None,
        )
        if entry is None:
            raise KeyError(f"Tool {tool_id} not found in registry")

        module_name = entry["module"]
        class_name = entry["class"]

        module = importlib.import_module(module_name)
        cls = getattr(module, class_name)
        instance = cls(user_id=user_id or "anonymous")
        self._instances[tool_id] = instance
        return instance

    def _load_registry(self) -> Dict[str, Any]:
        if not self.registry_path.exists():
            logger.warning("Tool registry missing at %s", self.registry_path)
            return {"tools": []}
        try:
            return json.loads(self.registry_path.read_text())
        except Exception as exc:
            logger.error("Failed to read tool registry: %s", exc)
            return {"tools": []}


_TOOL_MANAGER: Optional[ToolManager] = None


def get_tool_manager() -> ToolManager:
    global _TOOL_MANAGER
    if _TOOL_MANAGER is None:
        _TOOL_MANAGER = ToolManager()
    return _TOOL_MANAGER


__all__ = ["ToolManager", "ToolDefinition", "get_tool_manager"]
