"""
Subscription module for OPC UA client.

This module provides functions to manage subscriptions for data changes.
"""

import asyncio
import logging
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

from asyncua import Client, ua
from asyncua.common.node import Node
from asyncua.common.subscription import Subscription

logger = logging.getLogger(__name__)


async def create_subscription(client: Client, period: float = 500) -> Subscription:
    """
    Create an empty subscription.
    
    Args:
        client: The client with an established connection
        period: The publishing interval in milliseconds
        
    Returns:
        Subscription object
    """
    try:
        subscription = await client.create_subscription(period, None)
        logger.info(f"Created subscription with publishing interval {period}ms")
        return subscription
    except Exception as e:
        logger.error(f"Failed to create subscription: {e}")
        raise


async def modify_subscription(subscription: Subscription, period: float) -> None:
    """
    Modify an existing subscription.
    
    Args:
        subscription: The subscription to modify
        period: The new publishing interval in milliseconds
    """
    try:
        await subscription.modify_subscription(period=period)
        logger.info(f"Modified subscription to publishing interval {period}ms")
    except Exception as e:
        logger.error(f"Failed to modify subscription: {e}")
        raise


async def delete_subscription(subscription: Subscription) -> None:
    """
    Delete an existing subscription.
    
    Args:
        subscription: The subscription to delete
    """
    try:
        await subscription.delete()
        logger.info("Deleted subscription")
    except Exception as e:
        logger.error(f"Failed to delete subscription: {e}")
        raise


async def set_publishing_mode(subscription: Subscription, publishing: bool) -> None:
    """
    Set the publishing mode of an existing subscription.
    
    Args:
        subscription: The subscription to modify
        publishing: Whether to enable or disable publishing
    """
    try:
        await subscription.set_publishing_mode(publishing)
        status = "enabled" if publishing else "disabled"
        logger.info(f"Publishing mode {status}")
    except Exception as e:
        logger.error(f"Failed to set publishing mode: {e}")
        raise


async def subscribe_data_change(
    subscription: Subscription, 
    node_id: str, 
    callback: Callable[[Node, Any, Any], None],
    sampling_interval: float = 100
) -> int:
    """
    Subscribe to data changes for a specific node.
    
    Args:
        subscription: The subscription to use
        node_id: The ID of the node to subscribe to
        callback: The callback function to be called when the data changes
        sampling_interval: The sampling interval in milliseconds
        
    Returns:
        Handle ID for the monitored item
    """
    node = subscription.server.get_node(node_id)
    try:
        handle = await subscription.subscribe_data_change(node, callback, sampling_interval=sampling_interval)
        logger.info(f"Subscribed to data changes for node {node_id}")
        return handle
    except Exception as e:
        logger.error(f"Failed to subscribe to data changes: {e}")
        raise


async def keep_alive(client: Client, duration: float = 60) -> None:
    """
    Keep the connection alive for a specified duration.
    
    Args:
        client: The client with an established connection
        duration: The duration in seconds to keep the connection alive
    """
    try:
        start_time = asyncio.get_event_loop().time()
        end_time = start_time + duration
        
        while asyncio.get_event_loop().time() < end_time:
            # Read something from the server to keep the connection alive
            await client.nodes.root.read_browse_name()
            await asyncio.sleep(1)
            
        logger.info(f"Kept connection alive for {duration} seconds")
    except Exception as e:
        logger.error(f"Failed to keep connection alive: {e}")
        raise


async def create_parallel_subscriptions(
    client: Client, 
    node_ids: List[str], 
    callback: Callable[[Node, Any, Any], None],
    count: int = 2,
    period: float = 500
) -> List[Subscription]:
    """
    Create multiple subscriptions in parallel.
    
    Args:
        client: The client with an established connection
        node_ids: List of node IDs to subscribe to
        callback: The callback function for data changes
        count: Number of subscriptions to create
        period: The publishing interval in milliseconds
        
    Returns:
        List of Subscription objects
    """
    try:
        subscriptions = []
        
        # Create multiple subscriptions
        for i in range(count):
            subscription = await client.create_subscription(period, None)
            subscriptions.append(subscription)
            logger.info(f"Created subscription {i+1} with interval {period}ms")
        
        # Distribute nodes across subscriptions
        for i, node_id in enumerate(node_ids):
            sub_index = i % len(subscriptions)
            node = client.get_node(node_id)
            await subscriptions[sub_index].subscribe_data_change(node, callback)
            logger.info(f"Subscribed node {node_id} to subscription {sub_index+1}")
            
        return subscriptions
    except Exception as e:
        logger.error(f"Failed to create parallel subscriptions: {e}")
        raise 