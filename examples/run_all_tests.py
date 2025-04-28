"""
OPC UA 클라이언트의 모든 기능을 테스트하고 결과를 저장하는 스크립트
"""

import asyncio
import logging
import sys
import os
from datetime import datetime

# 현재 디렉토리를 sys.path에 추가해 모듈을 찾을 수 있게 함
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 같은 디렉토리의 예제 스크립트를 import
from examples.connection_examples import run_examples as run_connection_examples
from examples.node_and_method_examples import run_examples as run_node_method_examples
from examples.subscription_and_event_examples import run_examples as run_subscription_event_examples
from examples.client_example import run_client_example

from opcua_client.utils import setup_logging

SERVER_URL = "opc.tcp://mk:62541/Quickstarts/ReferenceServer"

async def run_all_tests():
    test_results = {}
    
    # 테스트 결과 저장 파일 준비
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    result_file = f"test_results_{timestamp}.txt"
    
    print(f"==== OPC UA 클라이언트 기능 테스트 시작 ====")
    print(f"테스트 서버: {SERVER_URL}")
    print(f"결과는 {result_file}에 저장됩니다.")
    
    with open(result_file, "w", encoding="utf-8") as f:
        f.write("==== OPC UA 클라이언트 기능 테스트 결과 ====\n\n")
        f.write(f"테스트 서버: {SERVER_URL}\n")
        f.write(f"테스트 시작 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        
        # 연결 테스트
        try:
            f.write("1. 연결 테스트\n")
            f.write("-" * 50 + "\n")
            print("\n1. 연결 테스트 실행 중...")
            await run_connection_examples()
            test_results["연결"] = "성공"
            f.write("결과: 성공\n\n")
        except Exception as e:
            test_results["연결"] = f"실패: {str(e)}"
            f.write(f"결과: 실패 - {str(e)}\n\n")
            print(f"연결 테스트 실패: {e}")
        
        # 노드 및 메서드 테스트
        try:
            f.write("2. 노드 및 메서드 테스트\n")
            f.write("-" * 50 + "\n")
            print("\n2. 노드 및 메서드 테스트 실행 중...")
            await run_node_method_examples()
            test_results["노드 및 메서드"] = "성공"
            f.write("결과: 성공\n\n")
        except Exception as e:
            test_results["노드 및 메서드"] = f"실패: {str(e)}"
            f.write(f"결과: 실패 - {str(e)}\n\n")
            print(f"노드 및 메서드 테스트 실패: {e}")
        
        # 구독 및 이벤트 테스트
        try:
            f.write("3. 구독 및 이벤트 테스트\n")
            f.write("-" * 50 + "\n")
            print("\n3. 구독 및 이벤트 테스트 실행 중...")
            await run_subscription_event_examples()
            test_results["구독 및 이벤트"] = "성공"
            f.write("결과: 성공\n\n")
        except Exception as e:
            test_results["구독 및 이벤트"] = f"실패: {str(e)}"
            f.write(f"결과: 실패 - {str(e)}\n\n")
            print(f"구독 및 이벤트 테스트 실패: {e}")
        
        # 클라이언트 통합 테스트
        try:
            f.write("4. 클라이언트 통합 테스트\n")
            f.write("-" * 50 + "\n")
            print("\n4. 클라이언트 통합 테스트 실행 중...")
            await run_client_example()
            test_results["클라이언트 통합"] = "성공"
            f.write("결과: 성공\n\n")
        except Exception as e:
            test_results["클라이언트 통합"] = f"실패: {str(e)}"
            f.write(f"결과: 실패 - {str(e)}\n\n")
            print(f"클라이언트 통합 테스트 실패: {e}")
        
        # 테스트 요약
        f.write("\n==== 테스트 요약 ====\n")
        for key, value in test_results.items():
            f.write(f"{key}: {value}\n")
        
        f.write(f"\n테스트 종료 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    print("\n==== 테스트 요약 ====")
    for key, value in test_results.items():
        print(f"{key}: {value}")
    
    print(f"\n모든 테스트가 완료되었습니다. 결과는 {result_file}에 저장되었습니다.")

if __name__ == "__main__":
    setup_logging(level=logging.INFO)
    asyncio.run(run_all_tests()) 