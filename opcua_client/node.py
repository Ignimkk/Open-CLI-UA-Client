"""
Node module for OPC UA client.

This module provides functions to browse nodes and read/write node attributes.
"""

import logging
from typing import Any, Dict, List, Optional, Union

from asyncua import Client, ua
from asyncua.common.node import Node

logger = logging.getLogger(__name__)


async def browse_node(client: Client, node_id: Optional[str] = None) -> List[Node]:
    """
    Browse a single node and return its children.
    
    Args:
        client: The client with an established connection
        node_id: The ID of the node to browse (None for root node)
        
    Returns:
        List of child nodes
    """
    if node_id is None:
        node = client.nodes.root
    else:
        node = client.get_node(node_id)
    
    try:
        children = await node.get_children()
        for child in children:
            name = await child.read_browse_name()
            logger.info(f"Node: {name}, ID: {child.nodeid}")
        return children
    except Exception as e:
        logger.error(f"Failed to browse node: {e}")
        return []


async def read_node_attribute(client: Client, node_id: str, attribute: ua.AttributeIds = ua.AttributeIds.Value) -> Any:
    """
    Read an attribute from a node.
    
    Args:
        client: The client with an established connection
        node_id: The ID of the node to read from
        attribute: The attribute to read (default: Value)
        
    Returns:
        The value of the attribute
    """
    node = client.get_node(node_id)
    try:
        value = await node.read_attribute(attribute)
        return value.Value.Value
    except Exception as e:
        logger.error(f"Failed to read node attribute: {e}")
        raise


async def read_array_node_attribute(client: Client, node_id: str) -> List[Any]:
    """
    Read an array attribute from a node.
    
    Args:
        client: The client with an established connection
        node_id: The ID of the node to read from
        
    Returns:
        List of values
    """
    node = client.get_node(node_id)
    try:
        value = await node.read_value()
        if not isinstance(value, list):
            raise TypeError(f"Node does not contain an array. Actual type: {type(value)}")
        return value
    except Exception as e:
        logger.error(f"Failed to read array node attribute: {e}")
        raise


async def write_node_attribute(
    client: Client, 
    node_id: str, 
    value: Any, 
    attribute: ua.AttributeIds = ua.AttributeIds.Value
) -> None:
    """
    Write a value to a node attribute.
    
    Args:
        client: The client with an established connection
        node_id: The ID of the node to write to
        value: The value to write
        attribute: The attribute to write to (default: Value)
    """
    node = client.get_node(node_id)
    try:
        await node.write_attribute(attribute, ua.DataValue(ua.Variant(value)))
        logger.info(f"Successfully wrote value to node {node_id}")
    except Exception as e:
        logger.error(f"Failed to write node attribute: {e}")
        raise 