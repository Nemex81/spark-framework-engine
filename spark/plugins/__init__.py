"""Package spark.plugins — Plugin Manager per workspace Universo B.

Espone esclusivamente ``PluginManagerFacade`` come API pubblica
del package verso il server MCP e i tool di installazione/rimozione plugin.
"""
from __future__ import annotations

from spark.plugins.facade import PluginManagerFacade

__all__ = ["PluginManagerFacade"]
