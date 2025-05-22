"""
Node module for OPC UA client.

This module provides functions to browse nodes and read/write node attributes.
"""

import logging
from typing import Any, Dict, List, Optional, Union, Set

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
        
        # 중복 제거를 위해 각 노드의 DisplayName과 NodeId를 추적
        unique_children = []
        seen_nodes = set()  # (display_name, nodeid) 튜플의 집합
        
        for child in children:
            # 노드 정보 가져오기
            browse_name = await child.read_browse_name()
            display_name = await child.read_display_name()
            
            # 노드 ID 처리 및 로깅
            node_id_str = str(child.nodeid)
            if len(node_id_str) > 50:
                node_id_str_display = f"{node_id_str[:30]}...{node_id_str[-10:]}"
            else:
                node_id_str_display = node_id_str
                
            logger.info(f"Node: {display_name.Text}, ID: {node_id_str_display}")
            
            # 중복 확인 (DisplayName과 NodeId 둘 다 확인)
            node_key = (display_name.Text, node_id_str)
            
            if node_key not in seen_nodes:
                seen_nodes.add(node_key)
                unique_children.append(child)
        
        return unique_children
    except Exception as e:
        # 예외 메시지 간결화
        err_msg = str(e)
        if len(err_msg) > 100:
            err_msg = f"{err_msg[:100]}... [내용 생략]"
        logger.error(f"Failed to browse node: {err_msg}")
        return []


async def browse_nodes_recursive(client: Client, node_id: Optional[Union[str, Node]] = None, max_depth: int = 1, current_depth: int = 0) -> Dict[str, Any]:
    """
    Browse nodes recursively starting from the specified node up to a maximum depth.
    
    Args:
        client: The client with an established connection
        node_id: The ID of the node to browse or Node object (None for root node)
        max_depth: Maximum recursion depth
        current_depth: Current recursion depth (for internal use)
        
    Returns:
        Dictionary containing node information in a hierarchical structure
    """
    if current_depth > max_depth:
        return {}
        
    try:
        # Get the Node object
        if node_id is None:
            node = client.nodes.root
        elif isinstance(node_id, Node):
            node = node_id
        else:
            node = client.get_node(node_id)
            
        # Get node info
        browse_name = await node.read_browse_name()
        display_name = await node.read_display_name()
        node_class = await node.read_node_class()
        
        # Create node info dictionary
        node_info = {
            "NodeId": str(node.nodeid),
            "BrowseName": browse_name.Name,
            "DisplayName": display_name.Text,
            "NodeClass": node_class.name,
            "Level": current_depth,
            "Children": []
        }
        
        # If we haven't reached max depth, get children
        if current_depth < max_depth:
            children = await node.get_children()
            for child in children:
                try:
                    # 직접 노드 객체를 전달하여 문자열 변환 문제 방지
                    child_info = await browse_nodes_recursive(
                        client, 
                        child,  # 문자열 대신 노드 객체 전달
                        max_depth, 
                        current_depth + 1
                    )
                    if child_info:  # Only add if we got valid info
                        node_info["Children"].append(child_info)
                except Exception as child_e:
                    # 자식 노드 처리 중 오류 발생 시 오류 정보를 표시하는 노드 추가
                    error_info = {
                        "NodeId": str(child.nodeid),
                        "BrowseName": "Error",
                        "DisplayName": f"Error: {str(child_e)}",
                        "NodeClass": "Unknown",
                        "Level": current_depth + 1,
                        "Children": []
                    }
                    node_info["Children"].append(error_info)
        
        return node_info
    except Exception as e:
        # 오류 발생 시 오류 정보를 포함한 노드 반환
        node_id_str = str(node_id) if not isinstance(node_id, Node) else str(node_id.nodeid)
        error_info = {
            "NodeId": node_id_str if node_id else "root",
            "BrowseName": "Error",
            "DisplayName": f"Error: {str(e)}",
            "NodeClass": "Unknown",
            "Level": current_depth,
            "Children": []
        }
        return error_info


async def get_node_info(client: Client, node_id: str) -> Dict[str, Any]:
    """
    Get detailed information about a node.
    
    Args:
        client: The client with an established connection
        node_id: The ID of the node to get information about
        
    Returns:
        Dictionary containing node information
    """
    node = client.get_node(node_id)
    try:
        info = {}
        # 기본 속성들 읽기
        info["NodeId"] = str(node.nodeid)
        
        # 주요 속성들 읽기 - 각 속성에 대해 개별 예외 처리
        try:
            browse_name = await node.read_browse_name()
            info["BrowseName"] = browse_name.Name
        except Exception as e:
            logger.debug(f"Failed to read BrowseName: {e}")
            info["BrowseName"] = None
            
        try:
            display_name = await node.read_display_name()
            info["DisplayName"] = display_name.Text
        except Exception as e:
            logger.debug(f"Failed to read DisplayName: {e}")
            info["DisplayName"] = None
            
        try:
            node_class = await node.read_node_class()
            info["NodeClass"] = node_class.name
        except Exception as e:
            logger.debug(f"Failed to read NodeClass: {e}")
            info["NodeClass"] = None
        
        try:
            description = await node.read_description()
            info["Description"] = description.Text if description.Text else None
        except Exception as e:
            logger.debug(f"Failed to read Description: {e}")
            info["Description"] = None
            
        # Value 속성 읽기 시도
        try:
            value = await node.read_value()
            info["Value"] = value
        except Exception as e:
            logger.debug(f"Failed to read Value: {e}")
            info["Value"] = None
        
        # 참조 정보 추가
        try:
            references = await node.get_references()
            info["ReferenceCount"] = len(references)
        except Exception as e:
            logger.debug(f"Failed to get references: {e}")
            info["ReferenceCount"] = None
        
        return info
    except Exception as e:
        logger.error(f"Failed to get node info: {e}")
        raise


async def get_all_node_attributes(client: Client, node_id: str) -> Dict[str, Any]:
    """
    Get all available attributes for a node.
    
    Args:
        client: The client with an established connection
        node_id: The ID of the node to get attributes for
        
    Returns:
        Dictionary containing all available node attributes
    """
    node = client.get_node(node_id)
    attributes = {}
    
    try:
        # 기본 정보 먼저 추가
        node_id_str = str(node.nodeid)
        attributes["NodeId"] = node_id_str
    except Exception as e:
        logger.debug(f"Failed to convert NodeId to string: {e}")
    
    # 표준 OPC UA 속성 목록
    attr_dict = {
        ua.AttributeIds.NodeId: "NodeId",
        ua.AttributeIds.NodeClass: "NodeClass",
        ua.AttributeIds.BrowseName: "BrowseName",
        ua.AttributeIds.DisplayName: "DisplayName",
        ua.AttributeIds.Description: "Description",
        ua.AttributeIds.WriteMask: "WriteMask",
        ua.AttributeIds.UserWriteMask: "UserWriteMask",
        ua.AttributeIds.Value: "Value",
        ua.AttributeIds.DataType: "DataType",
        ua.AttributeIds.ValueRank: "ValueRank",
        ua.AttributeIds.ArrayDimensions: "ArrayDimensions",
        ua.AttributeIds.AccessLevel: "AccessLevel",
        ua.AttributeIds.UserAccessLevel: "UserAccessLevel",
        ua.AttributeIds.MinimumSamplingInterval: "MinimumSamplingInterval",
        ua.AttributeIds.Historizing: "Historizing",
        ua.AttributeIds.Executable: "Executable",
        ua.AttributeIds.UserExecutable: "UserExecutable",
        ua.AttributeIds.EventNotifier: "EventNotifier",
        ua.AttributeIds.IsAbstract: "IsAbstract"
    }
    
    # 중요 속성 먼저 가져오기 시도 (표시 이름, 값, 데이터 타입)
    important_attrs = [
        ua.AttributeIds.BrowseName,
        ua.AttributeIds.DisplayName,
        ua.AttributeIds.Value,
        ua.AttributeIds.DataType,
        ua.AttributeIds.NodeClass
    ]
    
    for attr_id in important_attrs:
        attr_name = attr_dict.get(attr_id)
        if attr_name:
            try:
                value = await node.read_attribute(attr_id)
                if not value.Value.is_empty():
                    if attr_id == ua.AttributeIds.NodeClass:
                        attributes[attr_name] = ua.NodeClass(value.Value.Value).name
                    elif attr_id == ua.AttributeIds.BrowseName:
                        attributes[attr_name] = value.Value.Value.Name
                    elif attr_id == ua.AttributeIds.DisplayName:
                        attributes[attr_name] = value.Value.Value.Text
                    elif attr_id == ua.AttributeIds.Value:
                        attributes[attr_name] = value.Value.Value
                    elif attr_id == ua.AttributeIds.DataType:
                        attributes[attr_name] = value.Value.Value
                        # 데이터 타입 이름 직접 조회
                        try:
                            data_type_id = value.Value.Value
                            data_type_node = client.get_node(data_type_id)
                            data_type_name = await data_type_node.read_browse_name()
                            attributes["DataTypeName"] = data_type_name.Name
                        except Exception as e:
                            logger.debug(f"Failed to get DataTypeName: {e}")
            except Exception as e:
                logger.debug(f"Failed to read important attribute {attr_name}: {e}")
    
    # 각 속성 읽기 시도 (중요하지 않은 나머지 속성들)
    for attr_id, attr_name in attr_dict.items():
        # 이미 처리한 중요 속성은 건너뛰기
        if attr_id in important_attrs:
            continue
            
        try:
            value = await node.read_attribute(attr_id)
            
            # 값이 비어있지 않은 경우만 처리
            if not value.Value.is_empty():
                # 속성 타입에 따른 가공
                if attr_id == ua.AttributeIds.AccessLevel or attr_id == ua.AttributeIds.UserAccessLevel:
                    access_level = value.Value.Value
                    access_texts = []
                    if access_level & ua.AccessLevel.CurrentRead:
                        access_texts.append("Read")
                    if access_level & ua.AccessLevel.CurrentWrite:
                        access_texts.append("Write")
                    if access_level & ua.AccessLevel.HistoryRead:
                        access_texts.append("HistoryRead")
                    if access_level & ua.AccessLevel.HistoryWrite:
                        access_texts.append("HistoryWrite")
                    if access_level & ua.AccessLevel.SemanticChange:
                        access_texts.append("SemanticChange")
                    attributes[attr_name] = ", ".join(access_texts) if access_texts else "None"
                else:
                    attributes[attr_name] = value.Value.Value
        except Exception as e:
            # 속성이 지원되지 않는 경우 무시하고 다음 속성으로 이동
            logger.debug(f"Attribute {attr_name} not supported: {e}")
    
    # 추가 정보 가져오기 시도
    try:
        # 부모 노드 정보 가져오기
        try:
            references = await node.get_references(refs=ua.ObjectIds.HasTypeDefinition)
            if references:
                type_def = references[0].NodeId
                attributes["TypeDefinition"] = str(type_def)
                
                # 타입 정의 이름 가져오기
                try:
                    type_node = client.get_node(type_def)
                    type_name = await type_node.read_browse_name()
                    attributes["TypeName"] = type_name.Name
                except Exception as e:
                    logger.debug(f"Failed to get TypeName: {e}")
        except Exception as e:
            logger.debug(f"Failed to get TypeDefinition: {e}")
            
        # 참조 개수 추가
        try:
            references = await node.get_references()
            attributes["ReferenceCount"] = len(references)
        except Exception as e:
            logger.debug(f"Failed to get references: {e}")
    except Exception as e:
        logger.debug(f"Failed to get additional attributes: {e}")
    
    # 적어도 하나 이상의 속성이 없으면 빈 dict 대신 기본 정보라도 채우기
    if not attributes or len(attributes) < 3:  # 최소한의 정보가 필요
        try:
            info = await get_node_info(client, node_id)
            if info:
                for key, value in info.items():
                    if key not in attributes:
                        attributes[key] = value
        except Exception as e:
            logger.debug(f"Failed to get fallback info: {e}")
    
    return attributes


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


async def find_nodes_by_name(client: Client, name_pattern: str, start_node_id: Optional[str] = None, case_sensitive: bool = False) -> List[Node]:
    """
    Find nodes by name pattern starting from the specified node.
    
    Args:
        client: The client with an established connection
        name_pattern: The name pattern to search for
        start_node_id: The ID of the node to start search from (None for root)
        case_sensitive: Whether the search should be case-sensitive
        
    Returns:
        List of matching nodes
    """
    if not case_sensitive:
        name_pattern = name_pattern.lower()
    
    matches = []
    visited = set()
    
    async def _search_recursive(node_id):
        if node_id in visited:
            return
        
        visited.add(node_id)
        node = client.get_node(node_id)
        
        try:
            # Check if current node matches
            display_name = await node.read_display_name()
            name = display_name.Text
            
            if (case_sensitive and name_pattern in name) or (not case_sensitive and name_pattern in name.lower()):
                matches.append(node)
            
            # Search in children
            children = await node.get_children()
            for child in children:
                await _search_recursive(child.nodeid)
                
        except Exception as e:
            logger.debug(f"Error searching node {node_id}: {e}")
    
    # Start search
    start_node = client.nodes.root if start_node_id is None else client.get_node(start_node_id)
    await _search_recursive(start_node.nodeid)
    
    return matches 