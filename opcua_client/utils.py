"""
Utility module for OPC UA client.

This module provides utility functions for the OPC UA client.
"""

import logging
from typing import Any, Dict, List, Optional, Union

from asyncua import Client, ua

logger = logging.getLogger(__name__)


def variant_to_python(variant: ua.Variant) -> Any:
    """
    Convert an OPC UA Variant to a Python type.
    
    Args:
        variant: The OPC UA Variant to convert
        
    Returns:
        Python representation of the variant
    """
    if variant.is_array:
        return [variant_to_python(ua.Variant(v)) for v in variant.Value]
    
    # Handle scalar types
    value = variant.Value
    
    # Convert OPC UA specific types to Python types
    if isinstance(value, ua.DateTime):
        return value.to_datetime()
    if isinstance(value, ua.LocalizedText):
        return value.Text
    if isinstance(value, ua.QualifiedName):
        return value.Name
    if isinstance(value, ua.NodeId):
        return str(value)
    if isinstance(value, ua.ExtensionObject):
        return "ExtensionObject"
    
    return value


def python_to_variant(value: Any) -> ua.Variant:
    """
    Convert a Python value to an OPC UA Variant.
    
    Args:
        value: The Python value to convert
        
    Returns:
        OPC UA Variant
    """
    # Already a variant
    if isinstance(value, ua.Variant):
        return value
    
    # Handle lists/arrays
    if isinstance(value, (list, tuple)):
        return ua.Variant(value, ua.VariantType.Null)
    
    # Scalars
    return ua.Variant(value)


def setup_logging(level: int = logging.INFO) -> None:
    """
    Set up basic logging configuration.
    
    Args:
        level: The logging level to use
    """
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )


def format_node_id(namespace: int, identifier: Union[int, str]) -> str:
    """
    Format a node ID string from namespace and identifier.
    
    Args:
        namespace: The namespace index
        identifier: The identifier
        
    Returns:
        Formatted node ID string
    """
    if isinstance(identifier, int):
        return f"ns={namespace};i={identifier}"
    else:
        return f"ns={namespace};s={identifier}"


def parse_node_id(node_id_str: str) -> Dict[str, Union[int, str]]:
    """
    Parse a node ID string into its components.
    
    Args:
        node_id_str: The node ID string to parse
        
    Returns:
        Dictionary containing namespace and identifier
    """
    parts = node_id_str.split(';')
    result = {}
    
    for part in parts:
        if '=' in part:
            key, value = part.split('=', 1)
            if key == 'ns':
                result['namespace'] = int(value)
            elif key in ('i', 's', 'g', 'b'):
                result['identifier_type'] = key
                if key == 'i':
                    result['identifier'] = int(value)
                else:
                    result['identifier'] = value
    
    return result 