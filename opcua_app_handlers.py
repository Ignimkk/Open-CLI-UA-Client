"""
OPC UA 클라이언트 애플리케이션 핸들러

이 모듈은 OPC UA 서버와의 상호작용을 위한 다양한 핸들러 함수들을 제공합니다.
"""

#!/usr/bin/env python3
import asyncio
import logging
import sys
import os
import time
import json
import inspect
import traceback
from typing import Optional, List, Dict, Any, Union, Tuple, Callable
from asyncua import ua, Client
import datetime

# 라이브러리 경로 추가
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

# OPC UA 클라이언트 모듈 가져오기
from opcua_client import connection
from opcua_client import client
from opcua_client import node
from opcua_client import method
from opcua_client import subscription
from opcua_client import event
from opcua_client import utils
from asyncua.ua import NodeId, NodeClass, DataChangeNotification, MonitoringMode, VariantType, DataValue, Variant
from asyncua.common.subscription import SubscriptionItemData
from asyncua.common.node import Node as AsyncuaNode
from asyncua.ua.uaerrors import UaStatusCodeError

# Configure logging
logger = logging.getLogger(__name__)

# Global variables
SERVER_URL = "opc.tcp://mk:62541/Quickstarts/ReferenceServer"
active_connection = None
active_client = None
active_subscriptions = {}
subscription_counter = 0

# Data change notification handler
async def data_change_notification(subscription_id, node, value, data):
    """Handle data change notification from subscribed nodes."""
    node_name = await node.read_browse_name()
    logging.info(f"Subscription {subscription_id}: {node_name} = {value}")
    print(f"Data change notification from {node_name}: {value}")

# 메뉴 출력 함수
def print_menu():
    """Print the application menu."""
    print("\n=== OPC UA Client Application Menu ===")
    print("1. Connect to OPC UA Server")
    print("2. Disconnect from OPC UA Server")
    print("3. Read Node Value")
    print("4. Write Node Value")
    print("5. Browse Server Nodes")
    print("6. Create Subscription")
    print("7. Modify Subscription")
    print("8. Subscribe to Data Change")
    print("9. Set Publishing Mode")
    print("10. Delete Subscription")
    print("11. Exit")
    print("=====================================")


async def handle_user_choice(choice: int):
    """Handle the user's menu choice."""
    choice_handlers = {
        1: handle_connect,
        2: handle_disconnect,
        3: handle_read_node,
        4: handle_write_node,
        5: handle_browse_nodes,
        6: handle_create_subscription,
        7: handle_modify_subscription,
        8: handle_subscribe_data_change,
        9: handle_set_publishing_mode, 
        10: handle_delete_subscription
    }
    
    if choice in choice_handlers:
        await check_connection(choice)
        await choice_handlers[choice]()
    else:
        print("Invalid choice. Please select a number between 1 and 11.")


async def check_connection(choice: int):
    """Check if connection is required for the selected choice."""
    global active_connection, active_client
    
    # Choice 1 is for connecting, so we skip the check
    if choice == 1:
        return
    
    if active_connection is None or active_client is None:
        logging.warning("Not connected to any server")
        print("You must connect to a server first (Option 1)")
        await handle_connect()


async def handle_connect():
    """Handle connecting to the OPC UA server."""
    global active_connection, active_client, SERVER_URL
    
    if active_connection is not None:
        print(f"Already connected to {SERVER_URL}")
        return
    
    try:
        # Allow user to specify a server URL or use the default
        user_url = input(f"Enter server URL (or press Enter for default {SERVER_URL}): ")
        if user_url.strip():
            SERVER_URL = user_url
        
        print(f"Connecting to {SERVER_URL}...")
        active_connection = await connection.create_session(SERVER_URL)
        
        # Test connection by reading server time
        server_time_node = active_connection.get_node(ua.NodeId(2258, 0))  # Server current time node
        server_time = await server_time_node.read_value()
        
        ns_node = active_connection.get_node(ua.NodeId(2255, 0))  # NamespaceArray node
        namespaces = await ns_node.read_value()
        
        print(f"Connected to {SERVER_URL}")
        print(f"Server time: {server_time}")
        print(f"Server has {len(namespaces)} namespaces")
        
        logging.info(f"Connected to {SERVER_URL}")
        
    except Exception as e:
        logging.error(f"Connection failed: {e}")
        print(f"Failed to connect: {e}")
        active_connection = None
        active_client = None


async def handle_disconnect():
    """Handle disconnecting from the OPC UA server."""
    global active_connection, active_client, active_subscriptions
    
    if active_connection is None:
        print("Not connected to any server")
        return
    
    try:
        # Clean up any active subscriptions
        for sub_id, (sub, _) in list(active_subscriptions.items()):
            try:
                print(f"Deleting subscription {sub_id}...")
                await sub.delete()
                del active_subscriptions[sub_id]
            except Exception as e:
                logging.error(f"Error deleting subscription {sub_id}: {e}")
        
        # Disconnect from server
        await connection.close_session(active_connection)
        print(f"Disconnected from {SERVER_URL}")
        logging.info(f"Disconnected from {SERVER_URL}")
        
        # Reset connection objects
        active_connection = None
        active_client = None
        active_subscriptions = {}
        
    except Exception as e:
        logging.error(f"Disconnect error: {e}")
        print(f"Error during disconnect: {e}")


async def handle_browse_nodes():
    """Handle browsing for nodes on the server."""
    if active_connection is None:
        return
    
    try:
        # 노드 선택 방식 제공
        print("\n=== Browse Nodes ===")
        print("1. Browse single level")
        print("2. Browse recursively")
        print("3. Find nodes by name")
        option = input("\nSelect option [1]: ") or "1"
        
        if option == "1":
            # 단일 레벨 탐색
            node_id_input = input("Enter starting NodeId (or press Enter for root): ")
            
            if not node_id_input:
                node_id_input = None  # Use None for root node
            
            # Browse for child nodes
            print(f"Browsing nodes under {node_id_input or 'root'}...")
            children = await node.browse_node(active_connection, node_id_input)
            
            if not children:
                print("No child nodes found")
                return
            
            print(f"Found {len(children)} child nodes:")
            for i, child in enumerate(children, 1):
                browse_name = await child.read_browse_name()
                display_name = await child.read_display_name()
                node_class = await child.read_node_class()
                
                print(f"{i}. NodeId: {child.nodeid}")
                print(f"   BrowseName: {browse_name.Name}")
                print(f"   DisplayName: {display_name.Text}")
                print(f"   NodeClass: {node_class.name}")
                print("---")
                
        elif option == "2":
            # 재귀적 탐색
            node_id_input = input("Enter starting NodeId (or press Enter for root): ")
            
            if not node_id_input:
                node_id_input = None
                
            # 탐색 깊이 입력
            max_depth = int(input("Enter max depth (1-5) [2]: ") or "2")
            max_depth = max(1, min(max_depth, 5))  # 1-5 사이로 제한
            
            print(f"Browsing nodes under {node_id_input or 'root'} with depth {max_depth}...")
            tree = await node.browse_nodes_recursive(active_connection, node_id_input, max_depth)
            
            # 트리 형태로 출력
            print("Node hierarchy:")
            await _print_node_tree(tree)
            
        elif option == "3":
            # 이름으로 노드 검색
            name_pattern = input("Enter name pattern to search for: ")
            if not name_pattern:
                print("Search pattern is required")
                return
                
            start_node = input("Enter starting NodeId (or press Enter for root): ") or None
            case_sensitive = input("Case sensitive search? (y/n) [n]: ").lower() == 'y'
            
            print(f"Searching for nodes containing '{name_pattern}'...")
            nodes = await node.find_nodes_by_name(
                active_connection, 
                name_pattern, 
                start_node, 
                case_sensitive
            )
            
            if not nodes:
                print("No matching nodes found")
                return
                
            print(f"Found {len(nodes)} matching nodes:")
            for i, found_node in enumerate(nodes, 1):
                try:
                    display_name = await found_node.read_display_name()
                    node_class = await found_node.read_node_class()
                    print(f"{i}. {display_name.Text} ({found_node.nodeid}) - {node_class.name}")
                except Exception as e:
                    print(f"{i}. {found_node.nodeid} - Error: {e}")
        else:
            print("Invalid option")
            
        logging.info(f"Browsed nodes with option {option}")
        
    except Exception as e:
        logging.error(f"Error browsing nodes: {e}")
        print(f"Failed to browse nodes: {e}")


async def _print_node_tree(node_info, indent=0):
    """노드 트리를 계층적으로 출력"""
    # 현재 노드 출력
    print(f"{' ' * indent}├─ {node_info['DisplayName']} ({node_info['NodeId']}) - {node_info['NodeClass']}")
    
    # 자식 노드들을 재귀적으로 출력
    for child in node_info.get('Children', []):
        await _print_node_tree(child, indent + 2)


async def handle_read_node():
    """Handle reading a node's value."""
    if active_connection is None:
        return
    
    try:
        # 노드 값 읽기 방식 제공
        print("\n=== Read Node Value ===")
        print("1. Read Value attribute")
        print("2. Read specific attribute")
        print("3. Read all attributes")
        option = input("\nSelect option [1]: ") or "1"
        
        # Get node identifier from user
        node_id_input = input("Enter the NodeId (e.g., 'ns=1;i=1001' or 'i=2258'): ")
        
        if node_id_input.lower() == 'server time':
            # Special case for server time
            server_time_node = active_connection.get_node(ua.NodeId(2258, 0))  # Server current time node
            server_time = await server_time_node.read_value()
            print(f"Server time: {server_time}")
            return
            
        if option == "1":
            # 값 속성 읽기
            value = await node.read_node_attribute(active_connection, node_id_input)
            print(f"Node value: {value}")
            
        elif option == "2":
            # 특정 속성 읽기
            print("\nAvailable attributes:")
            for name, attr_id in [
                ("NodeId", ua.AttributeIds.NodeId),
                ("NodeClass", ua.AttributeIds.NodeClass),
                ("BrowseName", ua.AttributeIds.BrowseName),
                ("DisplayName", ua.AttributeIds.DisplayName),
                ("Description", ua.AttributeIds.Description),
                ("Value", ua.AttributeIds.Value),
                ("DataType", ua.AttributeIds.DataType),
                ("AccessLevel", ua.AttributeIds.AccessLevel),
                ("UserAccessLevel", ua.AttributeIds.UserAccessLevel)
            ]:
                print(f"{attr_id.value}: {name}")
                
            attr_id_input = input("Enter attribute ID [13 for Value]: ") or "13"
            try:
                attr_id = ua.AttributeIds(int(attr_id_input))
                attr_value = await node.read_node_attribute(active_connection, node_id_input, attr_id)
                
                print(f"Attribute value: {attr_value}")
            except ValueError:
                print(f"Invalid attribute ID: {attr_id_input}")
                
        elif option == "3":
            # 모든 속성 읽기
            attributes = await node.get_all_node_attributes(active_connection, node_id_input)
            
            if not attributes:
                print("No attributes available or accessible")
                return
                
            print(f"\nAttributes for node {node_id_input}:")
            for name, value in attributes.items():
                # 값이 너무 길면 요약
                value_str = str(value)
                if len(value_str) > 100:
                    value_str = f"{value_str[:100]}... [내용 생략]"
                print(f"{name}: {value_str}")
        else:
            print("Invalid option")
            
        logging.info(f"Read node {node_id_input} with option {option}")
        
    except Exception as e:
        logging.error(f"Error reading node: {e}")
        print(f"Failed to read node: {e}")


async def handle_write_node():
    """Handle writing a value to a node."""
    if active_connection is None:
        return
    
    try:
        # Get node identifier and value from user
        node_id_input = input("Enter the NodeId (e.g., 'ns=1;i=1001'): ")
        value_input = input("Enter the value to write: ")
        data_type = input("Enter the data type (int, float, bool, string) [default: string]: ").lower()
        
        # Convert input to the specified data type
        if data_type == "int":
            value = int(value_input)
        elif data_type == "float":
            value = float(value_input)
        elif data_type == "bool":
            value = value_input.lower() in ("true", "yes", "1", "y")
        else:  # Default to string
            value = value_input
            
        # Write the value to the node
        await node.write_node_attribute(active_connection, node_id_input, value)
        
        print(f"Successfully wrote {value} to node {node_id_input}")
        logging.info(f"Wrote value {value} to node {node_id_input}")
        
    except Exception as e:
        logging.error(f"Error writing to node: {e}")
        print(f"Failed to write to node: {e}")


async def handle_call_method():
    """Handle calling a method on the server."""
    if active_connection is None:
        return
    
    try:
        print("\n=== Call Method ===")
        print("1. Direct method call")
        print("2. Browse and find methods")
        option = input("\nSelect option [1]: ") or "1"
        
        if option == "1":
            # 직접 메서드 호출
            object_id_input = input("Enter object NodeId (parent node): ")
            method_id_input = input("Enter method NodeId: ")
            
            # 메서드 정보 가져오기
            try:
                method_info = await method.get_method_info(active_connection, method_id_input)
                
                # 메서드 정보 출력
                print(f"\nMethod: {method_info.get('DisplayName')}")
                
                input_args_info = method_info.get('InputArguments', [])
                if input_args_info:
                    print("\nInput Arguments:")
                    for i, arg in enumerate(input_args_info, 1):
                        arg_desc = f" - {arg.get('Description')}" if arg.get('Description') else ""
                        print(f"{i}. {arg.get('Name')} ({arg.get('DataType')}){arg_desc}")
                else:
                    print("\nNo input arguments required")
                    
                output_args_info = method_info.get('OutputArguments', [])
                if output_args_info:
                    print("\nOutput Arguments:")
                    for i, arg in enumerate(output_args_info, 1):
                        arg_desc = f" - {arg.get('Description')}" if arg.get('Description') else ""
                        print(f"{i}. {arg.get('Name')} ({arg.get('DataType')}){arg_desc}")
            except Exception as e:
                print(f"Failed to get method info: {e}")
            
            # 입력 인자 수집
            has_inputs = input("Does this method require input arguments? (y/n): ").lower() == 'y'
            input_args = []
            
            if has_inputs:
                num_args = int(input("How many input arguments? "))
                for i in range(num_args):
                    arg_type = input(f"Argument {i+1} type (int, float, bool, string): ").lower()
                    arg_value = input(f"Argument {i+1} value: ")
                    
                    # Convert input to the specified data type
                    if arg_type == "int":
                        value = int(arg_value)
                    elif arg_type == "float":
                        value = float(arg_value)
                    elif arg_type == "bool":
                        value = arg_value.lower() in ("true", "yes", "1", "y")
                    else:  # Default to string
                        value = arg_value
                        
                    input_args.append(value)
            
            # Call the method
            print(f"Calling method {method_id_input} on object {object_id_input}...")
            result = await method.call_method_with_params(active_connection, object_id_input, method_id_input, input_args)
            
            print(f"Method call result: {result}")
            
        elif option == "2":
            # 메서드 찾기
            parent_id = input("Enter starting node to find methods (default is Objects): ") or "i=85"
            
            print(f"Searching for methods under {parent_id}...")
            methods = await method.find_methods(active_connection, parent_id)
            
            if not methods:
                print("No methods found")
                return
                
            print(f"\nFound {len(methods)} methods:")
            for i, m in enumerate(methods, 1):
                print(f"{i}. {m['DisplayName']} ({m['NodeId']})")
                print(f"   Parent: {m['ParentId']}")
                
            # 메서드 선택
            selection = input("\nSelect method to call (number) or 0 to cancel: ")
            if selection == "0" or not selection:
                return
                
            try:
                selected = int(selection) - 1
                if selected < 0 or selected >= len(methods):
                    print("Invalid selection")
                    return
                    
                selected_method = methods[selected]
                method_id = selected_method['NodeId']
                parent_id = selected_method['ParentId']
                
                # 메서드 정보 가져오기
                method_info = await method.get_method_info(active_connection, method_id)
                
                # 메서드 정보 출력
                print(f"\nMethod: {method_info.get('DisplayName')}")
                
                input_args_info = method_info.get('InputArguments', [])
                if input_args_info:
                    print("\nInput Arguments:")
                    for i, arg in enumerate(input_args_info, 1):
                        arg_desc = f" - {arg.get('Description')}" if arg.get('Description') else ""
                        print(f"{i}. {arg.get('Name')} ({arg.get('DataType')}){arg_desc}")
                else:
                    print("\nNo input arguments required")
                    
                # 입력 값 수집
                input_values = []
                for i, arg in enumerate(input_args_info, 1):
                    arg_name = arg.get('Name', f'Argument {i}')
                    arg_type = arg.get('DataType', 'String')
                    arg_value = input(f"Enter value for {arg_name} ({arg_type}): ")
                    input_values.append(arg_value)
                    
                # 메서드 호출 (자동 타입 변환)
                result = await method.call_method_with_typed_params(
                    active_connection, 
                    parent_id, 
                    method_id, 
                    input_values
                )
                
                # 결과 출력
                if isinstance(result, list) and all(isinstance(item, dict) for item in result):
                    # 구조화된 결과
                    print("\nMethod result:")
                    for i, out in enumerate(result, 1):
                        print(f"{i}. {out.get('Name')}: {out.get('Value')} ({out.get('DataType')})")
                else:
                    print(f"\nMethod call result: {result}")
                
            except ValueError:
                print("Invalid input")
                return
                
        else:
            print("Invalid option")
            
        logging.info(f"Called method with option {option}")
        
    except Exception as e:
        logging.error(f"Error calling method: {e}")
        print(f"Failed to call method: {e}")


async def handle_create_subscription():
    """Handle creating a subscription."""
    global active_connection, active_subscriptions, subscription_counter
    
    if active_connection is None:
        return
    
    try:
        print("\n=== Create Subscription ===")
        # 구독 파라미터 수집
        publishing_interval = float(input("Enter publishing interval in ms [1000]: ") or "1000")
        lifetime_count = int(input("Enter lifetime count [2400]: ") or "2400")
        max_keep_alive_count = int(input("Enter max keep alive count [10]: ") or "10")
        priority = int(input("Enter priority [0]: ") or "0")
        
        # 개선된 구독 생성 함수 사용
        sub = await subscription.create_subscription(
            active_connection,
            publishing_interval,
            lifetime_count,
            max_keep_alive_count,
            priority
        )
        
        # 구독 ID 생성 및 저장
        subscription_counter += 1
        active_subscriptions[subscription_counter] = (sub, [])
        
        print(f"Created subscription with ID: {subscription_counter}")
        print(f"Server-assigned subscription ID: {sub.subscription_id}")
        
        # 모니터링 항목 추가 여부
        add_items = input("Add monitored items now? (y/n): ").lower() == 'y'
        if add_items:
            await handle_create_monitored_item()
        
        logging.info(f"Created subscription {subscription_counter} with server ID {sub.subscription_id}")
        
    except Exception as e:
        logging.error(f"Error creating subscription: {e}")
        print(f"Failed to create subscription: {e}")


async def handle_create_monitored_item():
    """Handle creating a monitored item on an active subscription."""
    global active_connection, active_subscriptions
    
    if not active_connection:
        print("Not connected to any server")
        return
    
    # Check connection status
    try:
        # Simple check to verify connection is still active
        await active_connection.get_namespace_array()
    except Exception as conn_err:
        print(f"Connection issue detected: {conn_err}")
        reconnect = input("Try to reconnect? (y/n): ").lower() == 'y'
        if reconnect:
            try:
                # Try to close existing connection gracefully
                try:
                    await connection.close_session(active_connection)
                except:
                    pass
                
                # Reconnect to server
                print(f"Reconnecting to {SERVER_URL}...")
                active_connection = await connection.create_session(SERVER_URL)
                print(f"Reconnected successfully")
                logging.info(f"Reconnected to {SERVER_URL}")
                
                # User might need to recreate subscriptions
                if active_subscriptions:
                    recreate = input("Previous subscriptions may be invalid. Create a new subscription? (y/n): ").lower() == 'y'
                    if recreate:
                        await handle_create_subscription()
                        return
            except Exception as re_err:
                print(f"Failed to reconnect: {re_err}")
                logging.error(f"Failed to reconnect: {re_err}")
                return
        else:
            return
    
    # List active subscriptions
    if not active_subscriptions:
        print("No active subscriptions. Create a subscription first.")
        create_new = input("Create a new subscription now? (y/n): ").lower() == 'y'
        if create_new:
            await handle_create_subscription()
        else:
            return
        
        # Check if the subscription was created successfully
        if not active_subscriptions:
            return
    
    print("\nActive subscriptions:")
    for sub_id, (sub, items) in active_subscriptions.items():
        print(f"{sub_id}. Server ID: {sub.subscription_id} (Items: {len(items)})")
    
    try:
        sub_id = int(input("\nSelect subscription ID: "))
        if sub_id not in active_subscriptions:
            print("Invalid subscription selection")
            return
        
        sub, monitored_items = active_subscriptions[sub_id]
    except ValueError:
        print("Invalid subscription ID")
        return
    
    # Get node to monitor
    node_id = input("Enter node ID to monitor: ")
    if not node_id:
        print("Node ID is required")
        return
    
    # Validate node exists before trying to subscribe
    try:
        test_node = active_connection.get_node(node_id)
        try:
            # Attempt to read something from the node to verify it's accessible
            await test_node.read_browse_name()
            print(f"Node {node_id} verified as accessible")
        except Exception as browse_err:
            print(f"Warning: Node exists but might not be fully accessible: {browse_err}")
            print("Some nodes might be writable but not readable, or have restricted access")
            if input("Continue anyway? (y/n): ").lower() != 'y':
                return
    except Exception as node_err:
        print(f"Error: Could not access node {node_id}: {node_err}")
        if input("Continue anyway? (y/n): ").lower() != 'y':
            return
    
    # Get sampling interval
    try:
        sampling_interval = float(input("Enter sampling interval in ms [100]: ") or "100")
    except ValueError:
        print("Invalid sampling interval, using default value of 100ms")
        sampling_interval = 100.0
    
    # Advanced options
    store_values = input("Store values for analysis? (y/n): ").lower() == 'y'
    max_values = 100
    if store_values:
        try:
            max_values = int(input("Maximum values to store [100]: ") or "100")
        except ValueError:
            max_values = 100
    
    # Setup handler options
    handler_options = {
        "log_changes": True,
        "store_values": store_values,
        "max_values": max_values,
        "timestamp_values": True
    }
    
    try:
        async def data_change_callback(node, value, data):
            try:
                node_id_str = str(node.nodeid)
                try:
                    display_name = await node.read_browse_name()
                    name = display_name.Name
                except:
                    name = node_id_str
                
                value_str = str(value)
                if len(value_str) > 60:
                    value_str = f"{value_str[:60]}..."
                print(f"Data change: {name} ({node_id_str}) = {value_str}")
            except Exception as e:
                print(f"Error in callback: {e}")
                logger.error(f"Error in data change callback: {e}")
        
        # Show message to user before potentially long operation
        print(f"Adding monitored item for node {node_id}...")
        
        # Subscribe to data changes
        try:
            handle = await subscription.subscribe_data_change(
                sub,
                node_id,
                data_change_callback,
                sampling_interval,
                advanced_handler_options=handler_options
            )
            
            # Store this monitored item
            monitored_items.append({
                'handle': handle,
                'node_id': node_id,
                'sampling_interval': sampling_interval,
                'handler_options': handler_options
            })
            
            print(f"Successfully created monitored item with handle {handle}")
            logging.info(f"Added monitored item for node {node_id} to subscription {sub_id}")
            
        except Exception as sub_err:
            logger.error(f"Failed to create monitored item: {sub_err}")
            print(f"Error: {sub_err}")
            
            # Check if error is related to connection issues
            if "connection" in str(sub_err).lower() or "closed" in str(sub_err).lower():
                print("Connection issue detected. The server may have disconnected.")
                reconnect = input("Try to reconnect and retry? (y/n): ").lower() == 'y'
                if reconnect:
                    try:
                        # Reconnect to server
                        try:
                            await connection.close_session(active_connection)
                        except:
                            pass
                        
                        print(f"Reconnecting to {SERVER_URL}...")
                        active_connection = await connection.create_session(SERVER_URL)
                        print(f"Reconnected successfully. Creating new subscription...")
                        
                        # Create a new subscription with same parameters
                        try:
                            # Try to get parameters from existing subscription
                            publishing_interval = 500  # Default
                            lifetime_count = 10        # Default 
                            max_keep_alive_count = 3   # Default
                            
                            new_sub = await subscription.create_subscription(
                                active_connection, 
                                publishing_interval,
                                lifetime_count, 
                                max_keep_alive_count
                            )
                            
                            # Replace old subscription with new one
                            active_subscriptions[sub_id] = (new_sub, [])
                            
                            # Try again with monitored item
                            handle = await subscription.subscribe_data_change(
                                new_sub,
                                node_id,
                                data_change_callback,
                                sampling_interval,
                                advanced_handler_options=handler_options
                            )
                            
                            # Update the monitored items list
                            monitored_items = []
                            active_subscriptions[sub_id] = (new_sub, monitored_items)
                            
                            monitored_items.append({
                                'handle': handle,
                                'node_id': node_id,
                                'sampling_interval': sampling_interval,
                                'handler_options': handler_options
                            })
                            
                            print(f"Successfully created monitored item after reconnection!")
                            logging.info(f"Added monitored item for node {node_id} after reconnection")
                            
                        except Exception as retry_err:
                            print(f"Failed to create subscription or monitored item after reconnection: {retry_err}")
                            logging.error(f"Retry failed: {retry_err}")
                            
                    except Exception as conn_err:
                        print(f"Failed to reconnect: {conn_err}")
                        logging.error(f"Reconnection failed: {conn_err}")
            
            # Check if error might be related to server limitations
            elif "limit" in str(sub_err).lower() or "capacity" in str(sub_err).lower():
                print("The server may have reached its subscription or monitored item limit.")
                print("Try removing some existing subscriptions first.")
            
            # Other potential issues
            elif "not found" in str(sub_err).lower() or "exist" in str(sub_err).lower():
                print("The node ID may not exist or may not be accessible with current permissions.")
            elif "permission" in str(sub_err).lower() or "access" in str(sub_err).lower():
                print("You may not have permission to monitor this node.")
                
    except Exception as e:
        logger.error(f"Failed to create monitored item: {e}")
        print(f"Error: {e}")
        
    # Ask if user wants to add another item
    if input("\nAdd another monitored item? (y/n): ").lower() == 'y':
        await handle_create_monitored_item()


async def handle_subscribe_data_change():
    """Handle subscribing to data changes for a node."""
    global active_connection, active_subscriptions, subscription_counter
    
    if not active_connection:
        print("Not connected to any server")
        return
    
    # Create subscription if none exists
    if not active_subscriptions:
        create_new = input("No active subscriptions. Create a new subscription? (y/n): ").lower() == 'y'
        if create_new:
            await handle_create_subscription()
        else:
            return
    
    if not active_subscriptions:
        print("Cannot proceed without a subscription")
        return
    
    # List active subscriptions
    print("\nActive subscriptions:")
    for sub_id, (sub, _) in active_subscriptions.items():
        print(f"{sub_id}. Server ID: {sub.subscription_id}")
    
    sub_choice = input("\nSelect subscription ID: ")
    try:
        sub_id = int(sub_choice)
        if sub_id not in active_subscriptions:
            print("Invalid subscription selection")
            return
        
        sub, monitored_items = active_subscriptions[sub_id]
    except (ValueError, KeyError):
        print("Invalid subscription ID")
        return
    
    # Allow multiple nodes to be monitored
    while True:
        # Get node to monitor
        node_id = input("\nEnter node ID to monitor (empty to finish): ")
        if not node_id:
            break
        
        # Get sampling interval
        try:
            sampling_interval = float(input("Enter sampling interval in ms [100]: ") or "100")
        except ValueError:
            print("Invalid sampling interval")
            continue
        
        # Advanced options
        store_values = input("Store values for analysis? (y/n): ").lower() == 'y'
        max_values = 100
        if store_values:
            try:
                max_values = int(input("Maximum values to store [100]: ") or "100")
            except ValueError:
                max_values = 100
        
        # Setup handler options
        handler_options = {
            "log_changes": True,
            "store_values": store_values,
            "max_values": max_values,
            "timestamp_values": True
        }
        
        try:
            # Define callback for data changes
            async def data_change_callback(node, value, data):
                try:
                    node_id_str = str(node.nodeid)
                    try:
                        display_name = await node.read_browse_name()
                        name = display_name.Name
                    except:
                        name = node_id_str
                        
                    value_str = str(value)
                    if len(value_str) > 60:
                        value_str = f"{value_str[:60]}..."
                    print(f"Data change: {name} ({node_id_str}) = {value_str}")
                except Exception as e:
                    print(f"Error in callback: {e}")
            
            # Subscribe to data changes
            try:
                handle = await subscription.subscribe_data_change(
                    sub,
                    node_id,
                    data_change_callback,
                    sampling_interval,
                    advanced_handler_options=handler_options
                )
                
                # Store information about this monitored item
                monitored_items.append({
                    'handle': handle,
                    'node_id': node_id,
                    'sampling_interval': sampling_interval,
                    'handler_options': handler_options
                })
                
                print(f"Successfully subscribed to data changes for {node_id}")
                logging.info(f"Added monitored item for node {node_id} to subscription {sub_id}")
                
            except Exception as e:
                logger.error(f"Failed to subscribe to data changes: {e}")
                print(f"Error subscribing to node {node_id}: {e}")
        except Exception as e:
            logger.error(f"Error setting up data change subscription: {e}")
            print(f"Error: {e}")
        
        # Ask if user wants to add more nodes
        if input("Subscribe to another node? (y/n): ").lower() != 'y':
            break
    
    print(f"Data change subscriptions configured. Changes will be printed as they occur.")


async def handle_modify_subscription():
    """Handle modifying an existing subscription."""
    global active_subscriptions
    
    if not active_subscriptions:
        print("No active subscriptions to modify")
        return
    
    try:
        print("\n=== Modify Subscription ===")
        # 구독 목록 표시
        print("Active subscriptions:")
        for sub_id, (sub, items) in active_subscriptions.items():
            print(f"{sub_id}: Server ID {sub.subscription_id} (Items: {len(items)})")
        
        # 구독 선택
        try:
            sub_id = int(input("Enter subscription ID to modify: "))
            if sub_id not in active_subscriptions:
                print(f"Subscription with ID {sub_id} not found")
                return
                
            sub, monitored_items = active_subscriptions[sub_id]
        except ValueError:
            print("Invalid subscription ID")
            return
        
        # 수정 옵션 선택
        print("\nModification options:")
        print("1. Change publishing parameters")
        print("2. Set publishing mode")
        print("3. Add monitored item")
        option = input("Select option [1]: ") or "1"
        
        if option == "1":
            # 구독 파라미터 수정
            publishing_interval = float(input("Enter new publishing interval in ms [1000]: ") or "1000")
            lifetime_count = int(input("Enter new lifetime count [2400]: ") or "2400")
            max_keep_alive_count = int(input("Enter new max keep alive count [10]: ") or "10")
            
            # 구독 수정
            result = await subscription.modify_subscription(
                sub,
                publishing_interval,
                lifetime_count,
                max_keep_alive_count
            )
            
            if result:
                print(f"Modified subscription {sub_id}")
                
                # Try to read revised values if available
                try:
                    revised_interval = getattr(sub, "revised_publishing_interval", 
                                             getattr(sub, "RevisedPublishingInterval", publishing_interval))
                    revised_lifetime = getattr(sub, "revised_lifetime_count", 
                                             getattr(sub, "RevisedLifetimeCount", lifetime_count))
                    revised_keepalive = getattr(sub, "revised_max_keep_alive_count", 
                                              getattr(sub, "RevisedMaxKeepAliveCount", max_keep_alive_count))
                    
                    print(f"New publishing interval: {revised_interval}ms")
                    print(f"New lifetime count: {revised_lifetime}")
                    print(f"New max keep alive count: {revised_keepalive}")
                except:
                    print(f"New publishing interval: {publishing_interval}ms")
                    print(f"New lifetime count: {lifetime_count}")
                    print(f"New max keep alive count: {max_keep_alive_count}")
                
                logging.info(f"Modified subscription {sub_id}")
            else:
                print(f"Failed to modify subscription {sub_id}")
                
        elif option == "2":
            # 발행 모드 설정
            mode_input = input("Enter publishing mode (enabled/disabled) [enabled]: ").lower()
            publishing_enabled = mode_input != "disabled"
            
            # 발행 모드 설정
            result = await subscription.set_publishing_mode(sub, publishing_enabled)
            
            if result:
                mode_str = "enabled" if publishing_enabled else "disabled"
                print(f"Set publishing mode for subscription {sub_id} to {mode_str}")
                logging.info(f"Set publishing mode for subscription {sub_id} to {mode_str}")
            else:
                print(f"Failed to set publishing mode for subscription {sub_id}")
            
        elif option == "3":
            # 모니터링 항목 추가 - use the existing handle_create_monitored_item functionality
            await handle_create_monitored_item()
            
        else:
            print("Invalid option")
        
    except Exception as e:
        logging.error(f"Error modifying subscription: {e}")
        print(f"Failed to modify subscription: {e}")


async def handle_delete_subscription():
    """Handle deleting a subscription."""
    global active_subscriptions
    
    if not active_subscriptions:
        print("No active subscriptions to delete")
        return
    
    try:
        print("\n=== Delete Subscription ===")
        # 구독 목록 표시
        print("Active subscriptions:")
        for sub_id, (sub, items) in active_subscriptions.items():
            print(f"{sub_id}: Server ID {sub.subscription_id} (Items: {len(items)})")
        
        # 구독 선택
        sub_id_input = input("Enter subscription ID to delete (or 'all' for all): ")
        
        if sub_id_input.lower() == 'all':
            # 모든 구독 삭제
            success_count = 0
            fail_count = 0
            
            for sub_id, (sub, _) in list(active_subscriptions.items()):
                try:
                    result = await subscription.delete_subscription(sub)
                    if result:
                        del active_subscriptions[sub_id]
                        success_count += 1
                    else:
                        fail_count += 1
                except Exception as e:
                    logging.error(f"Error deleting subscription {sub_id}: {e}")
                    fail_count += 1
                    
            print(f"Deleted {success_count} subscriptions, failed to delete {fail_count}")
            logging.info(f"Deleted {success_count} subscriptions, failed {fail_count}")
            
        else:
            # 특정 구독 삭제
            try:
                sub_id = int(sub_id_input)
                if sub_id in active_subscriptions:
                    sub, _ = active_subscriptions[sub_id]
                    result = await subscription.delete_subscription(sub)
                    
                    if result:
                        del active_subscriptions[sub_id]
                        print(f"Subscription {sub_id} deleted")
                        logging.info(f"Subscription {sub_id} deleted")
                    else:
                        print(f"Failed to delete subscription {sub_id}")
                else:
                    print(f"Subscription with ID {sub_id} not found")
            except ValueError:
                print("Invalid subscription ID")
        
    except Exception as e:
        logging.error(f"Error deleting subscription: {e}")
        print(f"Failed to delete subscription: {e}")


async def exit_application():
    """Clean up and exit the application."""
    if active_connection is not None:
        await handle_disconnect()
    logging.info("Application exited")


if __name__ == "__main__":
    print("This module should not be run directly. Run opcua_app.py instead.") 