"""
Method module for OPC UA client.

This module provides functions to call methods on OPC UA servers.
"""

import logging
from typing import Any, List, Optional, Tuple, Union

from asyncua import Client, ua
from asyncua.common.node import Node

logger = logging.getLogger(__name__)


async def call_method(client: Client, object_id: str, method_id: str) -> Any:
    """
    Call a method without input or output parameters.
    
    Args:
        client: The client with an established connection
        object_id: The ID of the object node that contains the method
        method_id: The ID of the method node to call
        
    Returns:
        Result of the method call
    """
    parent_node = client.get_node(object_id)
    method_node = client.get_node(method_id)
    
    try:
        result = await parent_node.call_method(method_node)
        logger.info(f"Method {method_id} called successfully")
        return result
    except Exception as e:
        logger.error(f"Failed to call method {method_id}: {e}")
        raise


async def call_method_with_params(
    client: Client, 
    object_id: str, 
    method_id: str, 
    input_args: List[Any]
) -> Any:
    """
    Call a method with input parameters and return output parameters.
    
    Args:
        client: The client with an established connection
        object_id: The ID of the object node that contains the method
        method_id: The ID of the method node to call
        input_args: List of input arguments for the method
        
    Returns:
        Result of the method call (typically a list of output arguments)
    """
    parent_node = client.get_node(object_id)
    method_node = client.get_node(method_id)
    
    try:
        # Convert Python types to OPC UA Variants if necessary
        ua_input_args = []
        for arg in input_args:
            if not isinstance(arg, ua.Variant):
                arg = ua.Variant(arg)
            ua_input_args.append(arg)
            
        result = await parent_node.call_method(method_node, *ua_input_args)
        logger.info(f"Method {method_id} called successfully with parameters")
        return result
    except Exception as e:
        logger.error(f"Failed to call method {method_id} with parameters: {e}")
        raise 