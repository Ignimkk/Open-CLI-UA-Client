"""
Subscription module for OPC UA client.

This module provides functions to manage subscriptions for data changes.
"""

import asyncio
import logging
import datetime
import time
from typing import Any, Callable, Dict, List, Optional, Tuple, Union, Set

from asyncua import Client, ua
from asyncua.common.node import Node
from asyncua.common.subscription import Subscription

logger = logging.getLogger(__name__)

# 구독 기본값 상수 정의 - 모든 구독 관련 기본값을 한 곳에서 관리
# OPC UA 스펙에 따라 lifetime_count는 max_keep_alive_count의 최소 3배 이상이어야 함

# 구독 생성 시 기본값
DEFAULT_PUBLISHING_INTERVAL = 1000.0  # ms - 발행 간격
DEFAULT_LIFETIME_COUNT = 600  # 구독 수명 (10분) - period * lifetime = 600초
DEFAULT_MAX_KEEP_ALIVE_COUNT = 20  # Keep-Alive 카운트 (20초) - period * keepalive = 20초
DEFAULT_PRIORITY = 0  # 우선순위 (0이 가장 낮음)

# 비율 검증: DEFAULT_LIFETIME_COUNT(600) / DEFAULT_MAX_KEEP_ALIVE_COUNT(20) = 30 (권장값 3 이상 충족)

# 수정 시 사용하는 기본값 (기존 코드와 호환성 유지)
MODIFY_DEFAULT_PUBLISHING_INTERVAL = 500.0  # ms
MODIFY_DEFAULT_LIFETIME_COUNT = 600  # 새로운 기본값 사용 (이전: 2400)
MODIFY_DEFAULT_MAX_KEEP_ALIVE_COUNT = 20  # 새로운 기본값 사용 (이전: 10)


def validate_subscription_parameters(period: float, lifetime_count: int, max_keep_alive_count: int) -> Tuple[float, int, int]:
    """
    구독 파라미터를 검증하고 필요한 경우 조정합니다.
    
    Args:
        period: 발행 간격 (ms)
        lifetime_count: 수명 카운트
        max_keep_alive_count: 최대 Keep-Alive 카운트
        
    Returns:
        Tuple[float, int, int]: 검증/조정된 (period, lifetime_count, max_keep_alive_count)
    """
    # OPC UA 스펙 검증: lifetime_count는 max_keep_alive_count의 최소 3배 이상이어야 함
    min_lifetime = max_keep_alive_count * 3
    if lifetime_count < min_lifetime:
        logger.warning(f"lifetime_count({lifetime_count})가 너무 작습니다. "
                     f"최소값 {min_lifetime}으로 조정합니다.")
        lifetime_count = min_lifetime
    
    return period, lifetime_count, max_keep_alive_count


def get_fallback_parameters(sub_info: dict) -> Tuple[float, int, int, int]:
    """
    구독 정보 딕셔너리에서 파라미터를 가져오거나 기본값을 반환합니다.
    
    Args:
        sub_info: 구독 정보 딕셔너리
        
    Returns:
        Tuple[float, int, int, int]: (publishing_interval, lifetime_count, max_keep_alive_count, priority)
    """
    publishing_interval = sub_info.get("publishing_interval", DEFAULT_PUBLISHING_INTERVAL)
    lifetime_count = sub_info.get("lifetime_count", DEFAULT_LIFETIME_COUNT)
    max_keep_alive_count = sub_info.get("max_keep_alive_count", DEFAULT_MAX_KEEP_ALIVE_COUNT)
    priority = sub_info.get("priority", DEFAULT_PRIORITY)
    
    return publishing_interval, lifetime_count, max_keep_alive_count, priority


async def create_subscription(
    client: Client, 
    period: float = DEFAULT_PUBLISHING_INTERVAL, 
    lifetime_count: int = DEFAULT_LIFETIME_COUNT,
    max_keep_alive_count: int = DEFAULT_MAX_KEEP_ALIVE_COUNT, 
    priority: int = DEFAULT_PRIORITY,
    handler = None  
) -> Subscription:
    """
    Create a subscription on the server.
    
    Args:
        client: The client with an established connection
        period: The publishing interval in milliseconds
        lifetime_count: Lifetime count (multiple of publishing interval) - 권장: period * lifetime = 600초 ~ 3600초
        max_keep_alive_count: Max keep-alive count (multiple of publishing interval) - 권장: lifetime_count / 3 이상
        priority: Priority (0 is lowest)
        handler: Optional handler for subscription events (default: DataChangeHandler)
        
    Returns:
        Subscription object
        
    Note:
        OPC UA 스펙에 따라 lifetime_count는 max_keep_alive_count의 최소 3배 이상이어야 합니다.
        서버는 요청된 값을 서버의 제한에 맞게 수정할 수 있습니다.
    """
    try:
        if handler is None:
            handler = DataChangeHandler(
                log_changes=True,
                log_level=logging.INFO,
                store_values=False
            )
        
        # 파라미터 검증 및 조정
        period, lifetime_count, max_keep_alive_count = validate_subscription_parameters(
            period, lifetime_count, max_keep_alive_count
        )
        
        # AsyncUA의 create_subscription은 여러 방법으로 호출할 수 있습니다
        # 먼저 표준적인 방법 시도
        try:
            # Method 1: AsyncUA 최신 버전의 표준 방법
            subscription = await client.create_subscription(
                period, 
                handler,
                lifetime=lifetime_count,
                maxkeepalive=max_keep_alive_count,
                priority=priority
            )
            logger.debug("구독 생성 성공 (Method 1: 표준 파라미터)")
            
        except TypeError as te1:
            logger.debug(f"Method 1 실패: {te1}")
            try:
                # Method 2: 다른 파라미터명 시도
                subscription = await client.create_subscription(
                    period, 
                    handler,
                    lifetime_count=lifetime_count,
                    max_keep_alive_count=max_keep_alive_count,
                    priority=priority
                )
                logger.debug("구독 생성 성공 (Method 2: 대체 파라미터명)")
                
            except TypeError as te2:
                logger.debug(f"Method 2 실패: {te2}")
                try:
                    # Method 3: 위치 파라미터 사용
                    subscription = await client.create_subscription(
                        period, 
                        handler,
                        lifetime_count,
                        max_keep_alive_count,
                        priority
                    )
                    logger.debug("구독 생성 성공 (Method 3: 위치 파라미터)")
                    
                except (TypeError, Exception) as te3:
                    logger.debug(f"Method 3 실패: {te3}")
                    # Method 4: 기본 생성 후 수정
                    logger.info("기본 파라미터로 구독 생성 후 수정을 시도합니다...")
                    subscription = await client.create_subscription(period, handler)
                    
                    # 생성 직후 파라미터 수정 시도
                    modify_result = await modify_subscription(
                        subscription, period, lifetime_count, max_keep_alive_count
                    )
                    if modify_result:
                        logger.info("구독 파라미터가 성공적으로 수정되었습니다.")
                    else:
                        logger.warning("구독 파라미터 수정에 실패했습니다. 서버 기본값이 사용됩니다.")
        
        # 서버가 수정한 실제 파라미터 확인 및 로그
        try:
            # 구독의 실제 파라미터 확인
            actual_params = getattr(subscription, 'parameters', None)
            if actual_params:
                actual_period = getattr(actual_params, 'RevisedPublishingInterval', period)
                actual_lifetime = getattr(actual_params, 'RevisedLifetimeCount', lifetime_count)
                actual_keepalive = getattr(actual_params, 'RevisedMaxKeepAliveCount', max_keep_alive_count)
                
                # 요청값과 실제값이 다른 경우 정보 제공
                if (actual_period != period or 
                    actual_lifetime != lifetime_count or 
                    actual_keepalive != max_keep_alive_count):
                    
                    logger.info(f"서버가 구독 파라미터를 수정했습니다:")
                    logger.info(f"  Publishing Interval: {period}ms → {actual_period}ms")
                    logger.info(f"  Lifetime Count: {lifetime_count} → {actual_lifetime}")
                    logger.info(f"  Keep-Alive Count: {max_keep_alive_count} → {actual_keepalive}")
                    
                    # 실제 시간 간격 계산
                    actual_lifetime_seconds = (actual_period * actual_lifetime) / 1000
                    actual_keepalive_seconds = (actual_period * actual_keepalive) / 1000
                    
                    logger.info(f"  실제 구독 수명: {actual_lifetime_seconds:.1f}초")
                    logger.info(f"  실제 Keep-Alive 간격: {actual_keepalive_seconds:.1f}초")
                    
                    # 비율 검증
                    if actual_lifetime < actual_keepalive * 3:
                        logger.warning(f"서버 수정 후에도 lifetime/keep-alive 비율이 권장값(3:1) 미만입니다: "
                                     f"{actual_lifetime}/{actual_keepalive} = {actual_lifetime/actual_keepalive:.1f}")
        except Exception as param_err:
            logger.debug(f"구독 파라미터 확인 중 오류: {param_err}")
        
        try:
            # asyncua 내부 메커니즘을 사용하여 즉시 publish 시작
            if hasattr(subscription, 'server') and hasattr(subscription.server, 'publish'):
                await subscription.server.publish()
                logger.debug("Manual publish request sent to ensure subscription activation")
        except Exception as publish_err:
            logger.debug(f"Could not send manual publish request: {publish_err}")
        
        logger.info(f"Created subscription with publishing interval {period}ms, "
                   f"lifetime count {lifetime_count}, max keep-alive count {max_keep_alive_count}, "
                   f"priority {priority}")
        return subscription
    except Exception as e:
        logger.error(f"Failed to create subscription: {e}")
        raise


async def modify_subscription(
    subscription: Subscription, 
    period: float = MODIFY_DEFAULT_PUBLISHING_INTERVAL, 
    lifetime_count: int = MODIFY_DEFAULT_LIFETIME_COUNT, 
    max_keep_alive_count: int = MODIFY_DEFAULT_MAX_KEEP_ALIVE_COUNT
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
        # Get the server object from subscription
        server = subscription.server if hasattr(subscription, 'server') else None
        if not server:
            logger.error("Cannot find server object in subscription")
            return False
        
        # Create ModifySubscriptionParameters
        params = ua.ModifySubscriptionParameters()
        params.SubscriptionId = subscription.subscription_id
        params.RequestedPublishingInterval = period
        params.RequestedLifetimeCount = lifetime_count
        params.RequestedMaxKeepAliveCount = max_keep_alive_count
        params.MaxNotificationsPerPublish = 0  # 0 means no limit
        params.Priority = 0  # Default priority
        
        # Try different modification approaches
        if hasattr(server, 'modify_subscriptions'):
            results = await server.modify_subscriptions([params])
            if results and len(results) > 0:
                result = results[0]
                if hasattr(result, 'RevisedPublishingInterval'):
                    logger.info(f"Successfully modified subscription: "
                              f"Publishing Interval={result.RevisedPublishingInterval}ms, "
                              f"Lifetime Count={result.RevisedLifetimeCount}, "
                              f"Keep-Alive Count={result.RevisedMaxKeepAliveCount}")
                    # Update subscription parameters if possible
                    _update_subscription_parameters(subscription, result)
                    return True
        
        # Fallback approaches
        if hasattr(server, 'modify_subscription'):
            await server.modify_subscription(params)
            logger.info("Used server.modify_subscription method")
            return True
        
        if hasattr(server, 'uaclient') and hasattr(server.uaclient, 'modify_subscription'):
            request = ua.ModifySubscriptionRequest()
            request.SubscriptionId = subscription.subscription_id
            request.RequestedPublishingInterval = period
            request.RequestedLifetimeCount = lifetime_count
            request.RequestedMaxKeepAliveCount = max_keep_alive_count
            request.MaxNotificationsPerPublish = 0
            request.Priority = 0
            
            result = await server.uaclient.modify_subscription(request)
            logger.info("Used server.uaclient.modify_subscription method")
            
            if hasattr(result, 'RevisedPublishingInterval'):
                logger.info(f"Successfully modified subscription via uaclient: "
                          f"Publishing Interval={result.RevisedPublishingInterval}ms")
            return True
        
        # Final fallback: Update parameters directly
        logger.warning("No modify subscription API found, updating parameters directly")
        if hasattr(subscription, 'parameters'):
            old_interval = getattr(subscription.parameters, 'RequestedPublishingInterval', None)
            subscription.parameters.RequestedPublishingInterval = period
            subscription.parameters.RequestedLifetimeCount = lifetime_count
            subscription.parameters.RequestedMaxKeepAliveCount = max_keep_alive_count
            
            logger.info(f"Updated subscription parameters directly: "
                      f"Interval {old_interval} -> {period}")
            return True
        
        logger.error("Cannot modify subscription: no suitable API found")
        return False
        
    except Exception as e:
        error_str = str(e)
        if "BadServiceUnsupported" in error_str:
            logger.warning("Server does not support subscription modification")
            # Try parameter update as fallback
            if hasattr(subscription, 'parameters'):
                subscription.parameters.RequestedPublishingInterval = period
                subscription.parameters.RequestedLifetimeCount = lifetime_count
                subscription.parameters.RequestedMaxKeepAliveCount = max_keep_alive_count
                logger.info("Fallback: Updated parameters locally since server doesn't support modification")
                return True
            return False
        else:
            err_msg = error_str[:100] + "... [내용 생략]" if len(error_str) > 100 else error_str
            logger.error(f"Failed to modify subscription: {err_msg}")
            
            # Final fallback for any error
            if hasattr(subscription, 'parameters'):
                subscription.parameters.RequestedPublishingInterval = period
                subscription.parameters.RequestedLifetimeCount = lifetime_count
                subscription.parameters.RequestedMaxKeepAliveCount = max_keep_alive_count
                logger.info("Fallback: Updated parameters locally after error")
                return True
            
            return False


def _update_subscription_parameters(subscription: Subscription, result) -> None:
    """Helper function to update subscription parameters."""
    try:
        if hasattr(subscription, 'parameters'):
            subscription.parameters.RequestedPublishingInterval = result.RevisedPublishingInterval
            subscription.parameters.RequestedLifetimeCount = result.RevisedLifetimeCount
            subscription.parameters.RequestedMaxKeepAliveCount = result.RevisedMaxKeepAliveCount
    except Exception as update_err:
        logger.debug(f"Could not update subscription parameters: {update_err}")


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
            logger.warning("Cannot set publishing mode: no suitable method found")
            return False
        return True
    except Exception as e:
        logger.error(f"Failed to set publishing mode: {e}")
        return False


def normalize_node_id(node_id):
    """
    NodeId를 표준 문자열 형태로 변환합니다.
    """
    if hasattr(node_id, 'NamespaceIndex') and hasattr(node_id, 'Identifier'):
        if node_id.NamespaceIndex == 0:
            return f"i={node_id.Identifier}"
        else:
            if hasattr(node_id, 'NodeIdType') and node_id.NodeIdType.name == 'String':
                return f"ns={node_id.NamespaceIndex};s={node_id.Identifier}"
            else:
                return f"ns={node_id.NamespaceIndex};i={node_id.Identifier}"
    else:
        return str(node_id)


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
        """
        logger.debug(f"datachange_notification called for node {node.nodeid}")
        
        # 노드 이름 가져오기
        try:
            display_name = await node.read_browse_name()
            name = display_name.Name
        except:
            node_id_str = normalize_node_id(node.nodeid)
            name = node_id_str  # 정규화된 node_id 사용
        
        # Keep-alive와 실제 데이터 변경 구분
        try:
            current_time = datetime.datetime.now().strftime("%H:%M:%S")
            
            # 데이터 변경인지 keep-alive인지 간단하게 판단
            is_keep_alive = False
            if hasattr(data, 'monitored_item') and hasattr(data.monitored_item, 'Value'):
                # StatusCode나 Timestamp를 통해 keep-alive 여부 추정
                status_code = getattr(data.monitored_item.Value, 'StatusCode', None)
                if status_code and not getattr(status_code, 'is_good', lambda: True)():
                    is_keep_alive = True
            
            # 간결한 콘솔 출력
            if not self.callback:
                if is_keep_alive:
                    print(f"[{current_time}]  {name}: keep-alive")
                else:
                    print(f"[{current_time}] {name}: {val}")
        except Exception as e:
            # 오류 시 기본 출력 방식 사용
            if not self.callback:
                print(f"{name}: {val}")
        
        # 내부 콜백 처리를 위해 __call__ 호출
        await self(node, val, data)

    async def status_change_notification(self, status):
        """Handle status change notifications."""
        try:
            status_str = str(status)
            self.logger.info(f"Subscription status changed: {status_str}")
        except Exception as e:
            self.logger.error(f"Error in status change handler: {e}")
    
    async def event_notification(self, event):
        """Handle event notifications."""
        try:
            event_str = str(event)
            if len(event_str) > 100:
                event_str = f"{event_str[:100]}... [내용 생략]"
            self.logger.info(f"Event notification received: {event_str}")
        except Exception as e:
            self.logger.error(f"Error in event notification handler: {e}")
            
    async def __call__(self, node: Node, value: Any, data: Any):
        """Handle data change notifications."""
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
            
            # Log the change if enabled (내부 로깅용)
            if self.log_changes:
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
        """Get stored values for a specific node or all nodes."""
        if node_id:
            return self.stored_values.get(node_id, [])
        return self.stored_values
        
    def clear_stored_values(self, node_id: str = None):
        """Clear stored values for a specific node or all nodes."""
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
        client = _get_client_from_subscription(subscription)
        if not client:
            raise ValueError("Invalid subscription object: missing client/server reference")
            
        # Get the node
        node = _get_node_from_client(client, node_id)
        
        # Create the appropriate handler
        handler = _create_handler(callback, advanced_handler_options)
                
        # Create the monitored item with multiple approaches
        handle = await _create_monitored_item(subscription, node, handler, sampling_interval, queuesize)
        
        if handle is not None:
            logger.info(f"Subscribed to data changes for node {node_id} with handle {handle}")
            return handle
        else:
            raise ValueError("Subscription handle is None - this should not happen")
            
    except Exception as e:
        logger.error(f"Failed to subscribe to data changes: {e}")
        raise


def _get_client_from_subscription(subscription: Subscription):
    """Get client reference from subscription."""
    if hasattr(subscription, 'server'):
        return subscription.server
    elif hasattr(subscription, '_client'):
        return subscription._client
    elif hasattr(subscription, 'client'):
        return subscription.client
    return None


def _get_node_from_client(client, node_id: str) -> Node:
    """Get node from client using node_id."""
    try:
        # Try string parsing first for better error messages
        if isinstance(node_id, str):
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
            
        # Verify node exists with a simple read operation
        try:
            asyncio.create_task(node.read_browse_name())
        except Exception as read_err:
            logger.warning(f"Node exists but may not be readable: {read_err}")
            
        return node
        
    except Exception as node_err:
        logger.error(f"Error getting node {node_id}: {node_err}")
        raise ValueError(f"Invalid node ID or node not accessible: {node_id}")


def _create_handler(callback, advanced_handler_options):
    """Create appropriate handler for subscription."""
    handler_opts = advanced_handler_options or {}
    direct_handler = handler_opts.get('direct_handler')
    
    if direct_handler:
        # Use the provided handler directly
        return direct_handler
    else:
        # Always use DataChangeHandler for normal cases
        if callback:
            handler_opts['callback'] = callback
        return DataChangeHandler(**handler_opts)


async def _create_monitored_item(subscription, node, handler, sampling_interval, queuesize):
    """Create monitored item with multiple fallback approaches."""
    handle = None
    errors = []
    
    # Approach 1: Full parameters
    try:
        handle = await subscription.subscribe_data_change(
            node, handler, queuesize=queuesize, sampling_interval=sampling_interval
        )
    except Exception as e:
        errors.append(f"Approach 1 failed: {str(e)}")
        
        # Approach 2: Without queuesize
        try:
            handle = await subscription.subscribe_data_change(
                node, handler, sampling_interval=sampling_interval
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
                    
                    # All approaches failed
                    error_details = "; ".join(errors)
                    logger.error(f"All subscription approaches failed: {error_details}")
                    raise ValueError(f"Could not create subscription: {error_details}")
    
    return handle


async def modify_monitored_item(
    subscription: Subscription,
    handle: int,
    new_sampling_interval: float,
    new_queuesize: int = 0,
    deadband_filter_value: float = -1
) -> bool:
    """
    Modify a monitored item's parameters.
    
    Args:
        subscription: The subscription containing the monitored item
        handle: Handle of the monitored item to modify
        new_sampling_interval: New sampling interval in milliseconds
        new_queuesize: New queue size (0 means server default)
        deadband_filter_value: New deadband filter value
                              -1: Keep existing filter
                              None: Remove filter
                              >0: Set absolute deadband filter value
        
    Returns:
        True if successful, False otherwise
    """
    try:
        # Check if the subscription object has the modify_monitored_item method
        if hasattr(subscription, 'modify_monitored_item'):
            result = await subscription.modify_monitored_item(
                handle, new_sampling_interval, new_queuesize, deadband_filter_value
            )
            
            if result and len(result) > 0:
                status_code = result[0].StatusCode if hasattr(result[0], 'StatusCode') else None
                if status_code and hasattr(status_code, 'is_good') and status_code.is_good():
                    logger.info(f"Successfully modified monitored item {handle}")
                    return True
                else:
                    logger.error(f"Failed to modify monitored item {handle}: {status_code}")
                    return False
            else:
                logger.warning(f"Modify monitored item returned empty result for handle {handle}")
                return False
        else:
            # Manual implementation if the method is not available
            return await _manual_modify_monitored_item(
                subscription, handle, new_sampling_interval, new_queuesize, deadband_filter_value
            )
                
    except Exception as e:
        logger.error(f"Failed to modify monitored item {handle}: {e}")
        return False


async def _manual_modify_monitored_item(subscription, handle, new_sampling_interval, new_queuesize, deadband_filter_value):
    """Manual implementation for modifying monitored items."""
    logger.warning("modify_monitored_item method not available, using manual implementation")
    
    if not hasattr(subscription, 'server') or not hasattr(subscription.server, 'uaclient'):
        logger.error("Cannot modify monitored item: no suitable API found")
        return False
        
    # Find the monitored item in subscription's internal map
    client_handle = None
    monitored_items_map = getattr(subscription, '_monitoreditems_map', {})
    
    for ch, data in monitored_items_map.items():
        if hasattr(data, 'server_handle') and data.server_handle == handle:
            client_handle = ch
            break
    
    if client_handle is None:
        logger.error(f"Could not find monitored item with handle {handle}")
        return False
    
    # Create modification request
    modif_item = ua.MonitoredItemModifyRequest()
    modif_item.MonitoredItemId = handle
    
    # Create monitoring parameters
    req_params = ua.MonitoringParameters()
    req_params.ClientHandle = client_handle
    req_params.QueueSize = new_queuesize
    req_params.SamplingInterval = new_sampling_interval
    
    # Handle deadband filter
    req_params.Filter = _create_deadband_filter(
        deadband_filter_value, monitored_items_map.get(client_handle)
    )
    
    modif_item.RequestedParameters = req_params
    
    # Create modify request
    params = ua.ModifyMonitoredItemsParameters()
    params.SubscriptionId = subscription.subscription_id
    params.ItemsToModify = [modif_item]
    
    # Send request
    results = await subscription.server.uaclient.modify_monitored_items(params)
    
    if results and len(results) > 0:
        result = results[0]
        if hasattr(result, 'StatusCode') and result.StatusCode.is_good():
            # Update the filter in the monitored items map
            item_data = monitored_items_map.get(client_handle)
            if item_data and hasattr(result, 'FilterResult'):
                item_data.mfilter = result.FilterResult
            
            logger.info(f"Successfully modified monitored item {handle}")
            return True
        else:
            logger.error(f"Failed to modify monitored item {handle}: {result.StatusCode}")
            return False
    else:
        logger.error(f"No results returned for modify monitored item {handle}")
        return False


def _create_deadband_filter(deadband_filter_value, item_data):
    """Create deadband filter based on value."""
    if deadband_filter_value is None:
        return None
    elif deadband_filter_value < 0:
        # Keep existing filter
        if item_data and hasattr(item_data, 'mfilter'):
            return item_data.mfilter
        else:
            return None
    else:
        # Create new deadband filter
        deadband_filter = ua.DataChangeFilter()
        deadband_filter.Trigger = ua.DataChangeTrigger(1)  # Value or status change
        deadband_filter.DeadbandType = 1  # Absolute
        deadband_filter.DeadbandValue = deadband_filter_value
        return deadband_filter


async def set_monitoring_mode(
    subscription: Subscription,
    handles: Union[int, List[int]],
    monitoring_mode: Union[str, int] = "Reporting"
) -> bool:
    """
    Set monitoring mode for monitored items.
    
    Args:
        subscription: The subscription containing the monitored items
        handles: Handle or list of handles of monitored items
        monitoring_mode: Monitoring mode - "Disabled", "Sampling", "Reporting" or ua.MonitoringMode value
        
    Returns:
        True if successful, False otherwise
    """
    try:
        # Convert single handle to list
        if isinstance(handles, int):
            handles = [handles]
        
        # Convert string mode to ua.MonitoringMode
        monitoring_mode = _parse_monitoring_mode(monitoring_mode)
        
        # Get server object
        server = subscription.server if hasattr(subscription, 'server') else None
        if not server:
            logger.error("Cannot find server object in subscription")
            return False
        
        # Try different approaches to set monitoring mode
        if hasattr(server, 'set_monitoring_mode'):
            return await _set_monitoring_mode_server(server, subscription, handles, monitoring_mode)
        elif hasattr(server, 'uaclient'):
            return await _set_monitoring_mode_uaclient(server, subscription, handles, monitoring_mode)
        else:
            logger.error("Cannot set monitoring mode: no suitable API found")
            return False
        
    except Exception as e:
        err_msg = str(e)[:100] + "... [내용 생략]" if len(str(e)) > 100 else str(e)
        logger.error(f"Failed to set monitoring mode: {err_msg}")
        return False


def _parse_monitoring_mode(monitoring_mode):
    """Parse monitoring mode string to ua.MonitoringMode."""
    if isinstance(monitoring_mode, str):
        mode_map = {
            "disabled": ua.MonitoringMode.Disabled,
            "sampling": ua.MonitoringMode.Sampling,
            "reporting": ua.MonitoringMode.Reporting
        }
        mode_lower = monitoring_mode.lower()
        if mode_lower in mode_map:
            return mode_map[mode_lower]
        else:
            raise ValueError(f"Invalid monitoring mode: {monitoring_mode}")
    return monitoring_mode


async def _set_monitoring_mode_server(server, subscription, handles, monitoring_mode):
    """Set monitoring mode using server.set_monitoring_mode."""
    params = ua.SetMonitoringModeParameters()
    params.SubscriptionId = subscription.subscription_id
    params.MonitoringMode = monitoring_mode
    params.MonitoredItemIds = handles
    
    results = await server.set_monitoring_mode(params)
    
    if results:
        success_count = sum(1 for result in results 
                          if (hasattr(result, 'is_good') and result.is_good()) or
                             (hasattr(result, 'value') and result.value == 0))
        
        if success_count == len(handles):
            mode_name = monitoring_mode.name if hasattr(monitoring_mode, 'name') else str(monitoring_mode)
            logger.info(f"Successfully set monitoring mode to {mode_name} for {success_count} items")
            return True
        else:
            logger.warning(f"Set monitoring mode succeeded for {success_count}/{len(handles)} items")
            return success_count > 0
    else:
        logger.error("No results returned for set monitoring mode request")
        return False


async def _set_monitoring_mode_uaclient(server, subscription, handles, monitoring_mode):
    """Set monitoring mode using server.uaclient."""
    request = ua.SetMonitoringModeRequest()
    request.SubscriptionId = subscription.subscription_id
    request.MonitoringMode = monitoring_mode
    request.MonitoredItemIds = handles
    
    result = await server.uaclient.set_monitoring_mode(request)
    
    if result and hasattr(result, 'Results'):
        success_count = sum(1 for status in result.Results
                          if (hasattr(status, 'is_good') and status.is_good()) or
                             (hasattr(status, 'value') and status.value == 0))
        
        mode_name = monitoring_mode.name if hasattr(monitoring_mode, 'name') else str(monitoring_mode)
        logger.info(f"Set monitoring mode to {mode_name} for {success_count}/{len(handles)} items")
        return success_count > 0
    else:
        logger.error("Failed to set monitoring mode via uaclient")
        return False
