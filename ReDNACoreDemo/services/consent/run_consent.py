"""
Consent Service - Runner

Starts the Consent Service on port 8200 (with auto-increment if occupied).
"""

import uvicorn
import logging
import socket
from pathlib import Path

logger = logging.getLogger(__name__)

# Port configuration
CONSENT_HOST = "127.0.0.1"
CONSENT_BASE_PORT = 8200
MAX_PORT_ATTEMPTS = 10


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
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.bind((CONSENT_HOST, port))
            sock.close()
            logger.info(f"Found available port: {port}")
            return port
        except OSError:
            logger.debug(f"Port {port} in use, trying next...")
            continue

    raise RuntimeError(f"Could not find available port in range {start_port}-{start_port + max_attempts - 1}")


def main():
    """Start Consent Service."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    try:
        port = find_available_port(CONSENT_BASE_PORT, MAX_PORT_ATTEMPTS)
        logger.info(f"🔒 Starting Consent Service on {CONSENT_HOST}:{port}")
        logger.info(f"📖 API docs: http://{CONSENT_HOST}:{port}/docs")

        # Log port to file for integration
        log_dir = Path(__file__).parent.parent.parent.parent / "data" / "consent"
        log_dir.mkdir(parents=True, exist_ok=True)
        port_log = log_dir / "consent_port.log"
        with open(port_log, "w") as f:
            f.write(f"{port}\n")

        uvicorn.run(
            "services.consent.api:app",
            host=CONSENT_HOST,
            port=port,
            reload=True,
            log_level="info"
        )

    except RuntimeError as e:
        logger.error(f"Failed to start Consent Service: {e}")
        exit(1)
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        exit(1)


if __name__ == "__main__":
    main()
