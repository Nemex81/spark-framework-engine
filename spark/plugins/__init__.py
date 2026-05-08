"""Package spark.plugins — Plugin Manager per workspace Universo B.

Espone ``PluginManagerFacade`` come API pubblica verso il server MCP e i
tool di installazione/rimozione plugin via store (Universo A).

Espone inoltre ``PluginManager``, ``download_plugin`` e
``list_available_plugins`` per il download diretto senza store (TASK-3,
Dual-Mode Architecture v1.0).
"""
from __future__ import annotations

from spark.plugins.facade import PluginManagerFacade
from spark.plugins.manager import PluginManager, download_plugin, list_available_plugins

__all__ = [
    "PluginManagerFacade",
    "PluginManager",
    "download_plugin",
    "list_available_plugins",
]
