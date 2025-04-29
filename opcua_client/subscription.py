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
    Create a subscription on the server.
    
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


async def modify_subscription(
    subscription: Subscription, 
    period: float = 500, 
    lifetime_count: int = 10000, 
    max_keep_alive_count: int = 3000
) -> None:
    """
    Modify an existing subscription.
    
    Args:
        subscription: The subscription to modify
        period: The new publishing interval in milliseconds
        lifetime_count: The new lifetime count
        max_keep_alive_count: The new max keep-alive count
    """
    try:
        # 구독 객체가 modify_subscription 메서드를 가지고 있는지 확인
        if hasattr(subscription, 'modify_subscription'):
            # 라이브러리 버전이 modify_subscription 메서드를 지원하는 경우
            await subscription.modify_subscription(period, lifetime_count, max_keep_alive_count)
        else:
            # 직접 ModifySubscriptionRequest 생성하여 전송
            # _client 또는 server 속성을 사용하여 서버 통신
            if hasattr(subscription, 'server') and hasattr(subscription.server, 'uaclient'):
                # 서버를 통한 전송
                request = ua.ModifySubscriptionRequest()
                request.SubscriptionId = subscription.subscription_id
                request.RequestedPublishingInterval = period
                request.RequestedLifetimeCount = lifetime_count
                request.RequestedMaxKeepAliveCount = max_keep_alive_count
                
                # 서버의 uaclient를 통해 요청 전송
                result = await subscription.server.uaclient.modify_subscription(request)
                
                # 구독 속성 업데이트 (속성 이름이 다를 수 있음)
                try:
                    subscription.RevisedPublishingInterval = result.RevisedPublishingInterval
                    subscription.RevisedLifetimeCount = result.RevisedLifetimeCount
                    subscription.RevisedMaxKeepAliveCount = result.RevisedMaxKeepAliveCount
                except:
                    pass  # 속성이 없으면 무시
            else:
                # 내부 구현으로 대체할 수 없음 - 로깅만 수행
                logger.warning(f"Cannot modify subscription: no suitable API found")
        
        logger.info(f"Modified subscription to publishing interval {period}ms")
    except Exception as e:
        # 예외 정보에서 바이너리 데이터가 포함될 가능성이 있으므로 간결하게 로깅
        err_msg = str(e)
        if len(err_msg) > 100:
            err_msg = f"{err_msg[:100]}... [내용 생략]"
        logger.error(f"Failed to modify subscription: {err_msg}")
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
        # 단일 구독의 경우에 대한 처리
        if hasattr(subscription.server, 'uaclient'):
            request = ua.SetPublishingModeRequest()
            request.PublishingEnabled = publishing
            request.SubscriptionIds = [subscription.subscription_id]
            
            result = await subscription.server.uaclient.set_publishing_mode(request)
            status = "enabled" if publishing else "disabled"
            logger.info(f"Publishing mode {status}")
        else:
            # 기존 코드 유지 (server에 set_publishing_mode가 있는 경우)
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
    try:
        # 수정: UaClient 대신 _client 속성 사용
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
            logger.debug("Keep-alive ping sent")
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
            
            # 수정: 노드 획득 방식 수정
            try:
                node = client.get_node(node_id)
                await subscriptions[sub_index].subscribe_data_change(node, callback)
                logger.info(f"Subscribed node {node_id} to subscription {sub_index+1}")
            except Exception as e:
                logger.error(f"Failed to subscribe node {node_id}: {e}")
            
        return subscriptions
    except Exception as e:
        logger.error(f"Failed to create parallel subscriptions: {e}")
        raise 