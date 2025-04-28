"""
예제 파일의 서버 URL을 UA Reference 서버 URL로 업데이트하는 스크립트
"""

import re
import os
import sys

# 현재 디렉토리를 기준으로 경로 설정
EXAMPLES_DIR = os.path.dirname(os.path.abspath(__file__))

def update_server_url_in_file(file_path, new_url):
    with open(file_path, 'r') as f:
        content = f.read()
    
    # "opc.tcp://localhost:4840/freeopcua/server/" 같은 형식의 URL을 찾아 대체
    updated_content = re.sub(
        r'server_url = "opc\.tcp://[^"]*"', 
        f'server_url = "{new_url}"', 
        content
    )
    
    with open(file_path, 'w') as f:
        f.write(updated_content)
    
    print(f"Updated URL in {file_path}")

def main():
    new_url = "opc.tcp://mk:62541/Quickstarts/ReferenceServer"
    example_files = [
        os.path.join(EXAMPLES_DIR, "connection_examples.py"),
        os.path.join(EXAMPLES_DIR, "node_and_method_examples.py"),
        os.path.join(EXAMPLES_DIR, "subscription_and_event_examples.py"),
        os.path.join(EXAMPLES_DIR, "client_example.py")
    ]
    
    for file in example_files:
        if os.path.exists(file):
            update_server_url_in_file(file, new_url)
        else:
            print(f"Warning: File not found: {file}")

if __name__ == "__main__":
    main() 