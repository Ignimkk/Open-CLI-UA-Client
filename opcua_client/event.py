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
    node = subscription.server.get_node(node_id)
    
    if event_filter is None:
        # Create a default event filter that includes standard fields
        event_filter = await _create_default_event_filter(subscription.server)
    
    try:
        handle = await subscription.subscribe_events(node, callback, event_filter)
        logger.info(f"Subscribed to events for node {node_id}")
        return handle
    except Exception as e:
        logger.error(f"Failed to subscribe to events: {e}")
        raise


async def _create_default_event_filter(server: Client) -> ua.EventFilter:
    """
    Create a default event filter that includes common event fields.
    
    Args:
        server: The OPC UA server client
        
    Returns:
        Event filter object
    """
    event_filter = ua.EventFilter()
    
    # Add common event fields
    for name in [
        "EventId", "EventType", "SourceNode", "SourceName",
        "Time", "ReceiveTime", "Message", "Severity"
    ]:
        op = ua.SimpleAttributeOperand()
        op.TypeDefinitionId = ua.NodeId(ua.ObjectIds.BaseEventType)
        op.BrowsePath = [ua.QualifiedName(name, 0)]
        op.AttributeId = ua.AttributeIds.Value
        event_filter.SelectClauses.append(op)
    
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
    node = subscription.server.get_node(node_id)
    
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