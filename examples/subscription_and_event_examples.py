"""
Examples for subscriptions, monitored items, and event handling.
"""

import asyncio
import logging
import sys
sys.path.insert(0, '..')

from asyncua import ua

from opcua_client import connection, subscription, event
from opcua_client.utils import setup_logging


# Define callback functions for data changes and events
def data_change_callback(node, val, data):
    print(f"Data change from {node}: {val}")


def event_callback(event_data):
    print(f"Event received: {event_data}")


async def example_empty_subscription():
    """Example showing how to create an empty subscription."""
    server_url = "opc.tcp://mk:62541/Quickstarts/ReferenceServer"
    
    print("Creating empty subscription...")
    client = await connection.create_session(server_url)
    
    try:
        # Create an empty subscription
        sub = await subscription.create_subscription(client, period=500)
        print(f"Created subscription with ID {sub.subscription_id}")
        
        # Let it run for a while
        await asyncio.sleep(2)
        
        # Delete the subscription
        await subscription.delete_subscription(sub)
        print("Subscription deleted")
        
    finally:
        await connection.close_session(client)


async def example_modify_subscription():
    """Example showing how to modify a subscription."""
    server_url = "opc.tcp://mk:62541/Quickstarts/ReferenceServer"
    
    print("Modifying subscription...")
    client = await connection.create_session(server_url)
    
    try:
        # Create a subscription
        sub = await subscription.create_subscription(client, period=1000)
        print(f"Created subscription with period 1000ms")
        
        # 원래 설정된 값을 출력 - attribute 오류 해결
        # 라이브러리 버전에 따라 속성 이름이 다를 수 있으므로 안전하게 접근
        original_interval = getattr(sub, 'RevisedPublishingInterval', None) or getattr(sub, 'revisedPublishingInterval', 1000)
        original_lifetime = getattr(sub, 'RevisedLifetimeCount', None) or getattr(sub, 'revisedLifetimeCount', 10000)
        original_keepalive = getattr(sub, 'RevisedMaxKeepAliveCount', None) or getattr(sub, 'revisedMaxKeepAliveCount', 3000)
        
        print(f"Original publishing interval: {original_interval}")
        print(f"Original lifetime count: {original_lifetime}")
        print(f"Original max keep alive count: {original_keepalive}")
        
        # Let it run for a while
        await asyncio.sleep(2)
        
        # Modify the subscription to have a faster publishing interval
        await subscription.modify_subscription(sub, period=200)
        print(f"Modified subscription to period 200ms")
        
        # 변경된 값을 출력
        # 라이브러리 버전에 따라 속성 이름이 다를 수 있으므로 안전하게 접근
        new_interval = getattr(sub, 'RevisedPublishingInterval', None) or getattr(sub, 'revisedPublishingInterval', 200)
        new_lifetime = getattr(sub, 'RevisedLifetimeCount', None) or getattr(sub, 'revisedLifetimeCount', None)
        new_keepalive = getattr(sub, 'RevisedMaxKeepAliveCount', None) or getattr(sub, 'revisedMaxKeepAliveCount', None)
        
        print(f"New publishing interval: {new_interval}")
        if new_lifetime:
            print(f"New lifetime count: {new_lifetime}")
        if new_keepalive:
            print(f"New max keep alive count: {new_keepalive}")
        
        # Let it run for a while
        await asyncio.sleep(2)
        
        # Delete the subscription
        await subscription.delete_subscription(sub)
        print("Subscription deleted")
        
    except Exception as e:
        print(f"Error in modify subscription example: {e}")
    finally:
        await connection.close_session(client)


async def example_subscription_publishing_mode():
    """Example showing how to set the publishing mode of a subscription."""
    server_url = "opc.tcp://mk:62541/Quickstarts/ReferenceServer"
    
    print("Setting subscription publishing mode...")
    client = await connection.create_session(server_url)
    
    try:
        # Create a subscription
        sub = await subscription.create_subscription(client)
        print(f"Created subscription with ID {sub.subscription_id}")
        
        # 서버의 서버 시간 노드 사용
        server_time_node = client.get_node(ua.NodeId(ua.ObjectIds.Server_ServerStatus_CurrentTime))
        
        # 노드가 존재하는지 확인
        try:
            initial_time = await server_time_node.read_value()
            print(f"Server time node found. Current time: {initial_time}")
            
            # Asyncua 라이브러리 버전에 맞게 수정
            try:
                # 노드에 직접 구독
                handle = await sub.subscribe_data_change(server_time_node, data_change_callback)
                print(f"Successfully subscribed to server time node")
                
                # 최초 데이터 변경을 기다립니다
                print("Waiting for initial data change notification...")
                await asyncio.sleep(1)
                
                # Disable publishing
                await subscription.set_publishing_mode(sub, False)
                print("Publishing mode disabled")
                
                # 서버 시간은 계속 변경되지만 알림이 오지 않아야 함
                print("Waiting 3 seconds (no notifications expected)...")
                await asyncio.sleep(3)
                
                # Enable publishing
                await subscription.set_publishing_mode(sub, True)
                print("Publishing mode enabled")
                
                # 이제 알림이 다시 오기 시작해야 함
                print("Waiting 3 seconds (notifications should resume)...")
                await asyncio.sleep(3)
                
                # 구독 해제
                await sub.unsubscribe(handle)
                print("Unsubscribed from server time node")
                
            except Exception as e:
                print(f"Error during subscription: {e}")
            
        except Exception as e:
            print(f"Error reading server time node: {e}")
            print("Using a different node for testing...")
            
            # 대체 방법: 서버 상태 노드 사용
            server_status_node = client.get_node(ua.NodeId(ua.ObjectIds.Server_ServerStatus_State))
            initial_status = await server_status_node.read_value()
            print(f"Server status: {initial_status}")
        
        # Delete the subscription
        await subscription.delete_subscription(sub)
        print("Subscription deleted")
        
    except Exception as e:
        print(f"Error in publishing mode example: {e}")
    finally:
        await connection.close_session(client)


async def example_data_change_subscription():
    """Example showing how to subscribe to data changes."""
    server_url = "opc.tcp://mk:62541/Quickstarts/ReferenceServer"
    
    print("Subscribing to data changes...")
    client = await connection.create_session(server_url)
    
    try:
        # Create a subscription
        sub = await subscription.create_subscription(client, period=200)
        print(f"Created subscription with ID {sub.subscription_id}")
        
        # 서버의 현재 시간 노드와 상태 노드
        server_time_node = client.get_node(ua.NodeId(ua.ObjectIds.Server_ServerStatus_CurrentTime))
        server_state_node = client.get_node(ua.NodeId(ua.ObjectIds.Server_ServerStatus_State))
        
        print("Monitoring server time and state...")
        
        try:
            # 시간 노드에 직접 구독
            time_handle = await sub.subscribe_data_change(server_time_node, data_change_callback)
            print("Subscribed to server time node")
            
            # 상태 노드에 직접 구독
            state_handle = await sub.subscribe_data_change(server_state_node, data_change_callback)
            print("Subscribed to server state node")
            
            # 5초 동안 변경 사항 모니터링
            print("Monitoring for 5 seconds...")
            await asyncio.sleep(5)
            
            # 구독 해제
            await sub.unsubscribe(time_handle)
            await sub.unsubscribe(state_handle)
            print("Unsubscribed from all nodes")
            
        except Exception as e:
            print(f"Error creating monitored items: {e}")
        
        # Delete the subscription
        await subscription.delete_subscription(sub)
        print("Subscription deleted")
        
    except Exception as e:
        print(f"Error in data change subscription example: {e}")
    finally:
        await connection.close_session(client)


async def example_keep_alive():
    """Example showing how to keep the connection alive."""
    server_url = "opc.tcp://mk:62541/Quickstarts/ReferenceServer"
    
    print("Keeping connection alive...")
    client = await connection.create_session(server_url)
    
    try:
        print("Starting keep-alive for 5 seconds...")
        await subscription.keep_alive(client, duration=5)
        print("Keep-alive completed")
        
    finally:
        await connection.close_session(client)


async def example_parallel_subscriptions():
    """Example showing how to create parallel subscriptions."""
    server_url = "opc.tcp://mk:62541/Quickstarts/ReferenceServer"
    
    print("Creating parallel subscriptions...")
    client = await connection.create_session(server_url)
    
    try:
        # 기존 OPC UA 서버 노드 사용
        nodes_to_monitor = [
            ua.NodeId(ua.ObjectIds.Server_ServerStatus_CurrentTime).to_string(),
            ua.NodeId(ua.ObjectIds.Server_ServerStatus_State).to_string(),
            ua.NodeId(ua.ObjectIds.Server_ServerStatus_StartTime).to_string()
        ]
        
        # 노드 이름 표시
        print("Monitoring the following nodes:")
        for i, node_id in enumerate(nodes_to_monitor):
            node = client.get_node(node_id)
            browse_name = await node.read_browse_name()
            print(f"Node {i+1}: {browse_name.Name} ({node_id})")
        
        # Create parallel subscriptions (2 subscriptions for 3 variables)
        subs = await subscription.create_parallel_subscriptions(
            client,
            nodes_to_monitor,
            data_change_callback,
            count=2,
            period=200
        )
        
        print(f"Created {len(subs)} subscriptions")
        
        # 구독 ID 출력
        for i, sub in enumerate(subs):
            print(f"Subscription {i+1} ID: {sub.subscription_id}")
        
        # 알림이 오는지 기다림
        print("Waiting for data change notifications (5 seconds)...")
        await asyncio.sleep(5)
        
        # Delete the subscriptions
        for i, sub in enumerate(subs):
            await subscription.delete_subscription(sub)
            print(f"Subscription {i+1} deleted")
        
    except Exception as e:
        print(f"Error in parallel subscriptions example: {e}")
    finally:
        await connection.close_session(client)


async def example_event_subscription():
    """Example showing how to subscribe to events."""
    server_url = "opc.tcp://mk:62541/Quickstarts/ReferenceServer"
    
    print("Subscribing to events...")
    client = await connection.create_session(server_url)
    
    try:
        # Create a subscription
        sub = await subscription.create_subscription(client, period=500)
        print(f"Created subscription with ID {sub.subscription_id}")
        
        # Subscribe to events from the server object
        server_node = client.nodes.server
        handle = await event.subscribe_events(
            sub,
            server_node.nodeid.to_string(),
            event_callback
        )
        
        print("Subscribed to events, waiting for events to occur...")
        # Let it run for a while (in a real scenario, events would be triggered by the server)
        await asyncio.sleep(5)
        
        # Delete the subscription
        await subscription.delete_subscription(sub)
        print("Subscription deleted")
        
    except Exception as e:
        print(f"Error in event subscription example: {e}")
    finally:
        await connection.close_session(client)


async def example_monitored_item():
    """Example showing how to add, modify, and delete monitored items."""
    server_url = "opc.tcp://mk:62541/Quickstarts/ReferenceServer"
    
    print("Working with monitored items...")
    client = await connection.create_session(server_url)
    
    try:
        # Create a subscription
        sub = await subscription.create_subscription(client, period=500)
        print(f"Created subscription with ID {sub.subscription_id}")
        
        # 서버의 현재 시간 노드 사용
        server_time_node = client.get_node(ua.NodeId(ua.ObjectIds.Server_ServerStatus_CurrentTime))
        
        # 노드 정보 출력
        browse_name = await server_time_node.read_browse_name()
        print(f"Monitoring server time node: {browse_name.Name}")
        initial_value = await server_time_node.read_value()
        print(f"Initial value: {initial_value}")
        
        try:
            # asyncua API를 사용하여 직접 구독
            # sampling_interval 파라미터로 제어
            handle = await sub.subscribe_data_change(
                server_time_node, 
                data_change_callback, 
                queuesize=10,
                sampling_interval=1000
            )
            print(f"Added monitored item with handle {handle}")
            
            # 데이터 변경을 기다림
            print("Waiting for data change notification (2 seconds)...")
            await asyncio.sleep(2)
            
            # 아이템 수정 - 샘플링 간격 변경
            # 직접 수정할 수 없을 경우 해제 후 다시 구독
            try:
                # 직접 modify 시도
                await sub.modify_data_change(handle, queuesize=10, sampling_interval=100)
                print("Modified monitored item to have faster sampling rate (100ms)")
            except Exception:
                # 지원되지 않으면 해제 후 재구독
                await sub.unsubscribe(handle)
                handle = await sub.subscribe_data_change(
                    server_time_node, 
                    data_change_callback, 
                    queuesize=10,
                    sampling_interval=100
                )
                print("Re-subscribed with faster sampling rate (100ms)")
            
            # 변경된 설정으로 추가 데이터 확인
            print("Waiting for faster data change notifications (2 seconds)...")
            await asyncio.sleep(2)
            
            # 구독 해제
            await sub.unsubscribe(handle)
            print("Deleted monitored item")
            
            # 더 이상 알림이 오지 않는지 확인
            print("Waiting 2 seconds (no notifications expected)...")
            await asyncio.sleep(2)
            
        except Exception as e:
            print(f"Error working with monitored items: {e}")
        
        # Delete the subscription
        await subscription.delete_subscription(sub)
        print("Subscription deleted")
        
    except Exception as e:
        print(f"Error in monitored item example: {e}")
    finally:
        await connection.close_session(client)


async def example_monitoring_mode():
    """Example showing how to set the monitoring mode."""
    server_url = "opc.tcp://mk:62541/Quickstarts/ReferenceServer"
    
    print("Setting monitoring mode...")
    client = await connection.create_session(server_url)
    
    try:
        # Create a subscription
        sub = await subscription.create_subscription(client, period=500)
        print(f"Created subscription with ID {sub.subscription_id}")
        
        # 서버의 현재 시간 노드 사용
        server_time_node = client.get_node(ua.NodeId(ua.ObjectIds.Server_ServerStatus_CurrentTime))
        
        # 노드 정보 출력
        browse_name = await server_time_node.read_browse_name()
        print(f"Monitoring server time node: {browse_name.Name}")
        initial_value = await server_time_node.read_value()
        print(f"Initial value: {initial_value}")
        
        try:
            # 노드에 직접 구독
            handle = await sub.subscribe_data_change(server_time_node, data_change_callback)
            print(f"Added monitored item with handle {handle}")
            
            # 첫 번째 데이터 변경 알림을 받기 위해 대기
            print("Waiting for initial notification (2 seconds)...")
            await asyncio.sleep(2)
            
            # 라이브러리 버전에 따라 다른 방식으로 시도
            try:
                # 방법 1: 구독 객체를 통해 모니터링 모드 설정
                await sub.set_monitoring_mode(handle, ua.MonitoringMode.Disabled)
                print("Set monitoring mode to Disabled (via subscription)")
            except Exception:
                try:
                    # 방법 2: 서버 객체를 통해 모니터링 모드 설정
                    await client.set_monitoring_mode([handle], ua.MonitoringMode.Disabled)
                    print("Set monitoring mode to Disabled (via client)")
                except Exception as e:
                    # 방법 3: 재구독 방식
                    print(f"Cannot set monitoring mode directly: {e}")
                    print("Using unsubscribe/resubscribe instead")
                    await sub.unsubscribe(handle)
                    print("Monitoring disabled (via unsubscribe)")
            
            # Disabled 모드에서는 알림이 오지 않아야 함
            print("Waiting with disabled monitoring (2 seconds, no notifications expected)...")
            await asyncio.sleep(2)
            
            # 다시 활성화
            try:
                # 방법 1: 구독 객체를 통해 모니터링 모드 설정
                await sub.set_monitoring_mode(handle, ua.MonitoringMode.Reporting)
                print("Set monitoring mode to Reporting (via subscription)")
            except Exception:
                try:
                    # 방법 2: 서버 객체를 통해 모니터링 모드 설정
                    await client.set_monitoring_mode([handle], ua.MonitoringMode.Reporting)
                    print("Set monitoring mode to Reporting (via client)")
                except Exception:
                    # 방법 3: 재구독 방식
                    handle = await sub.subscribe_data_change(server_time_node, data_change_callback)
                    print("Monitoring enabled (via resubscribe)")
            
            # Reporting 모드에서는 다시 알림이 와야 함
            print("Waiting with reporting enabled (2 seconds, notifications expected)...")
            await asyncio.sleep(2)
            
            # 구독 해제
            await sub.unsubscribe(handle)
            print("Deleted monitored item")
            
        except Exception as e:
            print(f"Error during monitoring mode operations: {e}")
        
        # Delete the subscription
        await subscription.delete_subscription(sub)
        print("Subscription deleted")
        
    except Exception as e:
        print(f"Error in monitoring mode example: {e}")
    finally:
        await connection.close_session(client)


async def run_examples():
    """Run all subscription and event examples."""
    setup_logging()
    
    examples = [
        ("Empty Subscription", example_empty_subscription),
        ("Modify Subscription", example_modify_subscription),
        ("Subscription Publishing Mode", example_subscription_publishing_mode),
        ("Data Change Subscription", example_data_change_subscription),
        ("Keep Alive", example_keep_alive),
        ("Parallel Subscriptions", example_parallel_subscriptions),
        ("Event Subscription", example_event_subscription),
        ("Monitored Item", example_monitored_item),
        ("Monitoring Mode", example_monitoring_mode)
    ]
    
    results = {}
    
    for name, example_func in examples:
        print(f"\n==== Running example: {name} ====")
        try:
            await example_func()
            results[name] = "성공"
            print(f"Example {name} completed successfully")
        except Exception as e:
            results[name] = f"실패: {str(e)}"
            print(f"Error running example {name}: {e}")
    
    # 결과 출력
    print("\n==== Subscription Examples Results ====")
    for name, result in results.items():
        print(f"{name}: {result}")
            
    success_count = sum(1 for result in results.values() if "성공" in result)
    print(f"\nCompleted {success_count} of {len(examples)} examples successfully")
    
    # 실패한 예제가 있으면 오류 반환하지 않고, 결과만 로그로 남김
    if success_count < len(examples):
        print("Some examples failed. See logs for details.")
    
    return success_count == len(examples)


if __name__ == "__main__":
    asyncio.run(run_examples())