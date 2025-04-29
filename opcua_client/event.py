"""
Event module for OPC UA client.

This module provides functions to handle events and monitored items.
"""

import logging
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

from asyncua import Client, ua
from asyncua.common.node import Node
from asyncua.common.subscription import Subscription

logger = logging.getLogger(__name__)


async def subscribe_events(
    subscription: Subscription,
    node_id: str,
    callback: Callable[[Any], None],
    event_filter: Optional[ua.EventFilter] = None
) -> int:
    """
    Subscribe to events from a specific node.
    
    Args:
        subscription: The subscription to use
        node_id: The ID of the node to subscribe to
        callback: The callback function to be called when an event is received
        event_filter: Optional event filter to use
        
    Returns:
        Handle ID for the monitored item
    """
    # 노드 객체 획득 방법 개선
    node = None
    if hasattr(subscription.server, 'get_node'):
        node = subscription.server.get_node(node_id)
    elif hasattr(subscription, '_client'):
        node = subscription._client.get_node(node_id)
    else:
        # 대체 방법 시도
        from asyncua import ua
        node_id_obj = ua.NodeId.from_string(node_id)
        node = Node(subscription.server, node_id_obj)
    
    if event_filter is None:
        # Create a default event filter that includes standard fields
        event_filter = await _create_default_event_filter(subscription.server)
    
    try:
        handle = await subscription.subscribe_events(node, callback, event_filter)
        # 로그에는 간결한 정보만 기록
        node_id_str = str(node_id)
        if len(node_id_str) > 50:
            node_id_str = f"{node_id_str[:30]}...{node_id_str[-10:]}"
        logger.info(f"Subscribed to events for node {node_id_str}")
        return handle
    except Exception as e:
        # 예외 메시지 간결화
        err_msg = str(e)
        if len(err_msg) > 100:
            err_msg = f"{err_msg[:100]}... [내용 생략]"
        logger.error(f"Failed to subscribe to events: {err_msg}")
        raise


async def _create_default_event_filter(client: Client) -> ua.EventFilter:
    """
    Create a default event filter with standard fields.
    
    Args:
        client: The client with an established connection
        
    Returns:
        EventFilter object
    """
    event_filter = ua.EventFilter()
    
    # Add select clauses for standard fields (simplified for brevity)
    for name in ["EventId", "EventType", "SourceNode", "SourceName", 
                 "Time", "ReceiveTime", "Message", "Severity"]:
        clause = ua.SimpleAttributeOperand()
        clause.TypeDefinitionId = ua.NodeId(ua.ObjectIds.BaseEventType)
        clause.BrowsePath.append(ua.QualifiedName(name, 0))
        clause.AttributeId = ua.AttributeIds.Value
        event_filter.SelectClauses.append(clause)
    
    return event_filter


async def add_monitored_item(
    subscription: Subscription,
    node_id: str,
    callback: Callable[[Node, Any, Any], None],
    sampling_interval: float = 100,
    queuesize: int = 1
) -> int:
    """
    Add a monitored item to a subscription.
    
    Args:
        subscription: The subscription to use
        node_id: The ID of the node to monitor
        callback: The callback function to be called when the data changes
        sampling_interval: The sampling interval in milliseconds
        queuesize: The queue size for the monitored item
        
    Returns:
        Handle ID for the monitored item
    """
    # 노드 객체 획득 방법 개선
    node = None
    if hasattr(subscription.server, 'get_node'):
        node = subscription.server.get_node(node_id)
    elif hasattr(subscription, '_client'):
        node = subscription._client.get_node(node_id)
    else:
        # 대체 방법 시도
        from asyncua import ua
        node_id_obj = ua.NodeId.from_string(node_id)
        node = Node(subscription.server, node_id_obj)
    
    try:
        handle = await subscription.subscribe_data_change(
            node, 
            callback,
            sampling_interval=sampling_interval,
            queuesize=queuesize
        )
        logger.info(f"Added monitored item for node {node_id}")
        return handle
    except Exception as e:
        logger.error(f"Failed to add monitored item: {e}")
        raise


async def modify_monitored_item(
    subscription: Subscription,
    handle: int,
    sampling_interval: float,
    queuesize: int = 1
) -> None:
    """
    Modify an existing monitored item.
    
    Args:
        subscription: The subscription containing the monitored item
        handle: The handle ID of the monitored item
        sampling_interval: The new sampling interval in milliseconds
        queuesize: The new queue size for the monitored item
    """
    try:
        await subscription.modify_monitored_item(
            handle,
            sampling_interval=sampling_interval,
            queuesize=queuesize
        )
        logger.info(f"Modified monitored item with handle {handle}")
    except Exception as e:
        logger.error(f"Failed to modify monitored item: {e}")
        raise


async def delete_monitored_item(subscription: Subscription, handle: int) -> None:
    """
    Delete an existing monitored item.
    
    Args:
        subscription: The subscription containing the monitored item
        handle: The handle ID of the monitored item
    """
    try:
        await subscription.unsubscribe(handle)
        logger.info(f"Deleted monitored item with handle {handle}")
    except Exception as e:
        logger.error(f"Failed to delete monitored item: {e}")
        raise


async def set_monitoring_mode(
    subscription: Subscription,
    handle: int,
    monitoring_mode: ua.MonitoringMode
) -> None:
    """
    Set the monitoring mode of an existing monitored item.
    
    Args:
        subscription: The subscription containing the monitored item
        handle: The handle ID of the monitored item
        monitoring_mode: The new monitoring mode
    """
    try:
        await subscription.set_monitoring_mode(handle, monitoring_mode)
        logger.info(f"Set monitoring mode to {monitoring_mode} for item with handle {handle}")
    except Exception as e:
        logger.error(f"Failed to set monitoring mode: {e}")
        raise 