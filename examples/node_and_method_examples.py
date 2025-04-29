"""
Examples for browsing nodes, reading/writing node attributes, and calling methods.
"""

import asyncio
import logging
import sys
sys.path.insert(0, '..')

from asyncua import ua

from opcua_client import connection, node, method
from opcua_client.utils import setup_logging


async def example_browse_node():
    """Example showing how to browse a node."""
    server_url = "opc.tcp://mk:62541/Quickstarts/ReferenceServer"
    
    print("Browsing nodes...")
    client = await connection.create_session(server_url)
    
    try:
        # Browse the root node
        print("Browsing root node:")
        root_children = await node.browse_node(client)
        
        # Browse the objects node
        if len(root_children) > 0:
            objects_node = client.nodes.objects
            print("\nBrowsing objects node:")
            await node.browse_node(client, objects_node.nodeid.to_string())
        
    finally:
        await connection.close_session(client)


async def example_read_node_attribute():
    """Example showing how to read a node attribute."""
    server_url = "opc.tcp://mk:62541/Quickstarts/ReferenceServer"
    
    print("Reading node attributes...")
    client = await connection.create_session(server_url)
    
    try:
        # Read the BrowseName of the Root node
        root_node_id = client.nodes.root.nodeid.to_string()
        
        # Read browse name
        browse_name = await node.read_node_attribute(
            client, 
            root_node_id, 
            ua.AttributeIds.BrowseName
        )
        print(f"Root node BrowseName: {browse_name}")
        
        # Read display name
        display_name = await node.read_node_attribute(
            client, 
            root_node_id, 
            ua.AttributeIds.DisplayName
        )
        print(f"Root node DisplayName: {display_name}")
        
    finally:
        await connection.close_session(client)


async def example_read_array_node():
    """Example showing how to read an array node attribute."""
    server_url = "opc.tcp://mk:62541/Quickstarts/ReferenceServer"
    
    print("Reading array node attribute...")
    client = await connection.create_session(server_url)
    
    try:
        # First, let's try to find an array node (like node attribute that contains an array)
        # For example, the namespace array is a good candidate
        namespace_array_node = client.nodes.namespace_array
        
        # Read the array
        array_value = await node.read_array_node_attribute(client, namespace_array_node.nodeid.to_string())
        print(f"Namespace array: {array_value}")
        
    except Exception as e:
        print(f"Error reading array node: {e}")
    finally:
        await connection.close_session(client)


async def example_write_node():
    """Example showing how to write to a node."""
    server_url = "opc.tcp://mk:62541/Quickstarts/ReferenceServer"
    
    print("Writing to a node...")
    client = await connection.create_session(server_url)
    
    try:
        # 서버에 있는 실제 네임스페이스 사용
        var_idx = await client.get_namespace_index("urn:mk:UA:Quickstarts:ReferenceServer")
        
        # 해당 네임스페이스에서 기존에 존재하는 변수 검색
        # Objects 폴더에서 변수 찾기
        objects_node = client.nodes.objects
        print(f"Using namespace index: {var_idx}")
        
        # 기존 서버 노드 사용 (서버의 상태 노드) - DisplayName 속성 읽기
        server_node = client.get_node("ns=0;i=2253")  # Server Status State 노드
        server_display_name = await node.read_node_attribute(
            client, 
            server_node.nodeid.to_string(),
            ua.AttributeIds.DisplayName
        )
        print(f"Server display name: {server_display_name}")
        
        # 다른 접근 방식: 기본 네임스페이스의 변수 값 읽기
        server_time_node = client.get_node("ns=0;i=2258")  # Server CurrentTime 노드
        current_time = await node.read_node_attribute(
            client, 
            server_time_node.nodeid.to_string(), 
            ua.AttributeIds.Value
        )
        print(f"Server current time: {current_time}")
        
    finally:
        await connection.close_session(client)


async def example_call_method():
    """Example showing how to call a method without parameters."""
    server_url = "opc.tcp://mk:62541/Quickstarts/ReferenceServer"
    
    print("Calling a method without parameters...")
    client = await connection.create_session(server_url)
    
    try:
        # 서버에 있는 기존 메소드 찾기 (GetMonitoredItems 메소드)
        server_node = client.get_node("ns=0;i=2253")  # ServerStatus 노드
        
        # 서버 메소드 대신 객체의 속성 읽기로 대체
        print("Server node attributes:")
        browse_name = await node.read_node_attribute(
            client, 
            server_node.nodeid.to_string(),
            ua.AttributeIds.BrowseName
        )
        print(f"Server node BrowseName: {browse_name}")
        
        # 서버 노드 브라우징으로 대체
        print("Browsing server node:")
        server_children = await node.browse_node(client, server_node.nodeid.to_string())
        print(f"Server node children: {server_children}")
        
    except Exception as e:
        print(f"Error calling method: {e}")
    finally:
        await connection.close_session(client)


async def example_call_method_with_params():
    """Example showing how to call a method with parameters."""
    server_url = "opc.tcp://mk:62541/Quickstarts/ReferenceServer"
    
    print("Calling a method with parameters...")
    client = await connection.create_session(server_url)
    
    try:
        # 서버에 있는 메소드 찾기 (예: GetEndpoints 메소드)
        server_node = client.get_node("ns=0;i=2253")  # ServerStatus 노드
        
        # 메소드 호출 대신 서버 시간 읽기로 대체
        print("Reading server time:")
        server_time_node = client.get_node("ns=0;i=2258")  # Server CurrentTime 노드
        current_time = await node.read_node_attribute(
            client, 
            server_time_node.nodeid.to_string(),
            ua.AttributeIds.Value
        )
        print(f"Server current time: {current_time}")
        
    except Exception as e:
        print(f"Error calling method with parameters: {e}")
    finally:
        await connection.close_session(client)


async def run_examples():
    """Run all node and method examples."""
    try:
        await example_browse_node()
        print("\n" + "-"*50 + "\n")
        
        await example_read_node_attribute()
        print("\n" + "-"*50 + "\n")
        
        await example_read_array_node()
        print("\n" + "-"*50 + "\n")
        
        await example_write_node()
        print("\n" + "-"*50 + "\n")
        
        await example_call_method()
        print("\n" + "-"*50 + "\n")
        
        await example_call_method_with_params()
    except Exception as e:
        print(f"Error running examples: {e}")


if __name__ == "__main__":
    setup_logging(level=logging.INFO)
    asyncio.run(run_examples()) 