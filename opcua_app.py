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

# 로깅 설정 (바이너리 데이터 필터링 포함)
utils.setup_logging(logging.WARNING)
logger = logging.getLogger(__name__)

DEFAULT_SERVER_URL = "opc.tcp://mk:62541/Quickstarts/ReferenceServer"

# 전역 변수로 세션 관리
session_manager = connection.MultiSessionManager()
current_session_id = None  # 현재 활성 세션 ID
subscription_lists = {}    # 세션별 구독 목록 - {session_id: [subscriptions...]}

def get_current_connection():
    """현재 활성화된 세션의 클라이언트 연결을 반환합니다."""
    global current_session_id, session_manager
    if not current_session_id:
        return None
    return session_manager.get_session(current_session_id)

async def display_menu():
    print("\n===== OPC UA Client Application =====")
    print("1. Connect to Server (New Session)")
    print("2. Disconnect Current Session")
    print("3. List and Switch Sessions")
    print("4. Get Node Information")
    print("5. Read Node Value")
    print("6. Write Node Value")
    print("7. Browse Nodes")
    print("8. Search Nodes")
    print("9. Call Method")
    print("10. Create Subscription")
    print("11. Modify Subscription")
    print("12. Delete Subscription")
    print("13. Execute Example Script")
    print("14. Enter Monitoring Mode")
    print("0. Exit")
    print("====================================")
    return input("Enter your choice: ")

async def connect_to_server():
    """
    새로운 세션을 생성하여 OPC UA 서버에 연결합니다.
    """
    global session_manager, current_session_id, subscription_lists
    
    try:
        print("\n=== Connect to Server (New Session) ===")
        session_id = input("Enter session name/ID: ")
        
        # 세션 ID 검증
        if not session_id:
            print("Session ID cannot be empty")
            return False
        
        # 이미 존재하는 세션인지 확인
        if session_id in session_manager.sessions:
            print(f"Session '{session_id}' already exists. Please use another name.")
            return False
        
        server_url = input(f"Enter server URL [{DEFAULT_SERVER_URL}]: ") or DEFAULT_SERVER_URL
        
        # 연결 생성
        print(f"Connecting to {server_url} with session '{session_id}'...")
        try:
            client = await session_manager.create_session(session_id, server_url)
        except Exception as e:
            logger.error(f"Failed to create session: {e}")
            print(f"Session creation failed: {e}")
            return False
            
        print(f"Connected successfully with session '{session_id}'!")
        
        # 연결 정보 표시
        try:
            server_status = await client.get_node("i=2256").read_value()  # ServerStatusDataType
            print(f"Server: {server_status.BuildInfo.ProductName} {server_status.BuildInfo.SoftwareVersion}")
            print(f"Current time: {server_status.CurrentTime}")
            print(f"State: {server_status.State.name}")
        except Exception as status_err:
            logger.warning(f"Could not read server status: {status_err}")
        
        # 네임스페이스 표시
        try:
            namespaces = await client.get_namespace_array()
            print("\nAvailable namespaces:")
            for i, ns in enumerate(namespaces):
                print(f"  ns={i}: {ns}")
        except Exception as ns_err:
            logger.warning(f"Could not read namespaces: {ns_err}")
        
        # 현재 세션으로 설정
        current_session_id = session_id
        subscription_lists[current_session_id] = []  # 새 세션의 구독 목록 초기화
        
        return True
    except Exception as e:
        logger.error(f"Failed to connect: {e}")
        print(f"Connection failed: {e}")
        return False

async def disconnect_from_server():
    """
    현재 활성화된 세션을 연결 해제합니다.
    """
    global session_manager, current_session_id, subscription_lists
    
    if not current_session_id:
        logger.info("No active session")
        print("Not connected to any server")
        return False
    
    try:
        # 세션 구독 정리
        if current_session_id in subscription_lists:
            for sub in subscription_lists[current_session_id]:
                try:
                    await subscription.delete_subscription(sub['subscription'])
                except Exception as e:
                    logger.warning(f"Error deleting subscription: {e}")
        
        # 세션 닫기
        await session_manager.close_session(current_session_id)
        print(f"Disconnected session '{current_session_id}'")
        
        # 구독 목록에서 제거
        if current_session_id in subscription_lists:
            del subscription_lists[current_session_id]
        
        # 다른 세션이 있으면 첫 번째 세션으로 전환
        if session_manager.sessions:
            current_session_id = next(iter(session_manager.sessions))
            print(f"Switched to session '{current_session_id}'")
        else:
            current_session_id = None
            
        return True
    except Exception as e:
        logger.error(f"Failed to disconnect: {e}")
        print(f"Disconnect failed: {e}")
        return False

async def list_and_switch_sessions():
    """
    현재 활성화된 세션 목록을 표시하고 전환합니다.
    """
    global session_manager, current_session_id
    
    if not session_manager.sessions:
        print("No active sessions. Please connect to a server first.")
        return False
    
    print("\n=== Active Sessions ===")
    
    # 활성 세션 목록 표시
    sessions = list(session_manager.sessions.keys())
    for i, session_id in enumerate(sessions, 1):
        status = "* CURRENT" if session_id == current_session_id else ""
        print(f"{i}. {session_id} {status}")
    
    # 세션 선택 입력
    choice = input("\nSelect session to switch to (number): ")
    
    try:
        idx = int(choice) - 1
        if 0 <= idx < len(sessions):
            selected_session = sessions[idx]
            
            # 이미 현재 세션이면 메시지만 표시
            if selected_session == current_session_id:
                print(f"Already using session '{current_session_id}'")
                return True
                
            # 다른 세션으로 전환
            current_session_id = selected_session
            print(f"Switched to session '{current_session_id}'")
            return True
        else:
            print("Invalid selection")
            return False
    except ValueError:
        print("Invalid input")
        return False

async def check_and_reconnect(preserve_subscriptions=True):
    """
    현재 세션의 연결 상태를 확인하고 필요한 경우 재연결합니다.
    
    Args:
        preserve_subscriptions: 구독 정보를 보존할지 여부
        
    Returns:
        튜플 (연결 객체, 재연결 여부)
    """
    global session_manager, current_session_id
    
    if not current_session_id:
        logger.warning("No active session")
        return None, False
    
    client_connection = session_manager.get_session(current_session_id)
    if not client_connection:
        logger.warning("No client connection for current session")
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
            
            # 다시 연결 생성
            server_url = DEFAULT_SERVER_URL
            new_client = await connection.create_session(server_url)
            
            # 세션 관리자의 연결 업데이트
            session_manager.sessions[current_session_id] = new_client
            
            logger.info(f"Reconnected to server: {server_url}")
            reconnected = True
            client_connection = new_client
        except Exception as reconnect_err:
            logger.error(f"Failed to reconnect: {reconnect_err}")
            return None, False
    
    return client_connection, reconnected

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

async def read_node_value(client_connection):
    if not client_connection:
        logger.info("Not connected to any server")
        return
    
    try:
        node_id = input("Enter node ID (e.g. 'i=84', 'ns=1;s=MyNode'): ")
        
        # 중앙 집중식 연결 확인 및 재연결 사용
        client_connection, reconnected = await check_and_reconnect()
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

async def create_subscription(client_connection, subscription_list, 
                          publishing_interval=500, lifetime_count=10, 
                          max_keep_alive_count=3, priority=0):
    """
    새로운 구독을 생성합니다.
    """
    if not client_connection:
        print("서버에 연결되어 있지 않습니다. 먼저 서버에 연결하세요.")
        return subscription_list
        
    try:
        # 라이브러리의 subscription 모듈을 사용하여 구독 생성
        sub = await subscription.create_subscription(
            client_connection, 
            publishing_interval, 
            lifetime_count, 
            max_keep_alive_count, 
            priority
        )
        
        # 구독 정보 저장
        subscription_info = {
            "id": sub.subscription_id,
            "subscription": sub,
            "publishing_interval": publishing_interval,
            "lifetime_count": lifetime_count,
            "max_keep_alive_count": max_keep_alive_count,
            "priority": priority,
            "monitored_items": []
        }
        
        subscription_list.append(subscription_info)
        print(f"구독이 생성되었습니다. ID: {sub.subscription_id}")
        
        # 모니터링 항목 추가 여부 확인
        add_item = input("모니터링 항목을 추가하시겠습니까? (y/n): ").lower() == 'y'
        if add_item:
            await add_monitored_item(client_connection, subscription_list)
            
    except Exception as e:
        logger.error(f"Error creating subscription: {e}")
        print(f"구독 생성 중 오류가 발생했습니다: {e}")
    
    return subscription_list

async def add_monitored_item(client_connection, subscription_list):
    """
    기존 구독에 모니터링 항목을 추가합니다.
    """
    if not client_connection:
        print("서버에 연결되어 있지 않습니다. 먼저 서버에 연결하세요.")
        return subscription_list
        
    if not subscription_list:
        print("활성화된 구독이 없습니다. 먼저 구독을 생성하세요.")
        create_sub = input("지금 구독을 생성하시겠습니까? (y/n): ").lower() == 'y'
        if create_sub:
            subscription_list = await create_subscription(client_connection, subscription_list)
            # 사용자가 이미 모니터링 항목을 추가했을 수 있으므로 여기서 종료
            return subscription_list
        else:
            return subscription_list
    
    # 연결 상태 확인 및 재연결 시도
    try:
        # 간단한 서버 연결 확인
        await client_connection.get_namespace_array()
        logger.debug("Connection verified before adding monitored item")
    except Exception as conn_err:
        logger.warning(f"Connection check failed: {conn_err}")
        print(f"서버 연결이 끊어졌습니다: {conn_err}")
        
        reconnect = input("서버에 재연결을 시도하시겠습니까? (y/n): ").lower() == 'y'
        if reconnect:
            try:
                # 현재 세션 ID 가져오기
                current_session_id = None
                for session_id, client in session_manager.sessions.items():
                    if client == client_connection:
                        current_session_id = session_id
                        break
                
                if not current_session_id:
                    print("세션 정보를 찾을 수 없습니다.")
                    return subscription_list
                
                # 기존 연결 닫기
                try:
                    await client_connection.disconnect()
                except:
                    pass  # 이미 닫혀있을 수 있음
                
                # 서버 URL 얻기 (기본값 사용)
                server_url = DEFAULT_SERVER_URL
                
                # 재연결 시도
                print(f"서버 {server_url}에 재연결 중...")
                
                # 세션 재생성
                new_client = await connection.create_session(server_url)
                
                # 세션 관리자 업데이트
                session_manager.sessions[current_session_id] = new_client
                
                # 클라이언트 연결 업데이트
                client_connection = new_client
                
                print("서버에 성공적으로 재연결되었습니다.")
                
                # 구독 재생성
                print("구독을 재생성 중입니다...")
                subscription_list = await recreate_subscriptions(client_connection, subscription_list)
                
                if not subscription_list:
                    print("구독을 재생성할 수 없습니다.")
                    return subscription_list
                
            except Exception as reconnect_err:
                print(f"재연결 실패: {reconnect_err}")
                logger.error(f"Failed to reconnect: {reconnect_err}")
                return subscription_list
        else:
            print("모니터링 항목 추가를 취소합니다.")
            return subscription_list
    
    # 구독 선택
    print("\n활성화된 구독 목록:")
    for i, sub_info in enumerate(subscription_list, 1):
        monitored_items = sub_info.get("monitored_items", [])
        print(f"{i}. ID: {sub_info['id']} (모니터링 항목: {len(monitored_items)}개)")
    
    try:
        selection_input = input("\n모니터링 항목을 추가할 구독 번호를 선택하세요: ")
        
        # 사용자 입력 처리 - 목록 번호 또는 실제 구독 ID 모두 허용
        selected_sub_info = None
        
        try:
            # 먼저 목록 번호로 시도 (1, 2, 3...)
            selection_idx = int(selection_input) - 1
            if 0 <= selection_idx < len(subscription_list):
                selected_sub_info = subscription_list[selection_idx]
            else:
                # 목록 번호가 잘못된 경우 실제 구독 ID로 시도
                for sub_info in subscription_list:
                    if str(sub_info['id']) == selection_input:
                        selected_sub_info = sub_info
                        break
        except ValueError:
            # 숫자가 아닌 경우 직접 구독 ID로 시도
            for sub_info in subscription_list:
                if str(sub_info['id']) == selection_input:
                    selected_sub_info = sub_info
                    break
        
        if not selected_sub_info:
            print("잘못된 선택입니다. 유효한 구독 번호 또는 ID를 입력하세요.")
            return subscription_list
        
        sub = selected_sub_info["subscription"]
        
        # 구독 상태 확인
        try:
            # 구독이 유효한지 간단한 확인 (subscription_id 접근)
            sub_id = sub.subscription_id
            logger.debug(f"Subscription {sub_id} verified")
        except Exception as sub_err:
            logger.warning(f"Subscription check failed: {sub_err}")
            print(f"구독이 유효하지 않습니다: {sub_err}")
            print("구독을 재생성합니다...")
            
            try:
                # 구독 파라미터 사용
                publishing_interval = selected_sub_info.get("publishing_interval", 500)
                lifetime_count = selected_sub_info.get("lifetime_count", 10)
                max_keep_alive_count = selected_sub_info.get("max_keep_alive_count", 3)
                priority = selected_sub_info.get("priority", 0)
                
                # 새 구독 생성
                new_sub = await subscription.create_subscription(
                    client_connection,
                    publishing_interval,
                    lifetime_count,
                    max_keep_alive_count,
                    priority
                )
                
                # 구독 정보 업데이트
                selected_sub_info["subscription"] = new_sub
                selected_sub_info["id"] = new_sub.subscription_id
                sub = new_sub
                
                print(f"구독이 재생성되었습니다. 새 ID: {new_sub.subscription_id}")
            except Exception as recreate_err:
                logger.error(f"Failed to recreate subscription: {recreate_err}")
                print(f"구독 재생성 실패: {recreate_err}")
                return subscription_list
        
        # 노드 ID 입력
        node_id_str = input("추가할 노드 ID를 입력하세요 (예: ns=2;i=1): ")
        if not node_id_str:
            print("노드 ID가 입력되지 않았습니다.")
            return subscription_list
        
        # 노드 존재 확인
        try:
            node_obj = client_connection.get_node(node_id_str)
            # 노드 접근 가능 확인 (선택적)
            try:
                await node_obj.read_browse_name()
                print(f"노드 {node_id_str}가 확인되었습니다.")
            except Exception as browse_err:
                logger.warning(f"Node exists but may not be readable: {browse_err}")
                print(f"노드가 존재하지만 읽을 수 없을 수 있습니다: {browse_err}")
                if input("계속 진행하시겠습니까? (y/n): ").lower() != 'y':
                    return subscription_list
        except Exception as node_err:
            logger.error(f"Node does not exist or is not accessible: {node_err}")
            print(f"노드가 존재하지 않거나 접근할 수 없습니다: {node_err}")
            return subscription_list
        
        # 샘플링 간격 입력
        sampling_interval_str = input("샘플링 간격을 입력하세요 (ms, 기본값: 100): ")
        sampling_interval = 100
        if sampling_interval_str:
            try:
                sampling_interval = float(sampling_interval_str)
            except ValueError:
                print("잘못된 샘플링 간격입니다. 기본값 100ms를 사용합니다.")
        
        # 데이터 변경 콜백 함수 정의
        async def data_change_callback(node, val, data):
            try:
                # 노드 이름 가져오기(가능한 경우)
                try:
                    display_name = await node.read_browse_name()
                    name = display_name.Name
                except:
                    # 이름을 가져올 수 없으면 노드 ID 사용
                    name = str(node.nodeid)
                
                # 간결한 출력 형식
                print(f"{name}: {val}")
            except Exception as e:
                print(f"Error in callback: {e}")
                logger.error(f"Error in data change callback: {e}")

        # 핸들러 옵션 설정
        handler_options = {
            'callback': data_change_callback,
            'log_changes': True,
            'log_level': logging.INFO
        }
        
        print(f"노드 {node_id_str}에 대한 모니터링 항목을 추가하는 중...")
        
        # 구독 핸들 가져오기
        try:
            handle = await subscription.subscribe_data_change(
                sub, node_id_str, 
                sampling_interval=sampling_interval,
                advanced_handler_options=handler_options
            )
            
            # 모니터링 항목 정보 저장
            monitored_item = {
                "handle": handle,
                "node_id": node_id_str,
                "sampling_interval": sampling_interval
            }
            
            selected_sub_info["monitored_items"].append(monitored_item)
            print(f"모니터링 항목이 추가되었습니다. 핸들: {handle}")
        except Exception as sub_err:
            logger.error(f"Failed to add monitored item: {sub_err}")
            print(f"모니터링 항목 추가 실패: {sub_err}")
            
            # 연결 문제인지 확인
            if "connection" in str(sub_err).lower() or "closed" in str(sub_err).lower():
                print("연결 문제가 감지되었습니다. 서버가 연결을 끊었을 수 있습니다.")
                retry = input("재연결 후 다시 시도하시겠습니까? (y/n): ").lower() == 'y'
                
                if retry:
                    # 재귀적으로 함수 재호출 (연결 확인 및 재연결 수행)
                    print("재연결 중...")
                    return await add_monitored_item(client_connection, subscription_list)
        
    except Exception as e:
        logger.error(f"Error adding monitored item: {e}")
        print(f"모니터링 항목 추가 중 오류가 발생했습니다: {e}")
    
    return subscription_list

async def modify_subscription(subscription_list):
    """
    기존 구독을 수정합니다.
    """
    if not subscription_list:
        print("활성화된 구독이 없습니다. 먼저 구독을 생성하세요.")
        return subscription_list

    # 구독 선택
    print("\n활성화된 구독 목록:")
    for i, sub_info in enumerate(subscription_list, 1):
        monitored_items = sub_info.get("monitored_items", [])
        print(f"{i}. ID: {sub_info['id']} (모니터링 항목: {len(monitored_items)}개)")
    
    try:
        selection_input = input("\n수정할 구독 번호를 선택하세요: ")
        
        # 사용자 입력 처리 - 목록 번호 또는 실제 구독 ID 모두 허용
        selected_sub = None
        
        try:
            # 먼저 목록 번호로 시도 (1, 2, 3...)
            selection_idx = int(selection_input) - 1
            if 0 <= selection_idx < len(subscription_list):
                selected_sub = subscription_list[selection_idx]
            else:
                # 목록 번호가 잘못된 경우 실제 구독 ID로 시도
                for sub_info in subscription_list:
                    if str(sub_info['id']) == selection_input:
                        selected_sub = sub_info
                        break
        except ValueError:
            # 숫자가 아닌 경우 직접 구독 ID로 시도
            for sub_info in subscription_list:
                if str(sub_info['id']) == selection_input:
                    selected_sub = sub_info
                    break
        
        if not selected_sub:
            print("잘못된 선택입니다. 유효한 구독 번호 또는 ID를 입력하세요.")
            return subscription_list
        
        client_connection = get_current_connection()
        if not client_connection:
            print("서버에 연결되어 있지 않습니다. 먼저 서버에 연결하세요.")
            return subscription_list
            
        # 선택된 구독 정보
        sub_object = selected_sub.get("subscription")
        
        if not sub_object:
            print("구독 객체를 찾을 수 없습니다.")
            return subscription_list
        
        print("\n수정 유형을 선택하세요:")
        print("1. 구독 속성 수정 (발행 간격 등)")
        print("2. 모니터링 항목 추가")
        print("3. 모니터링 항목 삭제")
        print("4. 발행 모드 설정 (활성화/비활성화)")
        
        mod_type = input("\n선택: ")
        
        if mod_type == "1":
            # 구독 속성 수정
            new_period = float(input(f"발행 간격(ms) [{selected_sub.get('publishing_interval', 500)}]: ") or selected_sub.get('publishing_interval', 500))
            new_lifetime = int(input(f"수명 카운트 [{selected_sub.get('lifetime_count', 10)}]: ") or selected_sub.get('lifetime_count', 10))
            new_keepalive = int(input(f"최대 Keep-Alive 카운트 [{selected_sub.get('max_keep_alive_count', 3)}]: ") or selected_sub.get('max_keep_alive_count', 3))
            
            # 속성 수정 시도
            result = await subscription.modify_subscription(
                sub_object, 
                new_period, 
                new_lifetime, 
                new_keepalive
            )
            
            if result:
                # 성공 시 구독 정보 업데이트
                selected_sub["publishing_interval"] = new_period
                selected_sub["lifetime_count"] = new_lifetime
                selected_sub["max_keep_alive_count"] = new_keepalive
                print(f"구독 {sub_object.subscription_id}의 속성이 업데이트되었습니다.")
            else:
                print(f"구독 {sub_object.subscription_id}의 속성 업데이트에 실패했습니다.")
                
        elif mod_type == "2":
            # 모니터링 항목 추가
            await add_monitored_item(client_connection, subscription_list)
            
        elif mod_type == "3":
            # 모니터링 항목 삭제
            monitored_items = selected_sub.get("monitored_items", [])
            if not monitored_items:
                print("이 구독에 모니터링 항목이 없습니다.")
                return subscription_list
                
            print("\n현재 모니터링 항목:")
            for i, item in enumerate(monitored_items, 1):
                print(f"{i}. {item.get('node_id')} (핸들: {item.get('handle')})")
                
            try:
                item_idx = int(input("\n삭제할 항목 번호를 선택하세요: "))
                if item_idx < 1 or item_idx > len(monitored_items):
                    print("잘못된 선택입니다.")
                    return subscription_list
                    
                # 선택된 항목 정보
                item = monitored_items[item_idx - 1]
                handle = item.get("handle")
                
                # 항목 삭제 시도
                try:
                    await sub_object.unsubscribe(handle)
                    # 삭제 후 목록에서 제거
                    monitored_items.pop(item_idx - 1)
                    print(f"모니터링 항목이 삭제되었습니다. 핸들: {handle}")
                except Exception as e:
                    logger.error(f"Failed to unsubscribe monitored item: {e}")
                    print(f"모니터링 항목 삭제 중 오류 발생: {e}")
            except ValueError:
                print("잘못된 입력입니다.")
                
        elif mod_type == "4":
            # 발행 모드 설정
            current_mode = "활성화됨" # 기본값은 활성화라고 가정
            new_mode_str = input(f"발행 모드 (현재: {current_mode}) [1: 활성화, 0: 비활성화]: ")
            if new_mode_str in ["0", "1"]:
                new_mode = new_mode_str == "1"
                result = await subscription.set_publishing_mode(sub_object, new_mode)
                
                if result:
                    status = "활성화" if new_mode else "비활성화"
                    print(f"구독 {sub_object.subscription_id}의 발행 모드가 {status}되었습니다.")
                else:
                    print(f"구독 {sub_object.subscription_id}의 발행 모드 설정에 실패했습니다.")
            else:
                print("잘못된 모드 선택입니다.")
                
        else:
            print("잘못된 수정 유형 선택입니다.")
            
    except Exception as e:
        logger.error(f"Error modifying subscription: {e}")
        print(f"구독 수정 중 오류 발생: {e}")
        
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
        
        selection = input("\nSelect subscription to delete (number/ID) or 'all' to delete all: ")
        
        if selection.lower() == 'all':
            for sub in subscription_list:
                result = await subscription.delete_subscription(sub['subscription'])
                print(f"Deleted subscription ID: {sub['id']}" if result else f"Failed to delete subscription ID: {sub['id']}")
            return []
        else:
            # 사용자 입력 처리 - 목록 번호 또는 실제 구독 ID 모두 허용
            selected_sub = None
            
            try:
                # 먼저 목록 번호로 시도 (1, 2, 3...)
                selection_idx = int(selection) - 1
                if 0 <= selection_idx < len(subscription_list):
                    selected_sub = subscription_list[selection_idx]
                else:
                    # 목록 번호가 잘못된 경우 실제 구독 ID로 시도
                    for sub_info in subscription_list:
                        if str(sub_info['id']) == selection:
                            selected_sub = sub_info
                            break
            except ValueError:
                # 숫자가 아닌 경우 직접 구독 ID로 시도
                for sub_info in subscription_list:
                    if str(sub_info['id']) == selection:
                        selected_sub = sub_info
                        break
            
            if not selected_sub:
                print("Invalid selection. Please enter a valid number or subscription ID.")
                return subscription_list
            
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

class DataChangeHandler:
    """OPC UA 데이터 변경 알림을 처리하는 핸들러 클래스"""
    
    async def datachange_notification(self, node, val, data):
        """데이터 변경 알림을 처리하는 메서드"""
        try:
            node_id_str = str(node.nodeid)
            try:
                display_name = await node.read_browse_name()
                name = display_name.Name
            except:
                name = node_id_str
            
            value_str = str(val)
            if len(value_str) > 60:
                value_str = f"{value_str[:60]}..."
            print(f"Data change: {name} ({node_id_str}) = {value_str}")
        except Exception as e:
            print(f"Error in callback: {e}")
            logger.error(f"Error in data change callback: {e}")
    
    async def event_notification(self, event):
        """이벤트 알림을 처리하는 메서드"""
        logger.info(f"Event received: {event}")
    
    async def status_change_notification(self, status):
        """상태 변경 알림을 처리하는 메서드"""
        logger.info(f"Status change: {status}")

async def recreate_subscriptions(client_connection, subscription_list):
    """
    구독 목록을 재생성합니다. 연결이 끊어지고 다시 연결된 경우 호출됩니다.
    
    Args:
        client_connection: OPC UA 클라이언트 연결
        subscription_list: 이전 구독 목록
        
    Returns:
        list: 새로 생성된 구독 목록
    """
    if not client_connection or not subscription_list:
        return subscription_list
    
    print("기존 구독을 다시 생성하는 중...")
    
    # 기존 구독 목록 백업
    backup_subscriptions = subscription_list.copy()
    new_subscriptions = []
    
    # 각 구독을 재생성
    for sub_info in backup_subscriptions:
        try:
            # 구독 파라미터 가져오기
            period = sub_info.get('publishing_interval', 500)
            lifetime = sub_info.get('lifetime_count', 10)
            keepalive = sub_info.get('max_keep_alive_count', 3)
            priority = sub_info.get('priority', 0)
            
            # 새 구독 생성
            new_sub = await subscription.create_subscription(
                client_connection,
                period,
                lifetime,
                keepalive,
                priority
            )
            
            # 새 구독 정보
            new_sub_info = {
                "id": new_sub.subscription_id,
                "subscription": new_sub,
                "publishing_interval": period,
                "lifetime_count": lifetime,
                "max_keep_alive_count": keepalive,
                "priority": priority,
                "monitored_items": []
            }
            
            # 기존 모니터링 항목 복원
            for item in sub_info.get('monitored_items', []):
                try:
                    node_id = item.get('node_id')
                    sampling_interval = item.get('sampling_interval', 100)
                    
                    # 데이터 변경 콜백 함수 정의
                    async def data_change_callback(node, val, data):
                        try:
                            # 노드 이름 가져오기(가능한 경우)
                            try:
                                display_name = await node.read_browse_name()
                                name = display_name.Name
                            except:
                                # 이름을 가져올 수 없으면 노드 ID 사용
                                name = str(node.nodeid)
                            
                            # 간결한 출력 형식
                            print(f"{name}: {val}")
                        except Exception as e:
                            print(f"Error in callback: {e}")
                            logger.error(f"Error in data change callback: {e}")
                    
                    # 핸들러 옵션 설정
                    handler_options = {
                        'callback': data_change_callback,
                        'log_changes': True,
                        'log_level': logging.INFO
                    }
                    
                    # 구독 핸들 가져오기
                    handle = await subscription.subscribe_data_change(
                        new_sub, node_id, 
                        sampling_interval=sampling_interval,
                        advanced_handler_options=handler_options
                    )
                    
                    # 모니터링 항목 정보 저장
                    monitored_item = {
                        "handle": handle,
                        "node_id": node_id,
                        "sampling_interval": sampling_interval
                    }
                    
                    new_sub_info['monitored_items'].append(monitored_item)
                    print(f"재생성된 구독에 노드 {node_id} 모니터링 항목이 추가되었습니다.")
                    
                except Exception as item_err:
                    logger.error(f"Error recreating monitored item: {item_err}")
                    print(f"모니터링 항목 재생성 오류: {item_err}")
            
            # 새 구독 목록에 추가
            new_subscriptions.append(new_sub_info)
            print(f"구독 ID: {new_sub.subscription_id}이(가) 재생성되었습니다.")
            
        except Exception as sub_err:
            logger.error(f"Error recreating subscription: {sub_err}")
            print(f"구독 재생성 중 오류 발생: {sub_err}")
    
    # 모든 구독이 재생성되었는지 확인
    if not new_subscriptions:
        print("구독을 재생성하지 못했습니다.")
        return []
        
    print(f"{len(new_subscriptions)}개의 구독이 재생성되었습니다.")
    return new_subscriptions

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
    
    # 모니터링 항목 확인
    has_monitored_items = False
    for sub_info in subscription_list:
        if len(sub_info.get("monitored_items", [])) > 0:
            has_monitored_items = True
            break
    
    if not has_monitored_items:
        print("\n모니터링할 항목이 없습니다. 먼저 구독에 모니터링 항목을 추가하세요.")
        add_item = input("지금 모니터링 항목을 추가하시겠습니까? (y/n): ").lower() == 'y'
        if add_item:
            await add_monitored_item(client_connection, subscription_list)
            # 다시 확인
            has_monitored_items = False
            for sub_info in subscription_list:
                if len(sub_info.get("monitored_items", [])) > 0:
                    has_monitored_items = True
                    break
            
            if not has_monitored_items:
                print("모니터링 항목이 추가되지 않았습니다. 모니터링 모드를 종료합니다.")
                return subscription_list
    
    print("\n===== 모니터링 모드 시작 =====")
    print("'q' 또는 'exit'를 입력하여 종료")
    
    # 모니터링 상태 플래그
    monitoring_active = True
    
    # 키보드 입력 확인 태스크
    async def check_exit_command():
        nonlocal monitoring_active
        while monitoring_active:
            # 비동기 방식으로 입력 받기
            exit_command = await asyncio.to_thread(input, "")
            if exit_command.lower() in ['q', 'exit', 'quit']:
                print("모니터링 모드 종료...")
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
                print("\n연결 오류가 발생했습니다: {e}")
                print("모니터링 종료.")
                monitoring_active = False
                return
            await asyncio.sleep(5)  # 5초마다 연결 상태 확인
    
    # 모니터링 태스크 시작
    input_task = asyncio.create_task(check_exit_command())
    connection_task = asyncio.create_task(check_connection_status())
    
    try:
        # 모니터링 모드 유지
        while monitoring_active:
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
        
        print("\n===== 모니터링 모드 종료 =====")
    
    return subscription_list

async def main():
    global session_manager, current_session_id, subscription_lists
    
    while True:
        try:
            choice = await display_menu()
            
            try:
                if choice == '0' or choice.lower() == 'q':
                    # Clean up before exit
                    try:
                        await session_manager.close_all_sessions()
                    except Exception as e:
                        logger.warning(f"Error closing sessions: {e}")
                    print("\nExiting OPC UA Client. Goodbye!")
                    break
                
                elif choice == '1':  # Connect to Server (New Session)
                    await connect_to_server()
                    
                elif choice == '2':  # Disconnect Current Session
                    await disconnect_from_server()
                    
                elif choice == '3':  # List and Switch Sessions
                    await list_and_switch_sessions()
                    
                elif choice == '4':  # Get Node Info
                    client_connection, reconnected = await check_and_reconnect()
                    if client_connection:
                        await get_node_info(client_connection)
                        
                        # 재연결된 경우 구독 복구
                        if reconnected and current_session_id in subscription_lists:
                            print("Connection was re-established. Recreating subscriptions...")
                            subscription_lists[current_session_id] = await recreate_subscriptions(
                                client_connection, subscription_lists[current_session_id])
                    
                elif choice == '5':  # Read Node Value
                    client_connection, reconnected = await check_and_reconnect()
                    if client_connection:
                        await read_node_value(client_connection)
                        
                        # 재연결된 경우 구독 복구
                        if reconnected and current_session_id in subscription_lists:
                            print("Connection was re-established. Recreating subscriptions...")
                            subscription_lists[current_session_id] = await recreate_subscriptions(
                                client_connection, subscription_lists[current_session_id])
                    
                elif choice == '6':  # Write Node Value
                    client_connection, reconnected = await check_and_reconnect()
                    if client_connection:
                        await write_node_value(client_connection)
                        
                        # 재연결된 경우 구독 복구
                        if reconnected and current_session_id in subscription_lists:
                            print("Connection was re-established. Recreating subscriptions...")
                            subscription_lists[current_session_id] = await recreate_subscriptions(
                                client_connection, subscription_lists[current_session_id])
                    
                elif choice == '7':  # Browse Nodes
                    client_connection, reconnected = await check_and_reconnect()
                    if client_connection:
                        await browse_nodes(client_connection)
                        
                        # 재연결된 경우 구독 복구
                        if reconnected and current_session_id in subscription_lists:
                            print("Connection was re-established. Recreating subscriptions...")
                            subscription_lists[current_session_id] = await recreate_subscriptions(
                                client_connection, subscription_lists[current_session_id])
                    
                elif choice == '8':  # Search Nodes
                    client_connection, reconnected = await check_and_reconnect()
                    if client_connection:
                        await find_nodes(client_connection)
                        
                        # 재연결된 경우 구독 복구
                        if reconnected and current_session_id in subscription_lists:
                            print("Connection was re-established. Recreating subscriptions...")
                            subscription_lists[current_session_id] = await recreate_subscriptions(
                                client_connection, subscription_lists[current_session_id])
                    
                elif choice == '9':  # Call Method
                    client_connection, reconnected = await check_and_reconnect()
                    if client_connection:
                        await call_method(client_connection)
                        
                        # 재연결된 경우 구독 복구
                        if reconnected and current_session_id in subscription_lists:
                            print("Connection was re-established. Recreating subscriptions...")
                            subscription_lists[current_session_id] = await recreate_subscriptions(
                                client_connection, subscription_lists[current_session_id])
                    
                elif choice == '10':  # Create Subscription
                    client_connection, reconnected = await check_and_reconnect()
                    if client_connection:
                        if current_session_id not in subscription_lists:
                            subscription_lists[current_session_id] = []
                            
                        subscription_lists[current_session_id] = await create_subscription(
                            client_connection, subscription_lists[current_session_id])
                    
                elif choice == '11':  # Modify Subscription
                    client_connection, reconnected = await check_and_reconnect()
                    if client_connection:
                        if reconnected and current_session_id in subscription_lists:
                            print("Connection was re-established. Recreating subscriptions...")
                            subscription_lists[current_session_id] = await recreate_subscriptions(
                                client_connection, subscription_lists[current_session_id])
                        
                        if current_session_id in subscription_lists:
                            subscription_lists[current_session_id] = await modify_subscription(
                                subscription_lists[current_session_id])
                        else:
                            print("No subscriptions in current session")
                    
                elif choice == '12':  # Delete Subscription
                    client_connection, reconnected = await check_and_reconnect()
                    if client_connection:
                        if reconnected and current_session_id in subscription_lists:
                            print("Connection was re-established. Recreating subscriptions...")
                            subscription_lists[current_session_id] = await recreate_subscriptions(
                                client_connection, subscription_lists[current_session_id])
                        
                        if current_session_id in subscription_lists:
                            subscription_lists[current_session_id] = await delete_subscription(
                                subscription_lists[current_session_id])
                        else:
                            print("No subscriptions in current session")
                    
                elif choice == '13':  # Execute Example Script
                    await execute_example_script()
                    
                elif choice == '14':  # Enter Monitoring Mode
                    client_connection, reconnected = await check_and_reconnect()
                    if client_connection:
                        if reconnected and current_session_id in subscription_lists:
                            print("Connection was re-established. Recreating subscriptions...")
                            subscription_lists[current_session_id] = await recreate_subscriptions(
                                client_connection, subscription_lists[current_session_id])
                        
                        if current_session_id in subscription_lists:
                            subscription_lists[current_session_id] = await enter_monitoring_mode(
                                client_connection, subscription_lists[current_session_id])
                        else:
                            print("No subscriptions in current session")
                    
                else:
                    print("\nInvalid choice. Please try again.")
                    
            except Exception as e:
                logger.error(f"Error processing choice: {e}")
                traceback.print_exc()

        except Exception as e:
            logger.error(f"Error processing main loop: {e}")
            traceback.print_exc()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nApplication terminated by user.")
    except Exception as e:
        logger.error(f"Unhandled exception: {e}")
        traceback.print_exc() 