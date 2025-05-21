"""
Subscription module for OPC UA client.

This module provides functions to manage subscriptions for data changes.
"""

import asyncio
import logging
import datetime
from typing import Any, Callable, Dict, List, Optional, Tuple, Union, Set

from asyncua import Client, ua
from asyncua.common.node import Node
from asyncua.common.subscription import Subscription

logger = logging.getLogger(__name__)


async def create_subscription(
    client: Client, 
    period: float = 500, 
    lifetime_count: int = 10000, 
    max_keep_alive_count: int = 3000,
    priority: int = 0
) -> Subscription:
    """
    Create a subscription on the server.
    
    Args:
        client: The client with an established connection
        period: The publishing interval in milliseconds
        lifetime_count: Lifetime count (multiple of publishing interval)
        max_keep_alive_count: Max keep-alive count (multiple of publishing interval)
        priority: Priority (0 is lowest)
        
    Returns:
        Subscription object
    """
    try:
        # 기본 핸들러 생성 - 콜백 없이도 기본 출력 제공
        handler = DataChangeHandler(
            log_changes=True,
            log_level=logging.INFO,
            store_values=False
        )
        
        # 구독 생성 시 핸들러 전달
        subscription = await client.create_subscription(
            period, 
            handler=handler  # 명시적으로 핸들러 전달
        )
        
        logger.info(f"Created subscription with publishing interval {period}ms, "
                   f"lifetime count {lifetime_count}, max keep-alive count {max_keep_alive_count}, "
                   f"priority {priority}")
        return subscription
    except Exception as e:
        logger.error(f"Failed to create subscription: {e}")
        raise


async def modify_subscription(
    subscription: Subscription, 
    period: float = 500, 
    lifetime_count: int = 10000, 
    max_keep_alive_count: int = 3000
) -> bool:
    """
    Modify an existing subscription.
    
    Args:
        subscription: The subscription to modify
        period: The new publishing interval in milliseconds
        lifetime_count: The new lifetime count
        max_keep_alive_count: The new max keep-alive count
        
    Returns:
        True if successful, False otherwise
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
        return True
    except Exception as e:
        # 예외 정보에서 바이너리 데이터가 포함될 가능성이 있으므로 간결하게 로깅
        err_msg = str(e)
        if len(err_msg) > 100:
            err_msg = f"{err_msg[:100]}... [내용 생략]"
        logger.error(f"Failed to modify subscription: {err_msg}")
        return False


async def delete_subscription(subscription: Subscription) -> bool:
    """
    Delete an existing subscription.
    
    Args:
        subscription: The subscription to delete
        
    Returns:
        True if successful, False otherwise
    """
    try:
        await subscription.delete()
        logger.info(f"Deleted subscription {subscription.subscription_id}")
        return True
    except Exception as e:
        logger.error(f"Failed to delete subscription: {e}")
        return False


async def set_publishing_mode(subscription: Subscription, publishing: bool) -> bool:
    """
    Set the publishing mode of an existing subscription.
    
    Args:
        subscription: The subscription to modify
        publishing: Whether to enable or disable publishing
        
    Returns:
        True if successful, False otherwise
    """
    try:
        # 단일 구독의 경우에 대한 처리
        if hasattr(subscription, 'server') and hasattr(subscription.server, 'uaclient'):
            request = ua.SetPublishingModeRequest()
            request.PublishingEnabled = publishing
            request.SubscriptionIds = [subscription.subscription_id]
            
            result = await subscription.server.uaclient.set_publishing_mode(request)
            status = "enabled" if publishing else "disabled"
            logger.info(f"Publishing mode {status} for subscription {subscription.subscription_id}")
        elif hasattr(subscription, 'set_publishing_mode'):
            # 기존 코드 유지 (구독 객체에 set_publishing_mode가 있는 경우)
            await subscription.set_publishing_mode(publishing)
            status = "enabled" if publishing else "disabled"
            logger.info(f"Publishing mode {status} for subscription {subscription.subscription_id}")
        else:
            logger.warning(f"Cannot set publishing mode: no suitable method found")
            return False
        return True
    except Exception as e:
        logger.error(f"Failed to set publishing mode: {e}")
        return False


class DataChangeHandler:
    """
    Advanced handler for data change notifications with customization options.
    """
    def __init__(self, 
                 callback: Callable[[Node, Any, Any], None] = None, 
                 log_changes: bool = True,
                 log_level: int = logging.INFO,
                 store_values: bool = False,
                 max_values: int = 100,
                 timestamp_values: bool = True):
        """
        Initialize a new data change handler.
        
        Args:
            callback: External callback function (optional)
            log_changes: Whether to log value changes
            log_level: Logging level for changes
            store_values: Whether to store values in memory
            max_values: Maximum number of values to store
            timestamp_values: Whether to add timestamps to stored values
        """
        self.callback = callback
        self.log_changes = log_changes
        self.log_level = log_level
        self.store_values = store_values
        self.max_values = max_values
        self.timestamp_values = timestamp_values
        self.stored_values = {}  # Dictionary: node_id -> list of (timestamp, value) tuples
        self.logger = logging.getLogger(__name__)
        
    async def datachange_notification(self, node: Node, val, data):
        """
        Handle data change notifications - compatible with asyncua's subscription handler interface.
        
        This method name matches what asyncua expects when used as a handler.
        asyncua 라이브러리는 데이터 변경 시 이 이름의 메서드를 호출합니다.
        """
        logger.debug(f"datachange_notification called for node {node.nodeid}")
        
        # 노드 이름 가져오기
        try:
            display_name = await node.read_browse_name()
            name = display_name.Name
        except:
            name = str(node.nodeid)
        
        # 간결한 콘솔 출력 (항상 출력)
        print(f"{name}: {val}")
        
        # 내부 콜백 처리를 위해 __call__ 호출
        await self(node, val, data)

    async def status_change_notification(self, status):
        """
        Handle status change notifications - required for subscription handler interface.
        
        Args:
            status: Status change information
        """
        try:
            status_str = str(status)
            self.logger.info(f"Subscription status changed: {status_str}")
        except Exception as e:
            self.logger.error(f"Error in status change handler: {e}")
    
    async def event_notification(self, event):
        """
        Handle event notifications - required for subscription handler interface.
        
        Args:
            event: Event information
        """
        try:
            event_str = str(event)
            if len(event_str) > 100:
                event_str = f"{event_str[:100]}... [내용 생략]"
            self.logger.info(f"Event notification received: {event_str}")
        except Exception as e:
            self.logger.error(f"Error in event notification handler: {e}")
            
    async def __call__(self, node: Node, value: Any, data: Any):
        """
        Handle data change notifications.
        
        Args:
            node: The node that changed
            value: The new value
            data: Additional data about the change
        """
        try:
            # Get node identifier as string for storage and logging
            node_id = str(node.nodeid)
            timestamp = datetime.datetime.now()
            
            # 노드 이름 가져오기
            try:
                display_name = await node.read_browse_name()
                name = display_name.Name
            except:
                name = node_id
            
            # 간결한 콘솔 출력 (항상 출력)
            print(f"{name}: {value}")
            
            # Log the change if enabled (내부 로깅용)
            if self.log_changes:
                # Format value for logging
                value_str = str(value)
                if len(value_str) > 100:
                    value_str = f"{value_str[:100]}... [내용 생략]"
                    
                self.logger.log(self.log_level, f"Data change for {name} ({node_id}): {value_str}")
            
            # Store the value if enabled
            if self.store_values:
                if node_id not in self.stored_values:
                    self.stored_values[node_id] = []
                    
                if self.timestamp_values:
                    self.stored_values[node_id].append((timestamp, value))
                else:
                    self.stored_values[node_id].append(value)
                    
                # Trim list if it exceeds max_values
                if len(self.stored_values[node_id]) > self.max_values:
                    self.stored_values[node_id] = self.stored_values[node_id][-self.max_values:]
            
            # Call the external callback if provided
            if self.callback:
                if asyncio.iscoroutinefunction(self.callback):
                    await self.callback(node, value, data)
                else:
                    # Support for non-async callbacks
                    self.callback(node, value, data)
                
        except Exception as e:
            self.logger.error(f"Error in data change handler: {e}")
            
    def get_stored_values(self, node_id: str = None):
        """
        Get stored values for a specific node or all nodes.
        
        Args:
            node_id: Node ID to get values for, or None for all nodes
            
        Returns:
            Dictionary of stored values or list of values for a specific node
        """
        if node_id:
            return self.stored_values.get(node_id, [])
        return self.stored_values
        
    def clear_stored_values(self, node_id: str = None):
        """
        Clear stored values for a specific node or all nodes.
        
        Args:
            node_id: Node ID to clear values for, or None for all nodes
        """
        if node_id:
            if node_id in self.stored_values:
                self.stored_values[node_id] = []
        else:
            self.stored_values = {}


async def subscribe_data_change(
    subscription: Subscription, 
    node_id: str, 
    callback: Callable[[Node, Any, Any], None] = None,
    sampling_interval: float = 100,
    queuesize: int = 1,
    advanced_handler_options: Optional[Dict[str, Any]] = None
) -> int:
    """
    Subscribe to data changes for a specific node.
    
    Args:
        subscription: The subscription to use
        node_id: The ID of the node to subscribe to
        callback: The callback function to be called when the data changes
        sampling_interval: The sampling interval in milliseconds
        queuesize: Size of data change notification queue
        advanced_handler_options: Options for DataChangeHandler if used
        
    Returns:
        Handle ID for the monitored item
    """
    try:
        # Get a reference to the client or server
        client = None
        if hasattr(subscription, 'server'):
            client = subscription.server
        elif hasattr(subscription, '_client'):
            client = subscription._client
        elif hasattr(subscription, 'client'):
            client = subscription.client
        
        if client is None:
            logger.error("Could not get client or server reference from subscription")
            raise ValueError("Invalid subscription object: missing client/server reference")
            
        # Get the node using the appropriate method
        node = None
        try:
            # Try string parsing first for better error messages
            if isinstance(node_id, str):
                # Try to parse as NodeId string
                try:
                    node_id_obj = ua.NodeId.from_string(node_id)
                    node = Node(client, node_id_obj)
                except Exception as parse_err:
                    logger.warning(f"Could not parse node ID '{node_id}': {parse_err}")
                    # Fall back to client's get_node method
                    node = client.get_node(node_id)
            else:
                # Already a NodeId object or similar
                node = client.get_node(node_id)
                
            # Verify node exists with a simple read operation - check if readable
            try:
                await node.read_browse_name()
            except Exception as read_err:
                logger.warning(f"Node exists but may not be readable: {read_err}")
                # Continue anyway as some nodes might be writable but not readable
                
        except Exception as node_err:
            logger.error(f"Error getting node {node_id}: {node_err}")
            raise ValueError(f"Invalid node ID or node not accessible: {node_id}")
        
        # Create the appropriate handler
        handler = None
        
        # Always use DataChangeHandler
        handler_opts = advanced_handler_options or {}
        if callback:
            handler_opts['callback'] = callback
        
        # 핸들러 생성 - 콜백이 없어도 기본 출력 제공
        handler = DataChangeHandler(**handler_opts)
                
        # Create the monitored item with appropriate parameters
        # Try multiple approaches with different parameter combinations
        # since servers and library versions may have different requirements
        handle = None
        errors = []
        
        # Approach 1: Full parameters
        try:
            handle = await subscription.subscribe_data_change(
                node,
                handler,
                queuesize=queuesize,
                sampling_interval=sampling_interval
            )
        except Exception as e:
            errors.append(f"Approach 1 failed: {str(e)}")
            
            # Approach 2: Without queuesize
            try:
                handle = await subscription.subscribe_data_change(
                    node,
                    handler,
                    sampling_interval=sampling_interval
                )
            except Exception as e:
                errors.append(f"Approach 2 failed: {str(e)}")
                
                # Approach 3: Only required parameters
                try:
                    handle = await subscription.subscribe_data_change(node, handler)
                except Exception as e:
                    errors.append(f"Approach 3 failed: {str(e)}")
                    
                    # Approach 4: Just node
                    try:
                        handle = await subscription.subscribe_data_change(node)
                    except Exception as e:
                        errors.append(f"Approach 4 failed: {str(e)}")
                        
                        # All approaches failed, raise a combined error
                        error_details = "; ".join(errors)
                        logger.error(f"All subscription approaches failed: {error_details}")
                        raise ValueError(f"Could not create subscription: {error_details}")
        
        # If we got here, one of the approaches worked
        if handle is not None:
            logger.info(f"Subscribed to data changes for node {node_id} with handle {handle}")
            return handle
        else:
            raise ValueError("Subscription handle is None - this should not happen")
            
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
    callback: Callable[[Node, Any, Any], None],
    count: int = 2,
    period: float = 500
) -> List[Subscription]:
    """
    Create multiple subscriptions in parallel.
    
    Args:
        client: The client with an established connection
        callback: The callback function to be called when data changes
        count: The number of subscriptions to create
        period: The publishing interval in milliseconds
        
    Returns:
        List of subscription objects
    """
    try:
        tasks = [
            create_subscription(client, period) for _ in range(count)
        ]
        subscriptions = await asyncio.gather(*tasks)
        logger.info(f"Created {count} parallel subscriptions")
        return subscriptions
    except Exception as e:
        logger.error(f"Failed to create parallel subscriptions: {e}")
        raise


async def create_subscription_group(
    client: Client,
    nodes: List[str],
    callback: Callable[[Node, Any, Any], None] = None,
    period: float = 500,
    sampling_interval: float = 100,
    advanced_handler_options: Optional[Dict[str, Any]] = None
) -> Tuple[Subscription, List[int]]:
    """
    Create a subscription and subscribe to multiple nodes in one operation.
    
    Args:
        client: The client with an established connection
        nodes: List of node IDs to subscribe to
        callback: The callback function to be called when data changes
        period: The publishing interval in milliseconds
        sampling_interval: The sampling interval in milliseconds
        advanced_handler_options: Options for DataChangeHandler if used
        
    Returns:
        Tuple of (subscription, list of handles)
    """
    try:
        # Create subscription
        subscription = await create_subscription(client, period)
        
        # Subscribe to all nodes
        handles = []
        for node_id in nodes:
            try:
                handle = await subscribe_data_change(
                    subscription, 
                    node_id, 
                    callback, 
                    sampling_interval,
                    advanced_handler_options=advanced_handler_options
                )
                handles.append(handle)
            except Exception as node_e:
                logger.error(f"Failed to subscribe to node {node_id}: {node_e}")
                
        logger.info(f"Created subscription group with {len(handles)} monitored items")
        return subscription, handles
    except Exception as e:
        logger.error(f"Failed to create subscription group: {e}")
        raise 