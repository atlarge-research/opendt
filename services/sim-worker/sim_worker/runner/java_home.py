"""Java home detection utilities."""

import logging
import os
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)


def detect_java_home() -> str:
    """Detect JAVA_HOME by finding the Java installation directory.

    Returns:
        Path to Java home directory

    Raises:
        RuntimeError: If Java cannot be found
    """
    # First check if JAVA_HOME is already set
    if "JAVA_HOME" in os.environ:
        java_home = os.environ["JAVA_HOME"]
        if Path(java_home).exists():
            return java_home

    # On macOS, use /usr/libexec/java_home
    try:
        result = subprocess.run(
            ["/usr/libexec/java_home"],
            capture_output=True,
            text=True,
            check=True,
        )
        java_home = result.stdout.strip()
        if java_home and Path(java_home).exists():
            logger.debug(f"Auto-detected JAVA_HOME (macOS): {java_home}")
            return java_home
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass

    # On Linux, try readlink approach
    try:
        result = subprocess.run(
            ["readlink", "-f", "/usr/bin/java"],
            capture_output=True,
            text=True,
            check=True,
        )
        java_binary = result.stdout.strip()
        # Java home is the parent of the bin directory
        java_home = str(Path(java_binary).parent.parent)
        if java_home and Path(java_home).exists():
            logger.debug(f"Auto-detected JAVA_HOME (Linux): {java_home}")
            return java_home
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass

    # Try common Linux paths
    common_paths = [
        "/usr/lib/jvm/java-21-openjdk-arm64",
        "/usr/lib/jvm/java-21-openjdk-amd64",
        "/usr/lib/jvm/default-java",
        "/usr/lib/jvm/java-21",
    ]

    for path in common_paths:
        if Path(path).exists():
            logger.info(f"Found JAVA_HOME at: {path}")
            return path

    raise RuntimeError("Could not detect JAVA_HOME. Please set the JAVA_HOME environment variable.")
