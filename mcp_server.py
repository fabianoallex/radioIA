"""
RadioIA MCP Server
Expoe ferramentas para que agentes de IA gerem e gerenciem episodios de radio.
"""

import os
import sys

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(PROJECT_DIR)
sys.path.insert(0, PROJECT_DIR)

from dotenv import load_dotenv
load_dotenv(os.path.join(PROJECT_DIR, '.env'))

import nest_asyncio
nest_asyncio.apply()

from mcp_tools._instance import mcp

# Importar módulos de ferramentas — cada import registra as tools no mcp
import mcp_tools.content   # noqa: F401
import mcp_tools.config    # noqa: F401
import mcp_tools.system    # noqa: F401
import mcp_tools.spots     # noqa: F401
import mcp_tools.media     # noqa: F401
import mcp_tools.context   # noqa: F401
import mcp_tools.exports   # noqa: F401
# Resources de leitura — expostos como dados, sem consumir tokens de ferramentas
import mcp_tools.resources  # noqa: F401

if __name__ == '__main__':
    mcp.run()
