"""
Method module for OPC UA client.

This module provides functions to call methods on OPC UA servers.
"""

import logging
from typing import Any, Dict, List, Optional, Tuple, Union

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


async def get_method_info(client: Client, method_id: str) -> Dict[str, Any]:
    """
    Get detailed information about a method.
    
    Args:
        client: The client with an established connection
        method_id: The ID of the method node
        
    Returns:
        Dictionary containing method information
    """
    method_node = client.get_node(method_id)
    
    try:
        info = {}
        
        # Get basic node information
        info["NodeId"] = str(method_node.nodeid)
        
        browse_name = await method_node.read_browse_name()
        info["BrowseName"] = browse_name.Name
        
        display_name = await method_node.read_display_name()
        info["DisplayName"] = display_name.Text
        
        # 메서드 노드에 대한 참조 정보 조회
        references = await method_node.get_references(refs=ua.ObjectIds.HasProperty)
        properties = []
        
        # InputArguments, OutputArguments 속성 찾기
        input_args = None
        output_args = None
        
        for ref in references:
            if ref.BrowseName and ref.BrowseName.Name == "InputArguments":
                input_node = client.get_node(ref.NodeId)
                input_args = await input_node.read_value()
                
            if ref.BrowseName and ref.BrowseName.Name == "OutputArguments":
                output_node = client.get_node(ref.NodeId)
                output_args = await output_node.read_value()
        
        # InputArguments 정보 처리
        if input_args:
            input_info = []
            for arg in input_args:
                arg_info = {
                    "Name": arg.Name,
                    "DataType": await _get_data_type_name(client, arg.DataType),
                    "ValueRank": arg.ValueRank,
                    "Description": arg.Description.Text if arg.Description else None
                }
                input_info.append(arg_info)
            info["InputArguments"] = input_info
        else:
            info["InputArguments"] = []
            
        # OutputArguments 정보 처리
        if output_args:
            output_info = []
            for arg in output_args:
                arg_info = {
                    "Name": arg.Name,
                    "DataType": await _get_data_type_name(client, arg.DataType),
                    "ValueRank": arg.ValueRank,
                    "Description": arg.Description.Text if arg.Description else None
                }
                output_info.append(arg_info)
            info["OutputArguments"] = output_info
        else:
            info["OutputArguments"] = []
        
        # 부모 객체 찾기
        parent_refs = await method_node.get_references(direction=ua.BrowseDirection.Inverse)
        parent_objects = []
        
        for ref in parent_refs:
            if ref.NodeClass == ua.NodeClass.Object:
                parent_node = client.get_node(ref.NodeId)
                parent_name = await parent_node.read_display_name()
                parent_objects.append({
                    "NodeId": str(ref.NodeId),
                    "DisplayName": parent_name.Text
                })
                
        info["ParentObjects"] = parent_objects
        
        return info
    except Exception as e:
        logger.error(f"Failed to get method info for {method_id}: {e}")
        raise


async def _get_data_type_name(client: Client, data_type_id: ua.NodeId) -> str:
    """
    Helper function to get the name of a data type from its ID.
    
    Args:
        client: The client with an established connection
        data_type_id: The ID of the data type node
        
    Returns:
        Name of the data type
    """
    try:
        # Check if it's a standard data type
        if data_type_id.NamespaceIndex == 0:
            # Use the standard UA DataType dictionary
            for name, id_val in vars(ua.ObjectIds).items():
                if id_val == data_type_id.Identifier:
                    return name
                    
        # If not found or not a standard type, get it from the server
        type_node = client.get_node(data_type_id)
        browse_name = await type_node.read_browse_name()
        return browse_name.Name
    except Exception as e:
        logger.debug(f"Failed to get data type name: {e}")
        return f"Unknown({data_type_id})"


async def find_methods(client: Client, parent_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Find all methods under a parent node.
    
    Args:
        client: The client with an established connection
        parent_id: The ID of the parent node (None for root)
        
    Returns:
        List of dictionaries containing method information
    """
    try:
        if parent_id is None:
            # Start from Objects folder if no parent specified
            parent_id = "i=85"  # Objects folder
            
        parent_node = client.get_node(parent_id)
        
        # Get all references
        references = await parent_node.get_references()
        
        methods = []
        
        # Find method nodes
        for ref in references:
            if ref.NodeClass == ua.NodeClass.Method:
                method_node = client.get_node(ref.NodeId)
                
                # Get basic information
                display_name = await method_node.read_display_name()
                browse_name = await method_node.read_browse_name()
                
                methods.append({
                    "NodeId": str(ref.NodeId),
                    "BrowseName": browse_name.Name,
                    "DisplayName": display_name.Text,
                    "ParentId": parent_id
                })
                
        # Get methods from child objects recursively
        for ref in references:
            if ref.NodeClass == ua.NodeClass.Object:
                try:
                    child_methods = await find_methods(client, str(ref.NodeId))
                    methods.extend(child_methods)
                except Exception as e:
                    logger.debug(f"Failed to get methods from child node {ref.NodeId}: {e}")
        
        return methods
    except Exception as e:
        logger.error(f"Failed to find methods under {parent_id}: {e}")
        return []


async def call_method_with_typed_params(
    client: Client,
    object_id: str,
    method_id: str,
    input_values: List[Any]
) -> List[Any]:
    """
    Call a method with automatic type conversion based on method definition.
    
    Args:
        client: The client with an established connection
        object_id: The ID of the object node that contains the method
        method_id: The ID of the method node to call
        input_values: List of input values (will be automatically converted)
        
    Returns:
        List of output values with proper types
    """
    try:
        # Get method information
        method_info = await get_method_info(client, method_id)
        input_args_info = method_info.get("InputArguments", [])
        
        # Check if number of provided arguments matches
        if len(input_values) != len(input_args_info):
            raise ValueError(f"Expected {len(input_args_info)} arguments, got {len(input_values)}")
        
        # Convert input values to appropriate types
        converted_args = []
        
        for i, (value, arg_info) in enumerate(zip(input_values, input_args_info)):
            data_type = arg_info.get("DataType", "")
            
            # Convert value based on data type
            converted_value = value
            
            # Handle common data types
            if "Boolean" in data_type and not isinstance(value, bool):
                if isinstance(value, str):
                    converted_value = value.lower() in ("true", "yes", "1", "y")
                else:
                    converted_value = bool(value)
                    
            elif "Int" in data_type and not isinstance(value, int):
                converted_value = int(value)
                
            elif "Double" in data_type or "Float" in data_type and not isinstance(value, float):
                converted_value = float(value)
                
            elif "String" in data_type and not isinstance(value, str):
                converted_value = str(value)
            
            converted_args.append(converted_value)
        
        # Call the method with converted arguments
        result = await call_method_with_params(client, object_id, method_id, converted_args)
        
        # Format output if a tuple/list is returned
        if isinstance(result, (list, tuple)):
            output_args_info = method_info.get("OutputArguments", [])
            
            # If we have output argument info and matching count, use it to format results
            if output_args_info and len(output_args_info) == len(result):
                formatted_result = []
                for value, arg_info in zip(result, output_args_info):
                    formatted_result.append({
                        "Name": arg_info.get("Name", ""),
                        "Value": value,
                        "DataType": arg_info.get("DataType", "")
                    })
                return formatted_result
        
        return result
    except Exception as e:
        logger.error(f"Failed to call method with typed parameters: {e}")
        raise 