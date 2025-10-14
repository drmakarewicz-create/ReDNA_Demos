"""
DevX Configuration
==================

Port safety and service isolation settings.
"""

import socket
from pathlib import Path

# Base ports (auto-increment if unavailable)
DEVX_BACKEND_PORT = 8100
DEVX_FRONTEND_PORT = 3100
DEVX_HOST = "127.0.0.1"

# Paths
DEVX_ROOT = Path(__file__).parent.parent
BACKEND_ROOT = DEVX_ROOT / "backend"
FRONTEND_ROOT = DEVX_ROOT / "frontend"
PROJECT_ROOT = DEVX_ROOT.parent

# Registry paths
REGISTRY_PATH = PROJECT_ROOT / "core" / "ontology" / "dna_registry.json"
SCHEMA_PATH = PROJECT_ROOT / "schemas" / "dna_registry.schema.json"

# Change request storage
CR_DIR = PROJECT_ROOT / "data" / "devx" / "change_requests"
CR_DIR.mkdir(parents=True, exist_ok=True)

# Logs
LOG_DIR = DEVX_ROOT / "logs"
LOG_DIR.mkdir(exist_ok=True)


def find_available_port(start_port: int, max_attempts: int = 10) -> int:
    """
    Find an available port starting from start_port.

    Args:
        start_port: Starting port number
        max_attempts: Maximum number of ports to try

    Returns:
        Available port number

    Raises:
        RuntimeError: If no available port found
    """
    for offset in range(max_attempts):
        port = start_port + offset
        try:
            # Try to bind to the port
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.bind((DEVX_HOST, port))
            sock.close()
            return port
        except OSError:
            continue

    raise RuntimeError(
        f"Could not find available port in range {start_port}-{start_port + max_attempts - 1}"
    )


def get_backend_port() -> int:
    """Get available backend port."""
    return find_available_port(DEVX_BACKEND_PORT)


def get_frontend_port() -> int:
    """Get available frontend port."""
    return find_available_port(DEVX_FRONTEND_PORT)
