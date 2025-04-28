"""
OPC UA Client Python package.
"""

from opcua_client.client import OpcUaClient
from opcua_client.utils import setup_logging

__version__ = "0.1.0"
__all__ = ["OpcUaClient", "setup_logging"] 