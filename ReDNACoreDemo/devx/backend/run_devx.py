#!/usr/bin/env python3
"""
DevX Backend Runner
===================

Starts the DevX FastAPI server with port auto-detection.
"""

import sys
import logging
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from devx.backend.config import get_backend_port, DEVX_HOST, LOG_DIR

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(LOG_DIR / "devx_backend.log"),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)


def main():
    """Start DevX backend server."""
    import uvicorn

    # Find available port
    try:
        port = get_backend_port()
        logger.info(f"DevX backend will start on {DEVX_HOST}:{port}")

        # Log to file for CP++ to read
        with open(LOG_DIR / "devx_start.log", "w") as f:
            f.write(f"backend_port={port}\n")
            f.write(f"backend_host={DEVX_HOST}\n")

    except RuntimeError as e:
        logger.error(f"Failed to find available port: {e}")
        sys.exit(1)

    # Start server
    try:
        uvicorn.run(
            "devx.backend.api:app",
            host=DEVX_HOST,
            port=port,
            reload=True,
            log_level="info"
        )
    except Exception as e:
        logger.error(f"Failed to start DevX backend: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
