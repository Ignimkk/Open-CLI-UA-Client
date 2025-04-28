"""
UA Reference 서버 특화 테스트 스크립트
"""

import asyncio
import logging
import sys
import os
from datetime import datetime

# 현재 디렉토리를 sys.path에 추가해 모듈을 찾을 수 있게 함
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from asyncua import ua

from opcua_client.client import OpcUaClient
from opcua_client.utils import setup_logging

SERVER_URL = "opc.tcp://mk:62541/Quickstarts/ReferenceServer"

async def explore_reference_server():
    """UA Reference 서버의 특정 노드 구조와 기능을 탐색합니다."""
    client = OpcUaClient(SERVER_URL)
    
    try:
        # 서버에 연결
        print("UA Reference 서버에 연결 중...")
        await client.connect()
        print("서버에 연결되었습니다.")
        
        # 루트 노드 탐색
        print("\n루트 노드 탐색:")
        root_children = await client.browse_node()
        
        # Objects 폴더 탐색
        objects_node = client.client.nodes.objects
        print("\nObjects 폴더 탐색:")
        objects_children = await client.browse_node(objects_node.nodeid.to_string())
        
        # Server 객체 탐색
        server_node = client.client.nodes.server
        print("\nServer 객체 탐색:")
        await client.browse_node(server_node.nodeid.to_string())
        
        # 서버 상태 읽기
        try:
            server_status_node = await server_node.get_child([ua.QualifiedName(0, "ServerStatus")])
            server_status = await client.read_node(server_status_node.nodeid.to_string())
            print(f"\n서버 상태: {server_status}")
        except Exception as e:
            print(f"서버 상태 읽기 실패: {e}")
        
        # 네임스페이스 배열 읽기
        try:
            ns_array = await client.read_array_node(client.client.nodes.namespace_array.nodeid.to_string())
            print("\n네임스페이스 배열:")
            for i, ns in enumerate(ns_array):
                print(f"  {i}: {ns}")
        except Exception as e:
            print(f"네임스페이스 배열 읽기 실패: {e}")
            
        # 변수 노드 찾기 및 읽기/쓰기 테스트
        print("\n변수 노드 찾기 및 읽기/쓰기 테스트:")
        try:
            # 일반적으로 UA Reference 서버에는 몇 가지 표준 변수들이 있습니다
            # Boiler 예제가 있는 경우를 대비한 코드
            boiler_node = None
            
            # Objects 폴더에서 Boiler 노드 찾기 시도
            for child in objects_children:
                name = await child.read_browse_name()
                if "Boiler" in str(name):
                    boiler_node = child
                    print(f"Boiler 노드 발견: {name}")
                    break
            
            if boiler_node:
                # Boiler 노드의 자식 탐색
                boiler_children = await client.browse_node(boiler_node.nodeid.to_string())
                
                # 변수 노드 찾기
                for child in boiler_children:
                    name = await child.read_browse_name()
                    node_class = await child.read_attribute(ua.AttributeIds.NodeClass)
                    
                    if node_class.Value.Value == ua.NodeClass.Variable:
                        print(f"변수 노드 발견: {name}")
                        node_id = child.nodeid.to_string()
                        
                        # 현재 값 읽기
                        value = await client.read_node(node_id)
                        print(f"  현재 값: {value}")
                        
                        # 값이 쓰기 가능한지 확인
                        try:
                            writable = await child.read_attribute(ua.AttributeIds.UserWriteMask)
                            if writable.Value.Value > 0:
                                # 쓰기 가능한 경우 값 쓰기 시도
                                if isinstance(value, (int, float)):
                                    new_value = value + 1
                                    await client.write_node(node_id, new_value)
                                    print(f"  새 값 쓰기 성공: {new_value}")
                                    
                                    # 다시 읽어서 확인
                                    updated_value = await client.read_node(node_id)
                                    print(f"  업데이트된 값: {updated_value}")
                        except Exception as e:
                            print(f"  쓰기 테스트 중 오류: {e}")
                        break
            else:
                print("Boiler 노드를 찾을 수 없습니다. 다른 노드에서 시도합니다.")
                
                # 대체 시도: 쓰기 가능한 변수를 찾아봅니다
                server_speed_node = None
                try:
                    # 몇 가지 일반적인 변수 이름을 시도
                    test_paths = [
                        [ua.QualifiedName(0, "Objects"), ua.QualifiedName(2, "DeviceSet"), ua.QualifiedName(2, "Device_1"), ua.QualifiedName(2, "Speed")],
                        [ua.QualifiedName(0, "Objects"), ua.QualifiedName(2, "Server"), ua.QualifiedName(2, "ServerStatus"), ua.QualifiedName(2, "CurrentTime")],
                    ]
                    
                    for path in test_paths:
                        try:
                            test_node = await client.client.nodes.root.get_child(path)
                            node_id = test_node.nodeid.to_string()
                            name = await test_node.read_browse_name()
                            print(f"테스트할 변수 노드: {name}")
                            
                            # 현재 값 읽기
                            value = await client.read_node(node_id)
                            print(f"  현재 값: {value}")
                            break
                        except Exception:
                            continue
                except Exception as e:
                    print(f"대체 변수 노드 찾기 실패: {e}")
        
        except Exception as e:
            print(f"변수 테스트 중 오류: {e}")
                    
        # 메서드 노드 찾기 및 호출 테스트
        print("\n메서드 노드 찾기 및 호출 테스트:")
        try:
            # 서버에서 GetMonitoredItems 메서드 찾기 시도
            subscription_diagnostics_node = None
            try:
                subscription_diagnostics_node = await server_node.get_child([ua.QualifiedName(0, "ServerDiagnostics"), ua.QualifiedName(0, "SubscriptionDiagnosticsArray")])
                print("SubscriptionDiagnosticsArray 노드 발견")
            except Exception:
                print("SubscriptionDiagnosticsArray 노드를 찾을 수 없습니다.")
            
            # 서버 메서드 중 하나 찾기 시도
            for child in await server_node.get_children():
                try:
                    name = await child.read_browse_name()
                    node_class = await child.read_attribute(ua.AttributeIds.NodeClass)
                    
                    if node_class.Value.Value == ua.NodeClass.Method:
                        print(f"메서드 노드 발견: {name}")
                        object_id = server_node.nodeid.to_string()
                        method_id = child.nodeid.to_string()
                        
                        # 메서드 호출 시도
                        try:
                            result = await client.call_method(object_id, method_id)
                            print(f"  메서드 호출 결과: {result}")
                        except Exception as e:
                            print(f"  메서드 호출 실패 (매개변수가 필요할 수 있음): {e}")
                        break
                except Exception:
                    continue
        except Exception as e:
            print(f"메서드 테스트 중 오류: {e}")
        
        # 구독 및 모니터링 테스트
        print("\n구독 및 모니터링 테스트:")
        try:
            # 데이터 변경 콜백 함수
            def data_change_callback(node, val, data):
                print(f"데이터 변경 감지: 노드={node}, 값={val}")
            
            # 구독 생성
            sub = await client.create_subscription(period=1000)
            print("구독 생성됨")
            
            # 서버 시간 노드 모니터링
            try:
                server_time_node = await server_node.get_child([ua.QualifiedName(0, "ServerStatus"), ua.QualifiedName(0, "CurrentTime")])
                handle = await client.subscribe_data_change(
                    sub,
                    server_time_node.nodeid.to_string(),
                    data_change_callback
                )
                print("서버 시간 노드 모니터링 중...")
                
                # 잠시 대기하면서 콜백 실행 확인
                print("5초 동안 데이터 변경 모니터링...")
                await asyncio.sleep(5)
                
                # 구독 삭제
                await client.delete_subscription(sub)
                print("구독 삭제됨")
            except Exception as e:
                print(f"서버 시간 모니터링 실패: {e}")
                
                # 다른 노드 시도
                try:
                    print("다른 노드에서 모니터링 시도...")
                    for child in await server_node.get_children():
                        try:
                            node_class = await child.read_attribute(ua.AttributeIds.NodeClass)
                            if node_class.Value.Value == ua.NodeClass.Variable:
                                handle = await client.subscribe_data_change(
                                    sub,
                                    child.nodeid.to_string(),
                                    data_change_callback
                                )
                                name = await child.read_browse_name()
                                print(f"{name} 노드 모니터링 중...")
                                await asyncio.sleep(5)
                                break
                        except Exception:
                            continue
                except Exception as e:
                    print(f"대체 노드 모니터링 실패: {e}")
                
                # 구독 정리
                try:
                    await client.delete_subscription(sub)
                    print("구독 삭제됨")
                except Exception:
                    pass
        except Exception as e:
            print(f"구독 테스트 중 오류: {e}")
            
    except Exception as e:
        print(f"테스트 중 오류 발생: {e}")
    finally:
        # 연결 종료
        await client.disconnect()
        print("\n서버 연결이 종료되었습니다.")

if __name__ == "__main__":
    setup_logging(level=logging.INFO)
    asyncio.run(explore_reference_server()) 