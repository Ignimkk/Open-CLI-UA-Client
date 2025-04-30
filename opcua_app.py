#!/usr/bin/env python3
"""
OPC UA 클라이언트 애플리케이션

이 애플리케이션은 OPC UA 서버에 연결하고 다양한 작업을 수행할 수 있는 
명령줄 인터페이스(CLI)를 제공합니다.
"""

import asyncio
import logging
import sys
import os
import time
import argparse
import traceback
from typing import Optional, List, Dict, Any, Union, Tuple

from asyncua import Client, ua

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

# OPC UA 클라이언트 핸들러 모듈 가져오기
from opcua_app_handlers import (
    handle_connect, handle_disconnect, handle_read_node, 
    handle_write_node, handle_browse_nodes, handle_call_method,
    handle_create_subscription, handle_delete_subscription,
    handle_modify_subscription, handle_subscribe_data_change,
    handle_create_monitored_item, 
    check_connection, exit_application
)

# 로깅 설정 (바이너리 데이터 필터링 포함)
utils.setup_logging(logging.INFO)
logger = logging.getLogger(__name__)

DEFAULT_SERVER_URL = "opc.tcp://mk:62541/Quickstarts/ReferenceServer"

async def display_menu():
    print("\n===== OPC UA Client Application =====")
    print("1. Connect to Server")
    print("2. Disconnect from Server")
    print("3. Get Node Information")
    print("4. Read Node Value")
    print("5. Write Node Value")
    print("6. Browse Nodes")
    print("7. Search Nodes")
    print("8. Call Method")
    print("9. Create Subscription")
    print("10. Modify Subscription")
    print("11. Delete Subscription")
    print("12. Execute Example Script")
    print("13. Enter Monitoring Mode")
    print("0. Exit")
    print("====================================")
    return input("Enter your choice: ")

async def connect_to_server(client_connection=None):
    if client_connection:
        logger.info("Already connected to server")
        return client_connection
    
    url = input(f"Enter server URL [{DEFAULT_SERVER_URL}]: ") or DEFAULT_SERVER_URL
    try:
        client_connection = await connection.create_session(url)
        logger.info(f"Connected to server: {url}")
        return client_connection
    except Exception as e:
        logger.error(f"Failed to connect to server: {e}")
        return None

async def disconnect_from_server(client_connection):
    if not client_connection:
        logger.info("Not connected to any server")
        return None
    
    try:
        await connection.close_session(client_connection)
        logger.info("Disconnected from server")
        return None
    except Exception as e:
        logger.error(f"Failed to disconnect from server: {e}")
        return client_connection

async def get_node_info(client_connection):
    if not client_connection:
        logger.info("Not connected to any server")
        return
    
    try:
        node_id = input("Enter node ID (e.g. 'i=84', 'ns=1;s=MyNode'): ")
        
        # 모든 속성 정보 조회 여부 선택
        detailed = input("Get detailed attributes? (y/n): ").lower() == 'y'
        
        if detailed:
            # 모든 OPC UA 속성 조회
            attributes = await node.get_all_node_attributes(client_connection, node_id)
            
            print("\nNode Attributes:")
            for key, value in attributes.items():
                # 값이 너무 길면 요약
                value_str = str(value)
                if len(value_str) > 100:
                    value_str = f"{value_str[:100]}... [내용 생략]"
                print(f"{key}: {value_str}")
        else:
            # 기본 노드 정보만 조회
            info = await node.get_node_info(client_connection, node_id)
            
            print("\nNode Information:")
            for key, value in info.items():
                # 값이 너무 길면 요약
                value_str = str(value)
                if len(value_str) > 100:
                    value_str = f"{value_str[:100]}... [내용 생략]"
                print(f"{key}: {value_str}")
            
    except Exception as e:
        logger.error(f"Failed to get node information: {e}")

async def check_and_reconnect(client_connection, preserve_subscriptions=True):
    """
    연결 상태를 확인하고 필요한 경우 재연결합니다.
    
    Args:
        client_connection: 현재 클라이언트 연결
        preserve_subscriptions: 구독 정보를 보존할지 여부
        
    Returns:
        튜플 (연결 객체, 재연결 여부)
    """
    if not client_connection:
        logger.warning("서버에 연결되어 있지 않습니다.")
        return None, False
    
    reconnected = False
    
    try:
        # 간단한 연결 확인
        await client_connection.get_namespace_array()
        logger.debug("Connection check successful")
    except Exception as e:
        logger.warning(f"Connection check failed: {e}")
        logger.info("Attempting to reconnect...")
        
        # 재연결 시도
        try:
            # 기존 연결 닫기
            try:
                await client_connection.disconnect()
            except:
                # 이미 닫혀있을 수 있음
                pass
            
            # 다시 연결
            server_url = DEFAULT_SERVER_URL
            client_connection = await connection.create_session(server_url)
            logger.info(f"Reconnected to server: {server_url}")
            reconnected = True
        except Exception as reconnect_err:
            logger.error(f"Failed to reconnect: {reconnect_err}")
            return None, False
    
    return client_connection, reconnected

async def recreate_subscriptions(client_connection, subscription_list):
    """
    재연결 후 구독을 복구합니다.
    
    Args:
        client_connection: 새로운 클라이언트 연결
        subscription_list: 기존 구독 목록
        
    Returns:
        복구된 구독 목록
    """
    if not client_connection or not subscription_list:
        return subscription_list
    
    new_subscription_list = []
    
    for sub_info in subscription_list:
        try:
            # 기존 구독 정보 추출
            old_sub = sub_info.get('subscription')
            old_id = sub_info.get('id')
            publishing_interval = sub_info.get('publishing_interval', 500)
            lifetime_count = sub_info.get('lifetime_count', 10)
            max_keep_alive_count = sub_info.get('max_keep_alive_count', 3)
            priority = sub_info.get('priority', 0)
            monitored_items = sub_info.get('monitored_items', [])
            
            logger.info(f"Recreating subscription {old_id}...")
            
            # 새 구독 생성
            new_sub = await subscription.create_subscription(
                client_connection,
                publishing_interval,
                lifetime_count,
                max_keep_alive_count,
                priority
            )
            
            # 새 구독 정보 저장
            new_sub_info = {
                "id": new_sub.subscription_id,
                "subscription": new_sub,
                "publishing_interval": publishing_interval,
                "lifetime_count": lifetime_count,
                "max_keep_alive_count": max_keep_alive_count,
                "priority": priority,
                "monitored_items": []
            }
            
            # 모니터링 항목 복구
            for item in monitored_items:
                try:
                    node_id = item.get('node_id')
                    sampling_interval = item.get('sampling_interval', 100)
                    handler_options = item.get('handler_options', {})
                    
                    if node_id:
                        logger.info(f"Recreating monitored item for node {node_id}...")
                        
                        # 콜백 함수 정의
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
                        
                        # 새 모니터링 항목 생성
                        handle = await subscription.subscribe_data_change(
                            new_sub,
                            node_id,
                            data_change_callback,
                            sampling_interval,
                            advanced_handler_options=handler_options
                        )
                        
                        # 새 모니터링 항목 정보 저장
                        new_sub_info["monitored_items"].append({
                            "handle": handle,
                            "node_id": node_id,
                            "sampling_interval": sampling_interval,
                            "handler_options": handler_options
                        })
                        
                        logger.info(f"Successfully recreated monitored item for {node_id}")
                except Exception as item_err:
                    logger.error(f"Failed to recreate monitored item: {item_err}")
            
            new_subscription_list.append(new_sub_info)
            logger.info(f"Successfully recreated subscription with ID: {new_sub.subscription_id}")
            
        except Exception as sub_err:
            logger.error(f"Failed to recreate subscription: {sub_err}")
    
    return new_subscription_list

async def read_node_value(client_connection):
    if not client_connection:
        logger.info("Not connected to any server")
        return
    
    try:
        node_id = input("Enter node ID (e.g. 'i=84', 'ns=1;s=MyNode'): ")
        
        # 중앙 집중식 연결 확인 및 재연결 사용
        client_connection, reconnected = await check_and_reconnect(client_connection)
        if not client_connection:
            print("Connection could not be established. Please reconnect.")
            return
        
        # 노드 값 읽기
        value = await node.read_node_attribute(client_connection, node_id)
        print(f"\nNode Value: {value}")
    except Exception as e:
        logger.error(f"Failed to read node value: {e}")

async def write_node_value(client_connection):
    if not client_connection:
        logger.info("Not connected to any server")
        return
    
    try:
        node_id = input("Enter node ID (e.g. 'i=84', 'ns=1;s=MyNode'): ")
        value_type = input("Enter value type (int, float, str, bool): ")
        value_str = input("Enter value: ")
        
        # Convert string input to the appropriate type
        if value_type == "int":
            value = int(value_str)
        elif value_type == "float":
            value = float(value_str)
        elif value_type == "bool":
            value = value_str.lower() in ("yes", "true", "t", "1")
        else:
            value = value_str
        
        result = await node.write_node_attribute(client_connection, node_id, value)
        print(f"\nSuccessfully wrote value '{value}' to node {node_id}")
    except Exception as e:
        logger.error(f"Failed to write node value: {e}")
        print(f"\nFailed to write value to node {node_id}")

async def browse_nodes(client_connection):
    if not client_connection:
        logger.info("Not connected to any server")
        return
    
    try:
        node_id = input("Enter node ID to browse (default is root node): ") or None
        
        # 추가 옵션 제공
        browse_type = input("Browse type (1=Basic, 2=Recursive): ") or "1"
        
        # 연결 확인 및 재연결 시도
        try:
            # 간단한 호출로 연결 상태 확인
            await client_connection.get_namespace_array()
        except Exception as conn_err:
            logger.warning(f"Connection check failed: {conn_err}")
            logger.info("Attempting to reconnect...")
            
            # 재연결 시도
            try:
                # 기존 연결 닫기
                try:
                    await client_connection.disconnect()
                except:
                    pass
                
                # 다시 연결
                server_url = DEFAULT_SERVER_URL
                client_connection = await connection.create_session(server_url)
                logger.info(f"Reconnected to server: {server_url}")
            except Exception as reconnect_err:
                logger.error(f"Failed to reconnect: {reconnect_err}")
                return
        
        if browse_type == "1":
            # 기본 노드 탐색 (한 단계)
            children = await node.browse_node(client_connection, node_id)
            
            print(f"\nNodes under {node_id or 'root'}:")
            for i, child in enumerate(children, 1):
                browse_name = await child.read_browse_name()
                display_name = await child.read_display_name()
                node_class = await child.read_node_class()
                print(f"{i}. {display_name.Text} ({child.nodeid}) - {node_class.name}")
                
        else:
            # 재귀적 노드 탐색
            max_depth = int(input("Enter max depth (1-5): ") or "2")
            max_depth = max(1, min(max_depth, 5))  # 1-5 사이로 제한
            
            tree = await node.browse_nodes_recursive(client_connection, node_id, max_depth)
            
            # 트리 형태로 출력
            await _print_node_tree(tree)
    except Exception as e:
        logger.error(f"Failed to browse nodes: {e}")

async def _print_node_tree(node_info, indent=0):
    """노드 트리를 계층적으로 출력"""
    # 현재 노드 출력
    print(f"{' ' * indent}├─ {node_info.get('DisplayName', 'Unknown')} ({node_info.get('NodeId', 'Unknown')}) - {node_info.get('NodeClass', 'Unknown')}")
    
    # 자식 노드들을 재귀적으로 출력
    for child in node_info.get('Children', []):
        await _print_node_tree(child, indent + 2)

async def find_nodes(client_connection):
    """서버에서 노드 검색"""
    if not client_connection:
        logger.info("Not connected to any server")
        return
    
    try:
        search_term = input("Enter search term: ")
        if not search_term:
            print("Search term is required")
            return
            
        start_node = input("Enter start node ID (default is root): ") or None
        case_sensitive = input("Case sensitive? (y/n): ").lower() == 'y'
        
        print(f"\nSearching for nodes containing '{search_term}'...")
        nodes = await node.find_nodes_by_name(
            client_connection, 
            search_term, 
            start_node, 
            case_sensitive
        )
        
        if not nodes:
            print("No matching nodes found")
            return
            
        print(f"\nFound {len(nodes)} matching nodes:")
        for i, found_node in enumerate(nodes, 1):
            try:
                display_name = await found_node.read_display_name()
                node_class = await found_node.read_node_class()
                print(f"{i}. {display_name.Text} ({found_node.nodeid}) - {node_class.name}")
            except Exception as e:
                print(f"{i}. {found_node.nodeid} - Error: {e}")
    except Exception as e:
        logger.error(f"Failed to search nodes: {e}")

async def call_method(client_connection):
    if not client_connection:
        logger.info("Not connected to any server")
        return
    
    try:
        # 메서드 발견 방식 선택
        discovery_option = input("Select method discovery option (1=Direct entry, 2=Browse methods): ") or "1"
        
        if discovery_option == "2":
            # 메서드 찾기 기능 사용
            parent_node_id = input("Enter parent node ID to browse methods (default is Objects): ") or "i=85"
            print("\nSearching for methods...")
            
            methods = await method.find_methods(client_connection, parent_node_id)
            if not methods:
                print("No methods found under the specified node")
                return
                
            print(f"\nFound {len(methods)} methods:")
            for i, method_info in enumerate(methods, 1):
                print(f"{i}. {method_info['DisplayName']} ({method_info['NodeId']})")
                print(f"   Parent: {method_info['ParentId']}")
            
            selection = input("\nSelect method number or enter 0 to cancel: ")
            if not selection or selection == "0":
                return
                
            # 선택한 메서드 정보 가져오기
            try:
                selected = int(selection) - 1
                if 0 <= selected < len(methods):
                    method_node_id = methods[selected]['NodeId']
                    parent_node_id = methods[selected]['ParentId']
                else:
                    print("Invalid selection")
                    return
            except ValueError:
                print("Invalid input")
                return
                
        else:
            # 직접 노드 ID 입력
            parent_node_id = input("Enter parent node ID: ")
            method_node_id = input("Enter method node ID: ")
        
        # 메서드 정보 가져오기
        method_info = await method.get_method_info(client_connection, method_node_id)
        
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
        
        # 입력 인수 수집
        input_values = []
        for i, arg in enumerate(input_args_info, 1):
            arg_name = arg.get('Name', f'Argument {i}')
            arg_type = arg.get('DataType', 'String')
            
            value = input(f"Enter value for {arg_name} ({arg_type}): ")
            input_values.append(value)
        
        # 자동 타입 변환으로 메서드 호출
        result = await method.call_method_with_typed_params(
            client_connection, 
            parent_node_id, 
            method_node_id, 
            input_values
        )
        
        # 결과 출력
        if isinstance(result, list) and all(isinstance(item, dict) for item in result):
            # 구조화된 결과
            print("\nMethod result:")
            for i, out in enumerate(result, 1):
                print(f"{i}. {out.get('Name')}: {out.get('Value')} ({out.get('DataType')})")
        else:
            print(f"\nMethod result: {result}")
            
    except Exception as e:
        logger.error(f"Failed to call method: {e}")
        print(f"Error: {e}")

async def create_subscription(client_connection, subscription_list):
    if not client_connection:
        logger.info("Not connected to any server")
        return subscription_list
    
    try:
        print("\n=== Create Subscription ===")
        # 구독 파라미터 입력
        publishing_interval = float(input("Enter publishing interval in ms [500]: ") or "500")
        lifetime_count = int(input("Enter lifetime count [10]: ") or "10")
        max_keep_alive_count = int(input("Enter max keep alive count [3]: ") or "3")
        priority = int(input("Enter priority [0]: ") or "0")
        
        # 연결 확인 및 재연결 시도
        try:
            # 간단한 호출로 연결 상태 확인
            await client_connection.get_namespace_array()
        except Exception as conn_err:
            logger.warning(f"Connection check failed before creating subscription: {conn_err}")
            logger.info("Attempting to reconnect...")
            
            # 재연결 시도
            try:
                # 기존 연결 닫기
                try:
                    await client_connection.disconnect()
                except:
                    pass
                
                # 다시 연결
                server_url = DEFAULT_SERVER_URL
                client_connection = await connection.create_session(server_url)
                logger.info(f"Reconnected to server: {server_url}")
            except Exception as reconnect_err:
                logger.error(f"Failed to reconnect: {reconnect_err}")
                print(f"Could not reconnect to server: {reconnect_err}")
                return subscription_list
        
        # 개선된 구독 생성 함수 사용
        try:
            sub = await subscription.create_subscription(
                client_connection,
                publishing_interval,
                lifetime_count,
                max_keep_alive_count,
                priority
            )
        except Exception as sub_err:
            if "closed" in str(sub_err).lower() or "connection" in str(sub_err).lower():
                logger.warning(f"Connection issue during subscription creation: {sub_err}")
                logger.info("Attempting to reconnect and retry...")
                
                # 재연결 시도
                try:
                    # 기존 연결 닫기
                    try:
                        await client_connection.disconnect()
                    except:
                        pass
                    
                    # 다시 연결
                    server_url = DEFAULT_SERVER_URL
                    client_connection = await connection.create_session(server_url)
                    logger.info(f"Reconnected to server: {server_url}")
                    
                    # 구독 다시 시도
                    sub = await subscription.create_subscription(
                        client_connection,
                        publishing_interval,
                        lifetime_count,
                        max_keep_alive_count,
                        priority
                    )
                except Exception as retry_err:
                    logger.error(f"Failed to retry subscription creation: {retry_err}")
                    print(f"Could not create subscription after reconnection: {retry_err}")
                    return subscription_list
            else:
                # 연결 관련 오류가 아닌 경우 그대로 예외 전파
                raise
        
        if sub:
            # 구독 정보 저장
            sub_info = {
                "id": sub.subscription_id,
                "subscription": sub,
                "publishing_interval": publishing_interval,
                "lifetime_count": lifetime_count,
                "max_keep_alive_count": max_keep_alive_count,
                "priority": priority,
                "monitored_items": []
            }
            
            subscription_list.append(sub_info)
            
            # 모니터링 항목 추가 여부
            add_monitored_items = input("Add monitored items? (y/n): ").lower() == 'y'
            if add_monitored_items:
                await _add_monitored_items(client_connection, sub, sub_info)
                
            print(f"\nSuccessfully created subscription (ID: {sub.subscription_id})")
        else:
            print("\nFailed to create subscription")
    except Exception as e:
        logger.error(f"Failed to create subscription: {e}")
        print(f"Error: {e}")
    
    return subscription_list

async def _add_monitored_items(client_connection, sub, sub_info):
    """구독에 모니터링 항목 추가"""
    try:
        while True:
            # 노드 ID 입력
            node_id = input("\nEnter node ID to monitor (or empty to finish): ")
            if not node_id:
                break
                
            # 샘플링 간격 입력
            sampling_interval = float(input("Enter sampling interval in ms [100]: ") or "100")
            
            # 저장 옵션
            store_values = input("Store values for later analysis? (y/n): ").lower() == 'y'
            max_values = 100
            if store_values:
                try:
                    max_values = int(input("Maximum values to store [100]: ") or "100")
                except ValueError:
                    max_values = 100
            
            # 고급 핸들러 설정
            handler_options = {
                "log_changes": True,
                "store_values": store_values,
                "max_values": max_values,
                "timestamp_values": True
            }
            
            # 값 변경 시 표시할 콜백 함수
            def display_callback(node, value, data):
                node_id_str = str(node.nodeid)
                value_str = str(value)
                if len(value_str) > 60:
                    value_str = f"{value_str[:60]}..."
                print(f"Data change: {node_id_str} = {value_str}")
            
            # 연결 확인 및 재시도
            try:
                handle = await subscription.subscribe_data_change(
                    sub, 
                    node_id,
                    display_callback,
                    sampling_interval,
                    advanced_handler_options=handler_options
                )
                
                # 모니터링 항목 정보 저장
                sub_info["monitored_items"].append({
                    "handle": handle,
                    "node_id": node_id,
                    "sampling_interval": sampling_interval
                })
                
                print(f"Successfully added monitored item for {node_id}")
            except Exception as e:
                logger.error(f"Failed to add monitored item: {e}")
                print(f"Error adding monitored item: {e}")
                
                # 연결 문제인지 확인
                if client_connection and ("closed" in str(e).lower() or "connection" in str(e).lower()):
                    logger.warning("Connection issue detected during monitored item creation")
                    
                    # 재연결 시도 여부 확인
                    try_reconnect = input("Connection issue detected. Try to reconnect? (y/n): ").lower() == 'y'
                    if try_reconnect:
                        try:
                            logger.info("Attempting to reconnect...")
                            
                            # 기존 연결 닫기
                            try:
                                await client_connection.disconnect()
                            except:
                                pass
                            
                            # 서버에 재연결
                            server_url = DEFAULT_SERVER_URL
                            client_connection = await connection.create_session(server_url)
                            logger.info(f"Reconnected to server: {server_url}")
                            
                            # 새 구독 생성
                            new_sub = await subscription.create_subscription(
                                client_connection,
                                sub_info["publishing_interval"],
                                sub_info["lifetime_count"],
                                sub_info["max_keep_alive_count"],
                                sub_info["priority"]
                            )
                            
                            # 구독 객체 갱신
                            sub_info["id"] = new_sub.subscription_id
                            sub_info["subscription"] = new_sub
                            sub = new_sub
                            
                            print(f"Successfully reconnected and created new subscription (ID: {new_sub.subscription_id})")
                            
                            # 다시 모니터링 항목 추가 시도
                            print("Retrying to add monitored item...")
                            handle = await subscription.subscribe_data_change(
                                sub, 
                                node_id,
                                display_callback,
                                sampling_interval,
                                advanced_handler_options=handler_options
                            )
                            
                            # 모니터링 항목 정보 저장
                            sub_info["monitored_items"].append({
                                "handle": handle,
                                "node_id": node_id,
                                "sampling_interval": sampling_interval
                            })
                            
                            print(f"Successfully added monitored item for {node_id} after reconnection")
                            
                        except Exception as reconnect_err:
                            logger.error(f"Failed to reconnect and add monitored item: {reconnect_err}")
                            print(f"Error during reconnection: {reconnect_err}")
            
            # 추가 항목 모니터링 여부
            if input("Add another monitored item? (y/n): ").lower() != 'y':
                break
    except Exception as e:
        logger.error(f"Error in _add_monitored_items: {e}")
        print(f"Error: {e}")

async def modify_subscription(subscription_list):
    if not subscription_list:
        print("No active subscriptions")
        return subscription_list
    
    try:
        # 구독 목록 표시
        print("\nActive subscriptions:")
        for i, sub in enumerate(subscription_list):
            monitored_count = len(sub.get("monitored_items", []))
            print(f"{i+1}. ID: {sub['id']} (Interval: {sub['publishing_interval']}ms, Items: {monitored_count})")
        
        # 구독 선택
        selection = input("\nSelect subscription to modify (number): ")
        try:
            idx = int(selection) - 1
            if idx < 0 or idx >= len(subscription_list):
                print("Invalid selection")
                return subscription_list
        except ValueError:
            print("Invalid input")
            return subscription_list
            
        selected_sub = subscription_list[idx]
        sub_object = selected_sub['subscription']
        
        # 수정 유형 선택
        mod_type = input("What to modify? (1=Parameters, 2=Add Items, 3=Publishing Mode): ") or "1"
        
        if mod_type == "1":
            # 구독 매개변수 수정
            publishing_interval = float(input(f"Enter new publishing interval in ms [{selected_sub['publishing_interval']}]: ") 
                                       or str(selected_sub['publishing_interval']))
            lifetime_count = int(input(f"Enter new lifetime count [{selected_sub['lifetime_count']}]: ") 
                                or str(selected_sub['lifetime_count']))
            max_keep_alive_count = int(input(f"Enter new max keep alive count [{selected_sub['max_keep_alive_count']}]: ") 
                                      or str(selected_sub['max_keep_alive_count']))
            
            # 구독 수정
            result = await subscription.modify_subscription(
                sub_object,
                publishing_interval,
                lifetime_count,
                max_keep_alive_count
            )
            
            if result:
                print(f"\nSuccessfully modified subscription (ID: {selected_sub['id']})")
                # 저장된 값 업데이트
                selected_sub['publishing_interval'] = publishing_interval
                selected_sub['lifetime_count'] = lifetime_count
                selected_sub['max_keep_alive_count'] = max_keep_alive_count
            else:
                print(f"\nFailed to modify subscription (ID: {selected_sub['id']})")
                
        elif mod_type == "2":
            # 모니터링 항목 추가
            await _add_monitored_items(None, sub_object, selected_sub)
            
        elif mod_type == "3":
            # 발행 모드 변경
            mode = input("Enable publishing? (y/n): ").lower() == 'y'
            result = await subscription.set_publishing_mode(sub_object, mode)
            
            if result:
                status = "enabled" if mode else "disabled"
                print(f"\nPublishing mode {status} for subscription (ID: {selected_sub['id']})")
            else:
                print(f"\nFailed to set publishing mode for subscription (ID: {selected_sub['id']})")
    except Exception as e:
        logger.error(f"Failed to modify subscription: {e}")
        print(f"Error: {e}")
    
    return subscription_list

async def delete_subscription(subscription_list):
    if not subscription_list:
        print("No active subscriptions")
        return subscription_list
    
    try:
        # List active subscriptions
        print("\nActive subscriptions:")
        for i, sub in enumerate(subscription_list):
            print(f"{i+1}. Subscription ID: {sub['id']}")
        
        selection = input("\nSelect subscription to delete (number) or 'all' to delete all: ")
        
        if selection.lower() == 'all':
            for sub in subscription_list:
                result = await subscription.delete_subscription(sub['subscription'])
                print(f"Deleted subscription ID: {sub['id']}" if result else f"Failed to delete subscription ID: {sub['id']}")
            return []
        else:
            idx = int(selection) - 1
            if idx < 0 or idx >= len(subscription_list):
                print("Invalid selection")
                return subscription_list
            
            selected_sub = subscription_list[idx]
            result = await subscription.delete_subscription(selected_sub['subscription'])
            
            if result:
                print(f"\nSuccessfully deleted subscription (ID: {selected_sub['id']})")
                return [sub for sub in subscription_list if sub['id'] != selected_sub['id']]
            else:
                print(f"\nFailed to delete subscription (ID: {selected_sub['id']})")
                return subscription_list
    except Exception as e:
        logger.error(f"Failed to delete subscription: {e}")
    
    return subscription_list

async def execute_example_script():
    examples_dir = "examples"
    example_files = [f for f in os.listdir(examples_dir) if f.endswith('.py') and not f.startswith('__')]
    
    print("\nAvailable example scripts:")
    for i, file in enumerate(example_files, 1):
        print(f"{i}. {file}")
    
    try:
        selection = int(input("\nSelect example to run (number): ")) - 1
        if selection < 0 or selection >= len(example_files):
            print("Invalid selection")
            return
        
        selected_file = example_files[selection]
        full_path = os.path.join(examples_dir, selected_file)
        
        print(f"\nExecuting {selected_file}...")
        await asyncio.create_subprocess_shell(f"python {full_path}")
        print(f"\nFinished executing {selected_file}")
    except Exception as e:
        logger.error(f"Failed to execute example script: {e}")

async def enter_monitoring_mode(client_connection, subscription_list):
    """구독 데이터 모니터링 모드로 진입합니다."""
    if not client_connection:
        logger.info("Not connected to any server")
        print("서버에 연결되어 있지 않습니다. 먼저 서버에 연결하세요.")
        return subscription_list
    
    if not subscription_list:
        print("활성화된 구독이 없습니다. 먼저 구독을 생성하세요.")
        create_sub = input("지금 구독을 생성하시겠습니까? (y/n): ").lower() == 'y'
        if create_sub:
            subscription_list = await create_subscription(client_connection, subscription_list)
        else:
            return subscription_list
    
    # 활성 구독 목록 출력
    print("\n활성화된 구독 목록:")
    for i, sub_info in enumerate(subscription_list, 1):
        monitored_items = sub_info.get("monitored_items", [])
        print(f"{i}. ID: {sub_info['id']} (모니터링 항목: {len(monitored_items)}개)")
    
    print("\n===== 모니터링 모드 =====")
    print("이 모드에서는 구독한 데이터의 변경사항을 실시간으로 관찰할 수 있습니다.")
    print("모니터링 중에 노드의 값이 변경되면 화면에 표시됩니다.")
    print("모니터링 모드를 종료하려면 'q' 또는 'exit'를 입력하세요.")
    print("데이터 변경 대기 중...")
    
    # 모니터링 상태 플래그
    monitoring_active = True
    
    # 키보드 입력 확인 태스크
    async def check_exit_command():
        nonlocal monitoring_active
        while monitoring_active:
            # 비동기 방식으로 입력 받기
            exit_command = await asyncio.to_thread(input, "")
            if exit_command.lower() in ['q', 'exit', 'quit']:
                print("모니터링 모드를 종료합니다...")
                monitoring_active = False
                return
            await asyncio.sleep(0.1)
    
    # 연결 상태 확인 태스크
    async def check_connection_status():
        nonlocal monitoring_active
        while monitoring_active:
            try:
                # 간단한 연결 상태 확인
                await client_connection.get_namespace_array()
            except Exception as e:
                print(f"\n연결 오류가 발생했습니다: {e}")
                print("서버와의 연결이 끊어졌을 수 있습니다. 모니터링을 종료합니다.")
                monitoring_active = False
                return
            await asyncio.sleep(5)  # 5초마다 연결 상태 확인
    
    # 모니터링 태스크 시작
    input_task = asyncio.create_task(check_exit_command())
    connection_task = asyncio.create_task(check_connection_status())
    
    # 모니터링 시작 시간
    start_time = time.time()
    
    try:
        # 모니터링 모드 유지
        while monitoring_active:
            # 진행 중인 시간 표시 (매 30초마다)
            current_time = time.time()
            elapsed_time = int(current_time - start_time)
            if elapsed_time > 0 and elapsed_time % 30 == 0:
                print(f"\n모니터링 진행 중... (경과 시간: {elapsed_time}초)")
            
            await asyncio.sleep(1)
    except asyncio.CancelledError:
        print("모니터링이 취소되었습니다.")
    except Exception as e:
        logger.error(f"모니터링 중 오류 발생: {e}")
        print(f"오류가 발생했습니다: {e}")
    finally:
        # 태스크 정리
        if not input_task.done():
            input_task.cancel()
        if not connection_task.done():
            connection_task.cancel()
        
        try:
            await input_task
        except asyncio.CancelledError:
            pass
        
        try:
            await connection_task
        except asyncio.CancelledError:
            pass
        
        print("\n모니터링 모드가 종료되었습니다.")
    
    return subscription_list

async def main():
    client_connection = None
    subscription_list = []
    
    while True:
        choice = await display_menu()
        
        try:
            if choice == '0' or choice.lower() == 'q':
                # Clean up before exit
                if client_connection:
                    for sub in subscription_list:
                        await subscription.delete_subscription(sub['subscription'])
                    await connection.close_session(client_connection)
                print("\nExiting OPC UA Client. Goodbye!")
                break
                
            elif choice == '1':  # Connect
                client_connection = await connect_to_server(client_connection)
                
            elif choice == '2':  # Disconnect
                client_connection = await disconnect_from_server(client_connection)
                subscription_list = []  # Clear subscriptions upon disconnect
                
            elif choice == '3':  # Get Node Info
                # 연결 확인 및 재연결
                client_connection, reconnected = await check_and_reconnect(client_connection)
                if client_connection:
                    await get_node_info(client_connection)
                    
                    # 재연결된 경우 구독 복구
                    if reconnected and subscription_list:
                        print("Connection was re-established. Recreating subscriptions...")
                        subscription_list = await recreate_subscriptions(client_connection, subscription_list)
                
            elif choice == '4':  # Read Node Value
                # 연결 확인 및 재연결
                client_connection, reconnected = await check_and_reconnect(client_connection)
                if client_connection:
                    await read_node_value(client_connection)
                    
                    # 재연결된 경우 구독 복구
                    if reconnected and subscription_list:
                        print("Connection was re-established. Recreating subscriptions...")
                        subscription_list = await recreate_subscriptions(client_connection, subscription_list)
                
            elif choice == '5':  # Write Node Value
                # 연결 확인 및 재연결
                client_connection, reconnected = await check_and_reconnect(client_connection)
                if client_connection:
                    await write_node_value(client_connection)
                    
                    # 재연결된 경우 구독 복구
                    if reconnected and subscription_list:
                        print("Connection was re-established. Recreating subscriptions...")
                        subscription_list = await recreate_subscriptions(client_connection, subscription_list)
                
            elif choice == '6':  # Browse Nodes
                # 연결 확인 및 재연결
                client_connection, reconnected = await check_and_reconnect(client_connection)
                if client_connection:
                    await browse_nodes(client_connection)
                    
                    # 재연결된 경우 구독 복구
                    if reconnected and subscription_list:
                        print("Connection was re-established. Recreating subscriptions...")
                        subscription_list = await recreate_subscriptions(client_connection, subscription_list)
                
            elif choice == '7':  # Search Nodes
                # 연결 확인 및 재연결
                client_connection, reconnected = await check_and_reconnect(client_connection)
                if client_connection:
                    await find_nodes(client_connection)
                    
                    # 재연결된 경우 구독 복구
                    if reconnected and subscription_list:
                        print("Connection was re-established. Recreating subscriptions...")
                        subscription_list = await recreate_subscriptions(client_connection, subscription_list)
                
            elif choice == '8':  # Call Method
                # 연결 확인 및 재연결
                client_connection, reconnected = await check_and_reconnect(client_connection)
                if client_connection:
                    await call_method(client_connection)
                    
                    # 재연결된 경우 구독 복구
                    if reconnected and subscription_list:
                        print("Connection was re-established. Recreating subscriptions...")
                        subscription_list = await recreate_subscriptions(client_connection, subscription_list)
                
            elif choice == '9':  # Create Subscription
                # 연결 확인 및 재연결
                client_connection, reconnected = await check_and_reconnect(client_connection)
                if client_connection:
                    subscription_list = await create_subscription(client_connection, subscription_list)
                
            elif choice == '10':  # Modify Subscription
                # 연결 확인 및 재연결
                client_connection, reconnected = await check_and_reconnect(client_connection)
                if client_connection:
                    if reconnected and subscription_list:
                        print("Connection was re-established. Recreating subscriptions...")
                        subscription_list = await recreate_subscriptions(client_connection, subscription_list)
                    
                    subscription_list = await modify_subscription(subscription_list)
                
            elif choice == '11':  # Delete Subscription
                # 연결 확인 및 재연결
                client_connection, reconnected = await check_and_reconnect(client_connection)
                if client_connection:
                    if reconnected and subscription_list:
                        print("Connection was re-established. Recreating subscriptions...")
                        subscription_list = await recreate_subscriptions(client_connection, subscription_list)
                    
                    subscription_list = await delete_subscription(subscription_list)
                
            elif choice == '12':  # Execute Example Script
                await execute_example_script()
                
            elif choice == '13':  # Enter Monitoring Mode
                # 연결 확인 및 재연결
                client_connection, reconnected = await check_and_reconnect(client_connection)
                if client_connection:
                    if reconnected and subscription_list:
                        print("Connection was re-established. Recreating subscriptions...")
                        subscription_list = await recreate_subscriptions(client_connection, subscription_list)
                    
                    subscription_list = await enter_monitoring_mode(client_connection, subscription_list)
                
            else:
                print("\nInvalid choice. Please try again.")
                
        except Exception as e:
            logger.error(f"Error processing choice: {e}")
            traceback.print_exc()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nApplication terminated by user.")
    except Exception as e:
        logger.error(f"Unhandled exception: {e}")
        traceback.print_exc() 