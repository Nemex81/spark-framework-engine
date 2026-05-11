"""Fixture condivise per la suite pytest di spark-framework-engine."""
from __future__ import annotations

import asyncio
import sys
from unittest.mock import MagicMock

import pytest

# Stub MCP modules a collection-time: deve precedere l'import dell'engine
# nei test file (exec_module avviene a livello modulo in ogni test file).
for _mod in ("mcp", "mcp.server", "mcp.server.fastmcp"):
    sys.modules.setdefault(_mod, MagicMock())


@pytest.fixture(scope="session", autouse=True)
def stub_mcp_modules() -> None:
    """Stub MagicMock per mcp/mcp.server/mcp.server.fastmcp — applicato a collection time.

    Gli stub sono già attivi a livello di modulo sopra; questa fixture
    garantisce il contratto di sessione e funge da documentazione.
    """


@pytest.hookimpl(tryfirst=True)
def pytest_pyfunc_call(pyfuncitem: pytest.Function) -> bool | None:
    """Esegue ``async def test_*`` via ``asyncio.run()`` senza pytest-asyncio.

    Intercetta le funzioni di test asincrone e le avvolge in ``asyncio.run()``,
    restituendo ``True`` per segnalare a pytest che l'esecuzione è completata.
    Le funzioni sincrone non vengono toccate (ritorna ``None``).
    """
    if not asyncio.iscoroutinefunction(pyfuncitem.function):
        return None
    funcargs = pyfuncitem.funcargs
    argnames = pyfuncitem._fixtureinfo.argnames  # type: ignore[attr-defined]
    testargs = {arg: funcargs[arg] for arg in argnames if arg in funcargs}
    asyncio.run(pyfuncitem.obj(**testargs))
    return True
