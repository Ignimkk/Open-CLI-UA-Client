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

# 구독 기본값 상수 import
from opcua_client.subscription import (
    DEFAULT_PUBLISHING_INTERVAL, 
    DEFAULT_LIFETIME_COUNT, 
    DEFAULT_MAX_KEEP_ALIVE_COUNT, 
    DEFAULT_PRIORITY,
    get_fallback_parameters
)

# 로깅 설정 (바이너리 데이터 필터링 포함)
utils.setup_logging(logging.WARNING)  # DEBUG에서 WARNING으로 다시 변경
logger = logging.getLogger(__name__)

DEFAULT_SERVER_URL = "opc.tcp://mkketi:62541/Quickstarts/ReferenceServer"

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
    print("0. List Server Endpoints")
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
    print("15. Event View (이벤트 전용 뷰)")
    print("99. Exit")
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
            # 기본 노드 정보 출력
            try:
                node_obj = client_connection.get_node(node_id)
                display_name = await node_obj.read_display_name()
                print(f"{display_name.Text}: {await node_obj.read_value()}")
            except Exception as e:
                logger.debug(f"기본 정보 표시 오류: {e}")
            
            print("\n=== 노드 속성 상세 정보 ===")
            
            # 계층적으로 표시할 속성 그룹 정의
            node_obj = client_connection.get_node(node_id)
            
            # 기본 정보 그룹
            print("▶ NodeId")
            node_id_obj = node_obj.nodeid
            try:
                print(f"  NamespaceIndex: {node_id_obj.NamespaceIndex}")
                print(f"  IdentifierType: {node_id_obj.NodeIdType.name}")
                print(f"  Identifier: {node_id_obj.Identifier}")
            except Exception as e:
                logger.debug(f"NodeId 정보 표시 오류: {e}")
                print(f"  {node_id_obj}")
            
            # 노드 클래스 정보
            try:
                node_class = await node_obj.read_node_class()
                print(f"▶ NodeClass: {node_class.name}")
            except Exception as e:
                logger.debug(f"NodeClass 정보 표시 오류: {e}")
            
            # 이름 정보
            try:
                browse_name = await node_obj.read_browse_name()
                display_name = await node_obj.read_display_name()
                print(f"▶ BrowseName: {browse_name.Name}")
                print(f"▶ DisplayName: {display_name.Text}")
            except Exception as e:
                logger.debug(f"이름 정보 표시 오류: {e}")
            
            # 설명 정보
            try:
                description = await node_obj.read_description()
                if description and description.Text:
                    print(f"▶ Description: {description.Text}")
                else:
                    print("▶ Description: [없음]")
            except Exception as e:
                logger.debug(f"설명 정보 표시 오류: {e}")
                print("▶ Description: [오류]")
            
            # 값 그룹
            print("▶ Value")
            try:
                value = await node_obj.read_value()
                status_code = "Good"
                server_timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
                
                # 서버 타임스탬프 가져오기 시도
                try:
                    data_value = await node_obj.read_data_value()
                    if hasattr(data_value, 'ServerTimestamp'):
                        server_timestamp = data_value.ServerTimestamp.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
                    if hasattr(data_value, 'StatusCode'):
                        status_code = str(data_value.StatusCode)
                except Exception as ts_err:
                    logger.debug(f"타임스탬프 정보 표시 오류: {ts_err}")
                
                print(f"  ServerTimestamp: {server_timestamp}")
                print(f"  StatusCode: {status_code}")
                print(f"  Value: {value}")
            except Exception as e:
                logger.debug(f"값 정보 표시 오류: {e}")
                print("  [값을 읽을 수 없음]")
            
            # 데이터 타입 그룹
            print("▶ DataType")
            try:
                data_type_id = await node_obj.read_data_type()
                data_type_node = client_connection.get_node(data_type_id)
                data_type_name = await data_type_node.read_browse_name()
                
                print(f"  NamespaceIndex: {data_type_id.NamespaceIndex}")
                print(f"  IdentifierType: {data_type_id.NodeIdType.name}")
                print(f"  Identifier: {data_type_id.Identifier}")
                print(f"  Name: {data_type_name.Name}")
            except Exception as e:
                logger.debug(f"데이터 타입 정보 표시 오류: {e}")
                print("  [데이터 타입을 읽을 수 없음]")
            
            # 값 순위 및 배열 차원 정보
            try:
                value_rank = await node_obj.read_value_rank()
                print(f"▶ ValueRank: {value_rank}")
                if value_rank >= 0:
                    try:
                        dimensions = await node_obj.read_array_dimensions()
                        print(f"▶ ArrayDimensions: {dimensions if dimensions else 'Null'}")
                    except Exception as dim_err:
                        logger.debug(f"배열 차원 정보 표시 오류: {dim_err}")
                        print("▶ ArrayDimensions: [읽을 수 없음]")
                else:
                    print("▶ ArrayDimensions: Null")
            except Exception as e:
                logger.debug(f"값 순위 정보 표시 오류: {e}")
            
            # 접근 수준 정보
            try:
                access_level = await node_obj.read_attribute(ua.AttributeIds.AccessLevel)
                access_level_value = access_level.Value.Value
                access_strs = []
                
                if access_level_value & ua.AccessLevel.CurrentRead:
                    access_strs.append("CurrentRead")
                if access_level_value & ua.AccessLevel.CurrentWrite:
                    access_strs.append("CurrentWrite")
                if access_level_value & ua.AccessLevel.HistoryRead:
                    access_strs.append("HistoryRead")
                if access_level_value & ua.AccessLevel.HistoryWrite:
                    access_strs.append("HistoryWrite")
                
                print(f"▶ AccessLevel: {', '.join(access_strs)}")
                
                # 사용자 접근 수준도 표시
                try:
                    user_access = await node_obj.read_attribute(ua.AttributeIds.UserAccessLevel)
                    user_access_value = user_access.Value.Value
                    user_access_strs = []
                    
                    if user_access_value & ua.AccessLevel.CurrentRead:
                        user_access_strs.append("CurrentRead")
                    if user_access_value & ua.AccessLevel.CurrentWrite:
                        user_access_strs.append("CurrentWrite")
                    if user_access_value & ua.AccessLevel.HistoryRead:
                        user_access_strs.append("HistoryRead")
                    if user_access_value & ua.AccessLevel.HistoryWrite:
                        user_access_strs.append("HistoryWrite")
                    
                    print(f"▶ UserAccessLevel: {', '.join(user_access_strs)}")
                except Exception as user_err:
                    logger.debug(f"사용자 접근 수준 정보 표시 오류: {user_err}")
            except Exception as e:
                logger.debug(f"접근 수준 정보 표시 오류: {e}")
            
            # 히스토리 및 기타 정보
            try:
                min_sampling = await node_obj.read_attribute(ua.AttributeIds.MinimumSamplingInterval)
                if not min_sampling.Value.is_empty():
                    print(f"▶ MinimumSamplingInterval: {min_sampling.Value.Value}")
                
                historizing = await node_obj.read_attribute(ua.AttributeIds.Historizing)
                if not historizing.Value.is_empty():
                    print(f"▶ Historizing: {historizing.Value.Value}")
            except Exception as e:
                logger.debug(f"추가 정보 표시 오류: {e}")
            
            # 참조 정보 표시
            try:
                references = await node_obj.get_references()
                print(f"▶ References: {len(references)}개")
                
                # 타입 정의 참조 찾기
                type_refs = [ref for ref in references if ref.ReferenceTypeId == ua.ObjectIds.HasTypeDefinition]
                if type_refs:
                    type_def = type_refs[0].NodeId
                    type_node = client_connection.get_node(type_def)
                    type_name = await type_node.read_browse_name()
                    print(f"▶ TypeDefinition: {type_name.Name} ({type_def})")
            except Exception as e:
                logger.debug(f"참조 정보 표시 오류: {e}")
            
        else:
            # 기본 노드 정보만 조회
            info = await node.get_node_info(client_connection, node_id)
            
            # 노드 정보 출력
            print("\nNode Information:")
            for key, value in info.items():
                # 값이 너무 길면 요약
                value_str = str(value)
                if len(value_str) > 100:
                    value_str = f"{value_str[:100]}... [내용 생략]"
                print(f"{key}: {value_str}")
            
            # 데이터 타입 추가 조회 시도
            try:
                node_obj = client_connection.get_node(node_id)
                data_type_attr = await node_obj.read_data_type()
                data_type_node = client_connection.get_node(data_type_attr)
                data_type_name = await data_type_node.read_browse_name()
                print(f"\n데이터 타입: {data_type_name.Name}")
            except Exception as type_err:
                logger.debug(f"데이터 타입을 읽을 수 없습니다: {type_err}")
            
    except Exception as e:
        logger.error(f"Failed to get node information: {e}")
        print(f"노드 정보를 가져오는 중 오류가 발생했습니다: {e}")
        traceback.print_exc()

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
        
        print("\n사용 가능한 값 타입:")
        print("1. int (정수)")
        print("2. int16 (16비트 정수)")
        print("3. uint16 (부호 없는 16비트 정수)")
        print("4. int32 (32비트 정수)")
        print("5. uint32 (부호 없는 32비트 정수)")
        print("6. int64 (64비트 정수)")
        print("7. uint64 (부호 없는 64비트 정수)")
        print("8. float (실수)")
        print("9. double (배정밀도 실수)")
        print("10. bool (불리언)")
        print("11. str (문자열)")
        
        value_type = input("\nEnter value type (숫자 또는 이름으로 입력): ").lower()
        value_str = input("Enter value: ")
        
        # Convert string input to the appropriate type
        if value_type in ["1", "int"]:
            value = int(value_str)
        elif value_type in ["2", "int16"]:
            value = ua.Int16(int(value_str))
        elif value_type in ["3", "uint16"]:
            value = ua.UInt16(int(value_str))
        elif value_type in ["4", "int32"]:
            value = ua.Int32(int(value_str))
        elif value_type in ["5", "uint32"]:
            value = ua.UInt32(int(value_str))
        elif value_type in ["6", "int64"]:
            value = ua.Int64(int(value_str))
        elif value_type in ["7", "uint64"]:
            value = ua.UInt64(int(value_str))
        elif value_type in ["8", "float"]:
            value = float(value_str)
        elif value_type in ["9", "double"]:
            value = float(value_str)  # Python's float is already double precision
        elif value_type in ["10", "bool"]:
            value = value_str.lower() in ("yes", "true", "t", "1", "y")
        elif value_type in ["11", "str"]:
            value = value_str
        else:
            print(f"지원되지 않는 값 타입: {value_type}. 기본 타입(int)으로 처리합니다.")
            value = int(value_str)
        
        try:
            # 노드 정보를 읽어 실제 데이터 타입 확인 (선택적)
            node_obj = client_connection.get_node(node_id)
            
            # 데이터 타입 노드 ID 얻기 (선택적)
            try:
                data_type_attr = await node_obj.read_data_type()
                data_type_node = client_connection.get_node(data_type_attr)
                data_type_name = await data_type_node.read_browse_name()
                print(f"\n노드의 데이터 타입: {data_type_name.Name}")
            except Exception as type_err:
                logger.debug(f"데이터 타입을 읽을 수 없습니다: {type_err}")
        except Exception as e:
            logger.debug(f"노드 정보를 읽을 수 없습니다: {e}")
            
        result = await node.write_node_attribute(client_connection, node_id, value)
        print(f"\n노드 {node_id}에 값 '{value}' ({type(value).__name__})을 성공적으로 썼습니다.")
    except Exception as e:
        logger.error(f"Failed to write node value: {e}")
        print(f"\n노드 {node_id}에 값을 쓰는 데 실패했습니다.")
        print(f"오류: {e}")
        
        # 데이터 타입 불일치 오류인 경우 추가 정보 제공
        if "BadTypeMismatch" in str(e):
            print("\n데이터 타입 불일치 오류가 발생했습니다.")
            print("값의 타입이 노드의 데이터 타입과 일치하지 않습니다.")
            print("노드의 실제 데이터 타입을 확인하려면 '4. Get Node Information' 메뉴를 사용하세요.")

async def browse_nodes(client_connection):
    if not client_connection:
        logger.info("Not connected to any server")
        return
    
    try:
        node_id = input("Enter node ID to browse (default is root node): ") or None
        
        # 추가 옵션 제공
        browse_type = input("Browse type (1=Basic, 2=Tree): ") or "1"
        
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
                          publishing_interval=DEFAULT_PUBLISHING_INTERVAL, 
                          lifetime_count=DEFAULT_LIFETIME_COUNT, 
                          max_keep_alive_count=DEFAULT_MAX_KEEP_ALIVE_COUNT, 
                          priority=DEFAULT_PRIORITY):
    """
    새로운 구독을 생성합니다.
    
    Args:
        client_connection: OPC UA 클라이언트 연결
        subscription_list: 구독 목록
        publishing_interval: 발행 간격 (ms) - 기본값 1000ms
        lifetime_count: 수명 카운트 - 기본값 600 (10분)
        max_keep_alive_count: 최대 Keep-Alive 카운트 - 기본값 20 (20초)
        priority: 우선순위 - 기본값 0
        
    Note:
        OPC UA 스펙에 따라 lifetime_count는 max_keep_alive_count의 최소 3배 이상이어야 합니다.
        기본값: lifetime_count(600) / max_keep_alive_count(20) = 30 (권장값 충족)
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
        add_item = input("\n모니터링 항목을 추가하시겠습니까? (y/n): ").lower() == 'y'
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
                # 구독 파라미터 사용 - 헬퍼 함수 사용으로 중복 제거
                publishing_interval, lifetime_count, max_keep_alive_count, priority = get_fallback_parameters(selected_sub_info)
                
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
        print("5. 모니터링 항목 설정 수정 (샘플링 간격)")
        print("6. 모니터링 모드 설정 (Disabled/Sampling/Reporting)")
        print("7. 구독 정보 표시 (Keep-Alive 간격 포함)")
        
        mod_type = input("\n선택: ")
        
        if mod_type == "1":
            # 구독 속성 수정
            new_period = float(input(f"발행 간격(ms) [{selected_sub.get('publishing_interval', DEFAULT_PUBLISHING_INTERVAL)}]: ") or selected_sub.get('publishing_interval', DEFAULT_PUBLISHING_INTERVAL))
            new_lifetime = int(input(f"수명 카운트 [{selected_sub.get('lifetime_count', DEFAULT_LIFETIME_COUNT)}]: ") or selected_sub.get('lifetime_count', DEFAULT_LIFETIME_COUNT))
            new_keepalive = int(input(f"최대 Keep-Alive 카운트 [{selected_sub.get('max_keep_alive_count', DEFAULT_MAX_KEEP_ALIVE_COUNT)}]: ") or selected_sub.get('max_keep_alive_count', DEFAULT_MAX_KEEP_ALIVE_COUNT))
            
            print(f"\n구독 속성을 수정하는 중...")
            
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
                print(f"\n구독 {sub_object.subscription_id}의 속성이 성공적으로 업데이트되었습니다.")
                print(f"새로운 발행 간격: {new_period}ms")
                print(f"새로운 수명 카운트: {new_lifetime}")
                print(f"새로운 Keep-Alive 카운트: {new_keepalive}")
            else:
                print(f"\n구독 {sub_object.subscription_id}의 속성 업데이트에 실패했습니다.")
                print("주의: 일부 OPC UA 서버는 구독 속성 수정을 지원하지 않을 수 있습니다.")
        
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
            new_mode_str = input(f"발행 모드 [1: 활성화, 0: 비활성화]: ")
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
        
        elif mod_type == "5":
            # 모니터링 항목 설정 수정
            monitored_items = selected_sub.get("monitored_items", [])
            if not monitored_items:
                print("이 구독에 모니터링 항목이 없습니다.")
                return subscription_list
                
            # 현재 모니터링 항목 목록 표시
            print("\n현재 모니터링 항목:")
            
            for i, item in enumerate(monitored_items, 1):
                handle = item.get('handle')
                node_id = item.get('node_id')
                sampling_interval = item.get('sampling_interval', 'Unknown')
                
                print(f"{i}. {node_id} (핸들: {handle})")
                print(f"   현재 샘플링 간격: {sampling_interval}ms")
            
            try:
                item_idx = int(input("\n수정할 항목 번호를 선택하세요: "))
                if item_idx < 1 or item_idx > len(monitored_items):
                    print("잘못된 선택입니다.")
                    return subscription_list
                    
                # 선택된 항목 정보
                item = monitored_items[item_idx - 1]
                handle = item.get("handle")
                current_sampling = item.get("sampling_interval", 100)
                
                print(f"\n현재 샘플링 간격: {current_sampling}ms")
                
                # 새로운 샘플링 간격 입력
                new_sampling_str = input(f"새로운 샘플링 간격(ms) [{current_sampling}]: ")
                new_sampling = float(new_sampling_str) if new_sampling_str else current_sampling
                
                # 모니터링 항목 수정 실행 (샘플링 간격만 수정)
                print(f"\n모니터링 항목 (핸들: {handle})의 샘플링 간격을 수정하는 중...")
                
                result = await subscription.modify_monitored_item(
                    sub_object,
                    handle,
                    new_sampling,
                    0,  # 큐 크기는 기본값 사용
                    -1  # 기존 필터 유지
                )
                
                if result:
                    # 성공 시 로컬 정보 업데이트
                    item["sampling_interval"] = new_sampling
                    print(f"\n모니터링 항목의 샘플링 간격이 성공적으로 수정되었습니다.")
                    print(f"새로운 샘플링 간격: {new_sampling}ms")
                else:
                    print(f"\n모니터링 항목 수정에 실패했습니다.")
                    
            except ValueError:
                print("잘못된 입력입니다.")
            except Exception as e:
                logger.error(f"Error modifying monitored item: {e}")
                print(f"모니터링 항목 수정 중 오류 발생: {e}")
        
        elif mod_type == "6":
            # 모니터링 모드 설정
            monitored_items = selected_sub.get("monitored_items", [])
            if not monitored_items:
                print("이 구독에 모니터링 항목이 없습니다.")
                return subscription_list
                
            # 현재 모니터링 항목 목록 표시
            print("\n현재 모니터링 항목:")
            for i, item in enumerate(monitored_items, 1):
                handle = item.get('handle')
                node_id = item.get('node_id')
                print(f"{i}. {node_id} (핸들: {handle})")
            
            print("\n모니터링 모드 설정 옵션:")
            print("1. 특정 항목 선택")
            print("2. 모든 항목")
            
            target_option = input("선택: ")
            
            # 대상 항목 결정
            target_handles = []
            if target_option == "1":
                try:
                    item_idx = int(input("\n모드를 설정할 항목 번호를 선택하세요: "))
                    if item_idx < 1 or item_idx > len(monitored_items):
                        print("잘못된 선택입니다.")
                        return subscription_list
                    target_handles = [monitored_items[item_idx - 1].get("handle")]
                except ValueError:
                    print("잘못된 입력입니다.")
                    return subscription_list
            elif target_option == "2":
                target_handles = [item.get("handle") for item in monitored_items]
            else:
                print("잘못된 선택입니다.")
                return subscription_list
            
            # 모니터링 모드 선택
            print("\n모니터링 모드 선택:")
            print("1. Disabled - 모니터링 비활성화")
            print("2. Sampling - 샘플링만 수행 (알림 없음)")
            print("3. Reporting - 샘플링 + 알림 전송")
            
            mode_option = input("선택 [3]: ") or "3"
            
            mode_map = {
                "1": "Disabled",
                "2": "Sampling", 
                "3": "Reporting"
            }
            
            if mode_option not in mode_map:
                print("잘못된 선택입니다.")
                return subscription_list
                
            selected_mode = mode_map[mode_option]
            
            # 모니터링 모드 설정 실행
            print(f"\n모니터링 모드를 {selected_mode}로 설정하는 중...")
            
            result = await subscription.set_monitoring_mode(sub_object, target_handles, selected_mode)
            
            if result:
                item_count = len(target_handles)
                print(f"\n{item_count}개 모니터링 항목의 모드가 {selected_mode}로 성공적으로 설정되었습니다.")
                
                # 모드별 설명 표시
                if selected_mode == "Disabled":
                    print("모니터링이 비활성화되어 데이터 변경 알림이 전송되지 않습니다.")
                elif selected_mode == "Sampling":
                    print("샘플링만 수행되며 데이터 변경 알림은 전송되지 않습니다.")
                elif selected_mode == "Reporting":
                    print("샘플링과 데이터 변경 알림이 모두 활성화되었습니다.")
            else:
                print(f"\n모니터링 모드 설정에 실패했습니다.")
        
        elif mod_type == "7":
            # 구독 정보 표시 (Keep-Alive 간격 포함)
            print(f"\n구독 {sub_object.subscription_id}의 정보:")
            print(f"  발행 간격: {selected_sub.get('publishing_interval')}ms")
            print(f"  수명 카운트: {selected_sub.get('lifetime_count')}")
            print(f"  최대 Keep-Alive 카운트: {selected_sub.get('max_keep_alive_count')}")
            print(f"  우선순위: {selected_sub.get('priority')}")
            
            # 모니터링 항목 표시
            print("\n모니터링 항목:")
            for i, item in enumerate(monitored_items, 1):
                print(f"{i}. {item.get('node_id')} (핸들: {item.get('handle')})")
                print(f"   현재 샘플링 간격: {item.get('sampling_interval')}ms")
        
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
            # 구독 파라미터 가져오기 - 헬퍼 함수 사용으로 중복 제거
            period, lifetime, keepalive, priority = get_fallback_parameters(sub_info)
            
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
    
    # 모니터링 항목 확인 (데이터 변경 구독만)
    has_monitored_items = False
    total_data_items = 0
    
    for sub_info in subscription_list:
        # 데이터 변경 모니터링 항목 확인
        data_items = sub_info.get("monitored_items", [])
        for item in data_items:
            total_data_items += 1
            has_monitored_items = True
    
    if not has_monitored_items:
        print("\n모니터링할 데이터 항목이 없습니다.")
        print("데이터 변경 모니터링 항목을 추가하세요.")
        print("(이벤트 모니터링은 메뉴 15번 'Event View'를 사용하세요)")
        
        choice = input("\n데이터 모니터링 항목을 추가하시겠습니까? (y/n): ")
        
        if choice.lower() == "y":
            await add_monitored_item(client_connection, subscription_list)
        else:
            return subscription_list
            
        # 다시 확인
        has_monitored_items = False
        total_data_items = 0
        
        for sub_info in subscription_list:
            data_items = sub_info.get("monitored_items", [])
            for item in data_items:
                total_data_items += 1
                has_monitored_items = True
        
        if not has_monitored_items:
            print("모니터링 항목이 추가되지 않았습니다. 모니터링 모드를 종료합니다.")
            return subscription_list
    
    print("\n===== 모니터링 모드 시작 =====")
    print("'q' 또는 'exit'를 입력하여 종료")
    
    # 모니터링 상태 상세 표시
    print(f"\n모니터링 현황:")
    print(f"  활성 구독: {len(subscription_list)}개")
    print(f"  데이터 모니터링: {total_data_items}개")
    
    for i, sub_info in enumerate(subscription_list, 1):
        pub_interval = sub_info.get('publishing_interval', DEFAULT_PUBLISHING_INTERVAL)
        keep_alive_count = sub_info.get('max_keep_alive_count', DEFAULT_MAX_KEEP_ALIVE_COUNT)
        keep_alive_interval = (pub_interval * keep_alive_count) / 1000
        
        data_count = len(sub_info.get("monitored_items", []))
        
        print(f"\n구독 {i} (ID: {sub_info['id']}):")
        print(f"  Publishing Interval: {pub_interval}ms")
        print(f"  Keep-Alive 간격: {keep_alive_interval:.1f}초")
        print(f"  항목: 데이터 {data_count}개")
        
        # 각 항목 상세 표시 (간략하게)
        if data_count > 0:
            for item in sub_info.get("monitored_items", []):
                node_id = item.get('node_id', 'Unknown')
                print(f"    Data: {node_id}")
    
    print(f"\n백그라운드 모니터링 시작...")
    if total_data_items > 0:
        print("  데이터 변경사항 실시간 표시")
    
    # 모니터링 상태 플래그
    monitoring_active = True
    start_time = asyncio.get_event_loop().time()
    
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

async def list_endpoints():
    """
    OPC UA 서버의 사용 가능한 엔드포인트를 조회합니다.
    
    서버에 연결하기 전에 지원하는 보안 모드와 정책을 확인할 수 있습니다.
    또한 인증서 및 연결 시 필요한 다른 보안 요구사항도 확인할 수 있습니다.
    """
    try:
        print("\n=== List Server Endpoints ===")
        server_url = input(f"Enter server URL [{DEFAULT_SERVER_URL}]: ") or DEFAULT_SERVER_URL
        
        print(f"\n서버 {server_url}의 엔드포인트를 가져오는 중...")
        
        # connection 모듈의 get_endpoints 함수 사용
        endpoints = await connection.get_endpoints(server_url)
        
        if not endpoints:
            print("사용 가능한 엔드포인트가 없습니다.")
            return
            
        print(f"\n{len(endpoints)}개의 엔드포인트를 찾았습니다:\n")
        
        # 각 엔드포인트의 정보 표시
        for i, endpoint in enumerate(endpoints, 1):
            # 보안 모드 가져오기 (정수를 이름으로 변환)
            security_mode_num = getattr(endpoint, 'SecurityMode', ua.MessageSecurityMode.None_)
            security_mode = ua.MessageSecurityMode(security_mode_num).name if isinstance(security_mode_num, int) else str(security_mode_num)
            
            # 보안 정책 URI 가져오기
            security_policy = getattr(endpoint, 'SecurityPolicyUri', None) or "Unknown"
            security_policy_name = security_policy.split("#")[1] if "#" in security_policy else security_policy
            
            # 엔드포인트 URL
            endpoint_url = getattr(endpoint, 'EndpointUrl', None) or "Unknown"
            
            # 간결한 출력 형식 (주요 정보만)
            print(f"{i}. 엔드포인트: {endpoint_url}")
            print(f"   보안 모드: {security_mode}")
            print(f"   보안 정책: {security_policy_name}")
            
            # 서버 인증서가 있으면 정보 표시
            server_cert = getattr(endpoint, 'ServerCertificate', None)
            if server_cert:
                # 바이너리 데이터가 있으면 간단한 정보만 표시
                cert_size = len(server_cert) if isinstance(server_cert, bytes) else "정보 없음"
                print(f"   서버 인증서: {cert_size} 바이트")
            
            # 사용자 인증 유형 정보
            user_token_types = []
            user_identity_tokens = getattr(endpoint, 'UserIdentityTokens', [])
            for token in user_identity_tokens:
                token_type = getattr(token, 'TokenType', None)
                if token_type is not None:
                    if isinstance(token_type, int):
                        # TokenType이 정수인 경우 이름으로 변환
                        try:
                            token_type_name = ua.UserTokenType(token_type).name
                        except ValueError:
                            token_type_name = f"Unknown({token_type})"
                    else:
                        token_type_name = str(token_type)
                    user_token_types.append(token_type_name)
            
            if user_token_types:
                print(f"   인증 유형: {', '.join(user_token_types)}")
            
            print()  # 엔드포인트 간 구분을 위한 빈 줄
            
    except Exception as e:
        logger.error(f"엔드포인트 조회 중 오류 발생: {e}")
        print(f"엔드포인트를 가져오는 중 오류가 발생했습니다: {e}")
async def enter_event_view(client_connection):
    """
    이벤트 전용 뷰에 진입합니다.
    이벤트만을 위한 별도의 구독을 생성하고 실시간 모니터링을 제공합니다.
    """
    if not client_connection:
        print("서버에 연결되어 있지 않습니다. 먼저 서버에 연결하세요.")
        return
    
    print("\n===== Event View (이벤트 전용 뷰) =====")
    print("이벤트 전용 구독을 생성하여 실시간 이벤트를 모니터링합니다.")    
    
    # 기존 구독들 일시 정지 (이벤트 뷰 동안 데이터 변경 출력 방지)
    global current_session_id, subscription_lists
    existing_subscriptions = []
    if current_session_id and current_session_id in subscription_lists:
        print("기존 데이터 구독을 일시 정지합니다...")
        for sub_info in subscription_lists[current_session_id]:
            try:
                await subscription.set_publishing_mode(sub_info['subscription'], False)
                existing_subscriptions.append(sub_info)
                print(f"구독 {sub_info['id']} 일시 정지됨")
            except Exception as e:
                print(f"구독 {sub_info['id']} 정지 실패: {e}")
    
    # 이벤트 전용 핸들러 클래스
    class EventViewHandler:
        def __init__(self):
            self.event_count = 0
            self.start_time = time.time()
            
        async def event_notification(self, event):
            """이벤트 알림 처리 - 실시간 표시"""
            self.event_count += 1
            current_time = time.strftime("%H:%M:%S.%f")[:-3]
            
            print(f"\n[{current_time}] Event #{self.event_count}")
            print("=" * 50)
            
            try:
                # 이벤트 필드 표시
                if hasattr(event, '__dict__'):
                    for field_name, field_value in event.__dict__.items():
                        if not field_name.startswith('_'):
                            # 중요한 필드 강조
                            if field_name in ['EventType', 'SourceName', 'Message', 'Severity', 'Time']:
                                print(f"  ★ {field_name}: {field_value}")
                            else:
                                value_str = str(field_value)
                                if len(value_str) > 60:
                                    value_str = f"{value_str[:60]}..."
                                print(f"    {field_name}: {value_str}")
                else:
                    print(f"  Event Data: {event}")
                    
            except Exception as e:
                print(f"  오류: 이벤트 처리 중 문제 발생 - {e}")
            
            print("=" * 50)
        
        async def datachange_notification(self, node, val, data):
            """데이터 변경 알림 (이벤트 뷰에서는 무시)"""
            # Event View에서는 데이터 변경을 처리하지 않음
            pass
        
        async def status_change_notification(self, status):
            """구독 상태 변경 알림"""
            current_time = time.strftime("%H:%M:%S")
            print(f"[{current_time}] 구독 상태 변경: {status}")
    
    # 이벤트 핸들러 생성
    event_handler = EventViewHandler()
    
    try:
        # 이벤트 전용 구독 생성
        print("\n이벤트 전용 구독을 생성하는 중...")
        
        event_subscription = await subscription.create_subscription(
            client_connection,
            period=1000,  # 더 짧은 간격으로 수정
            lifetime_count=3600,  # 더 짧은 lifetime
            max_keep_alive_count=12,  # 더 짧은 keep-alive
            priority=0,
            handler=event_handler  # 이벤트 핸들러 전달
        )
        
        print(f"이벤트 전용 구독 생성 완료! ID: {event_subscription.subscription_id}")
        
        # Keep-Alive PublishRequest 강제 활성화 시도
        print("\nKeep-Alive PublishRequest 활성화 시도 중...")
        try:
            # 이벤트 구독만으로 Keep-Alive가 발생하는지 확인
            # asyncua의 내부 구현을 확인하여 PublishRequest 강제 시작
            if hasattr(event_subscription, 'server') and hasattr(event_subscription.server, '_publish_task'):
                # 이미 publish task가 있는지 확인
                if event_subscription.server._publish_task and not event_subscription.server._publish_task.done():
                    print("PublishRequest 태스크가 이미 실행 중입니다.")
                else:
                    # PublishRequest 태스크 수동 시작 시도
                    print("PublishRequest 태스크를 수동으로 시작합니다.")
                    # 이것은 python-opcua 내부 API이므로 작동하지 않을 수 있음

        except Exception as keep_alive_err:
            print(f"Keep-Alive 활성화 시도 실패: {keep_alive_err}")
            print("이벤트 구독만으로 Keep-Alive PublishRequest가 발생하지 않을 수 있습니다.")
        
        # 서버가 수정한 실제 값들 표시
        try:
            # 구독 파라미터에서 실제 값 확인
            if hasattr(event_subscription, 'parameters'):
                params = event_subscription.parameters
                actual_interval = getattr(params, 'RevisedPublishingInterval', 1000)
                actual_lifetime = getattr(params, 'RevisedLifetimeCount', 3600)
                actual_keepalive = getattr(params, 'RevisedMaxKeepAliveCount', 20)
                
                print(f"서버 수정 파라미터:")
                print(f"  Publishing Interval: {actual_interval}ms")
                print(f"  Lifetime Count: {actual_lifetime}")
                print(f"  Keep-Alive Count: {actual_keepalive}")
                
                # 실제 Keep-Alive 간격 계산
                keepalive_interval = (actual_interval * actual_keepalive) / 1000
                print(f"  실제 Keep-Alive 간격: {keepalive_interval:.1f}초")
                
                if keepalive_interval > 10:
                    print(f"   Keep-Alive 간격이 너무 깁니다 ({keepalive_interval:.1f}초)")
                    print(f"     PublishRequest 빈도가 낮을 수 있습니다.")
        except Exception as param_err:
            print(f"파라미터 정보 확인 실패: {param_err}")
        
        # 이벤트 소스와 타입 선택
        print("\n이벤트 구독 설정:")
        print("1. Server 노드 - BaseEventType (기본)")
        print("2. Server 노드 - SystemEventType")
        print("3. Objects 노드 - BaseEventType")
        print("4. 사용자 정의")
        
        choice = input("선택 [1]: ") or "1"
        
        if choice == "1":
            source_node_id = "i=2253"  # Server
            event_type_id = "i=2041"   # BaseEventType
            config_name = "Server → BaseEventType"
        elif choice == "2":
            source_node_id = "i=2253"  # Server
            event_type_id = "i=2130"   # SystemEventType
            config_name = "Server → SystemEventType"
        elif choice == "3":
            source_node_id = "i=85"    # Objects
            event_type_id = "i=2041"   # BaseEventType
            config_name = "Objects → BaseEventType"
        elif choice == "4":
            source_node_id = input("이벤트 소스 노드 ID: ")
            event_type_id = input("이벤트 타입 노드 ID: ")
            config_name = f"Custom: {source_node_id} → {event_type_id}"
        else:
            source_node_id = "i=2253"
            event_type_id = "i=2041"
            config_name = "Server → BaseEventType"
        
        # 이벤트 구독 생성
        print(f"\n이벤트 구독 생성 중: {config_name}")
        
        source_node = client_connection.get_node(source_node_id)
        event_type_node = client_connection.get_node(event_type_id)
        
        handle = await event_subscription.subscribe_events(
            sourcenode=source_node,
            evtypes=event_type_node,
            queuesize=10
        )
        
        print(f"이벤트 구독 성공 핸들: {handle}")
        print(f"구성: {config_name}")
        
        print("\n===== 실시간 이벤트 모니터링 시작 =====")
        print("'q' 또는 'exit'를 입력하여 종료")
        print("=" * 55)
        
        # 실시간 모니터링 시작
        monitoring_active = True
        start_time = time.time()
        
        # 키보드 입력 확인 태스크
        async def check_exit_command():
            nonlocal monitoring_active
            while monitoring_active:
                try:
                    exit_command = await asyncio.to_thread(input, "")
                    if exit_command.lower() in ['q', 'exit', 'quit']:
                        print("\nEvent View 종료 중...")
                        monitoring_active = False
                        return
                except:
                    pass
                await asyncio.sleep(0.1)
        
        # 상태 표시 태스크
        async def show_status():
            nonlocal monitoring_active
            last_event_count = 0
            
            while monitoring_active:
                await asyncio.sleep(10)  # 10초마다 상태 표시
                if monitoring_active:
                    elapsed = time.time() - start_time
                    new_events = event_handler.event_count - last_event_count
                    last_event_count = event_handler.event_count
                    
                    print(f"\n[상태] 경과 시간: {elapsed:.0f}초, "
                          f"총 이벤트: {event_handler.event_count}개, "
                          f"최근 10초: {new_events}개")
        
        # 태스크 시작
        input_task = asyncio.create_task(check_exit_command())
        status_task = asyncio.create_task(show_status())
        
        try:
            # 모니터링 유지
            while monitoring_active:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            print("\nCtrl+C 감지됨. Event View 종료 중...")
        finally:
            # 태스크 정리
            if not input_task.done():
                input_task.cancel()
            if not status_task.done():
                status_task.cancel()
            
            try:
                await input_task
            except asyncio.CancelledError:
                pass
            
            try:
                await status_task
            except asyncio.CancelledError:
                pass
            
            # 구독 정리
            try:
                await subscription.delete_subscription(event_subscription)
                print("이벤트 구독이 정리되었습니다.")
            except Exception as cleanup_err:
                print(f"구독 정리 중 오류: {cleanup_err}")
            
            # 기존 구독들 재개
            if existing_subscriptions:
                print("기존 데이터 구독을 재개합니다...")
                for sub_info in existing_subscriptions:
                    try:
                        await subscription.set_publishing_mode(sub_info['subscription'], True)
                        print(f"구독 {sub_info['id']} 재개됨")
                    except Exception as e:
                        print(f"구독 {sub_info['id']} 재개 실패: {e}")
        
        print("\n===== Event View 종료 =====")
        
        # 요약 정보
        elapsed_total = time.time() - start_time
        print(f"총 모니터링 시간: {elapsed_total:.1f}초")
        print(f"총 수신 이벤트: {event_handler.event_count}개")
        if elapsed_total > 0:
            rate = event_handler.event_count / elapsed_total * 60
            print(f"평균 이벤트 발생률: {rate:.2f}개/분")
        
    except Exception as e:
        logger.error(f"Event View 실행 중 오류: {e}")
        print(f"Event View 실행 중 오류가 발생했습니다: {e}")
        
        # 오류 해결 방법 제시
        if "BadNodeIdUnknown" in str(e):
            print("해결 방법: 노드 ID가 존재하지 않습니다. 다른 노드를 시도해보세요.")
        elif "BadEventFilterInvalid" in str(e):
            print("해결 방법: 이벤트 필터가 유효하지 않습니다. 다른 이벤트 타입을 시도해보세요.")
        elif "BadServiceUnsupported" in str(e):
            print("해결 방법: 서버가 이벤트 구독을 지원하지 않습니다.")
        else:
            print("일반적인 해결 방법:")
            print("1. 서버 연결 상태 확인")
            print("2. 서버가 이벤트를 지원하는지 확인")
            print("3. 다른 이벤트 소스/타입 시도")

async def main():
    global session_manager, current_session_id, subscription_lists
    
    while True:
        try:
            choice = await display_menu()
            
            try:
                if choice == '99' or choice.lower() == 'q':
                    # Clean up before exit
                    try:
                        await session_manager.close_all_sessions()
                    except Exception as e:
                        logger.warning(f"Error closing sessions: {e}")
                    print("\nExiting OPC UA Client. Goodbye!")
                    break
                
                elif choice == '0':  # List Endpoints
                    await list_endpoints()
                
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
                    
                elif choice == '15':  # Event View (이벤트 전용 뷰)
                    client_connection, reconnected = await check_and_reconnect()
                    if client_connection:
                        # Event View는 독립적으로 실행되므로 기존 구독과 별개로 처리
                        await enter_event_view(client_connection)
                
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