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
        # Create a variable node to write to (for testing purposes)
        var_idx = await client.get_namespace_index("urn:example:testing")
        if var_idx == 0:  # If namespace doesn't exist, create it
            var_idx = await client.register_namespace("urn:example:testing")
        
        test_var = await client.nodes.objects.add_variable(
            ua.NodeId("TestWriteVar", var_idx),
            "TestWriteVar",
            42
        )
        
        # Read the current value
        test_var_id = test_var.nodeid.to_string()
        current_value = await node.read_node_attribute(client, test_var_id)
        print(f"Current value: {current_value}")
        
        # Write a new value
        new_value = 100
        await node.write_node_attribute(client, test_var_id, new_value)
        
        # Read the updated value
        updated_value = await node.read_node_attribute(client, test_var_id)
        print(f"Updated value: {updated_value}")
        
    finally:
        await connection.close_session(client)


async def example_call_method():
    """Example showing how to call a method without parameters."""
    server_url = "opc.tcp://mk:62541/Quickstarts/ReferenceServer"
    
    print("Calling a method without parameters...")
    client = await connection.create_session(server_url)
    
    try:
        # For testing, we'll need to create a method first
        var_idx = await client.get_namespace_index("urn:example:testing")
        if var_idx == 0:
            var_idx = await client.register_namespace("urn:example:testing")
        
        # Create a test method that returns the server current time
        test_object = await client.nodes.objects.add_object(
            ua.NodeId("TestObject", var_idx),
            "TestObject"
        )
        
        test_method = await test_object.add_method(
            ua.NodeId("TestMethod", var_idx),
            "TestMethod",
            lambda parent, *args: asyncio.get_event_loop().time(),
            [],  # no input arguments
            [ua.VariantType.Double]  # one output argument (a double)
        )
        
        # Call the method
        object_id = test_object.nodeid.to_string()
        method_id = test_method.nodeid.to_string()
        
        result = await method.call_method(client, object_id, method_id)
        print(f"Method call result: {result}")
        
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
        # For testing, we'll need to create a method with parameters
        var_idx = await client.get_namespace_index("urn:example:testing")
        if var_idx == 0:
            var_idx = await client.register_namespace("urn:example:testing")
        
        # Create a test method that adds two numbers
        test_object = await client.nodes.objects.add_object(
            ua.NodeId("TestParamObject", var_idx),
            "TestParamObject"
        )
        
        def add_method(parent, a, b):
            return [a + b]
        
        test_method = await test_object.add_method(
            ua.NodeId("AddMethod", var_idx),
            "AddMethod",
            add_method,
            [
                ua.VariantType.Int64,  # first input argument
                ua.VariantType.Int64   # second input argument
            ],
            [ua.VariantType.Int64]     # one output argument
        )
        
        # Call the method with parameters
        object_id = test_object.nodeid.to_string()
        method_id = test_method.nodeid.to_string()
        
        result = await method.call_method_with_params(
            client, 
            object_id, 
            method_id, 
            [10, 20]  # Input arguments: a=10, b=20
        )
        print(f"Method call result: {result}")  # Should be 30
        
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