"""
Examples for connecting to OPC UA servers.
"""

import asyncio
import logging
import sys
sys.path.insert(0, '..')

from opcua_client import connection
from opcua_client.utils import setup_logging


async def example_get_endpoints():
    """Example showing how to get endpoints from a server."""
    server_url = "opc.tcp://mk:62541/Quickstarts/ReferenceServer"
    
    print("Getting endpoints from server...")
    endpoints = await connection.get_endpoints(server_url)
    print(f"Found {len(endpoints)} endpoints")
    
    return endpoints


async def example_session_without_security():
    """Example showing how to create a session without security."""
    server_url = "opc.tcp://mk:62541/Quickstarts/ReferenceServer"
    
    print("Creating session without security...")
    client = await connection.create_session(server_url, security=False)
    print("Session created successfully")
    
    # Do something with the client
    namespace_array = await client.get_namespace_array()
    print(f"Server namespaces: {namespace_array}")
    
    # Close the session
    await connection.close_session(client)
    print("Session closed")
    
    return client


async def example_activate_session():
    """Example showing how to activate a session."""
    server_url = "opc.tcp://mk:62541/Quickstarts/ReferenceServer"
    
    print("Creating and activating session...")
    client = await connection.create_session(server_url)
    activated = await connection.activate_session(client)
    
    if activated:
        print("Session activated successfully")
    else:
        print("Failed to activate session")
    
    # Close the session
    await connection.close_session(client)
    print("Session closed")


async def example_multiple_sessions():
    """Example showing how to manage multiple sessions."""
    server_url = "opc.tcp://mk:62541/Quickstarts/ReferenceServer"
    
    print("Creating multiple sessions...")
    session_manager = connection.MultiSessionManager()
    
    # Create several sessions
    client1 = await session_manager.create_session("session1", server_url)
    client2 = await session_manager.create_session("session2", server_url)
    
    print("Sessions created successfully")
    
    # Use sessions
    for session_id in ["session1", "session2"]:
        client = session_manager.get_session(session_id)
        if client:
            namespace_array = await client.get_namespace_array()
            print(f"Session {session_id} namespaces: {namespace_array}")
    
    # Close all sessions
    await session_manager.close_all_sessions()
    print("All sessions closed")


async def run_examples():
    """Run all connection examples."""
    try:
        await example_get_endpoints()
        print("\n" + "-"*50 + "\n")
        
        await example_session_without_security()
        print("\n" + "-"*50 + "\n")
        
        await example_activate_session()
        print("\n" + "-"*50 + "\n")
        
        await example_multiple_sessions()
    except Exception as e:
        print(f"Error running examples: {e}")


if __name__ == "__main__":
    setup_logging(level=logging.INFO)
    asyncio.run(run_examples()) 