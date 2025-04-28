"""
Example showing how to use the OpcUaClient class.
"""

import asyncio
import logging
import sys
sys.path.insert(0, '..')

from asyncua import ua

from opcua_client.client import OpcUaClient
from opcua_client.utils import setup_logging


# Callback functions for data changes and events
def data_change_callback(node, val, data):
    print(f"Data change from {node}: {val}")


def event_callback(event_data):
    print(f"Event received: {event_data}")


async def run_client_example():
    """Run a comprehensive example using the OpcUaClient class."""
    server_url = "opc.tcp://mk:62541/Quickstarts/ReferenceServer"
    
    # Create the client
    client = OpcUaClient(server_url)
    
    try:
        # Get endpoints
        print("Getting endpoints...")
        endpoints = await client.get_endpoints()
        print(f"Found {len(endpoints)} endpoints")
        
        # Connect to the server
        print("Connecting to the server...")
        await client.connect()
        print("Connected successfully")
        
        # Browse nodes
        print("\nBrowsing root node:")
        root_children = await client.browse_node()
        
        # Get some nodes to work with
        objects_node = client.client.nodes.objects
        
        # Create a test variable
        var_idx = await client.client.get_namespace_index("urn:example:testing")
        if var_idx == 0:  # If namespace doesn't exist, create it
            var_idx = await client.client.register_namespace("urn:example:testing")
        
        test_var = await client.client.nodes.objects.add_variable(
            ua.NodeId("TestClientVar", var_idx),
            "TestClientVar",
            42
        )
        
        # Read and write to the variable
        print("\nReading and writing to variable:")
        test_var_id = test_var.nodeid.to_string()
        
        # Read the initial value
        value = await client.read_node(test_var_id)
        print(f"Initial value: {value}")
        
        # Write a new value
        await client.write_node(test_var_id, 100)
        print("Wrote value: 100")
        
        # Read the updated value
        value = await client.read_node(test_var_id)
        print(f"Updated value: {value}")
        
        # Create a subscription
        print("\nCreating subscription:")
        sub = await client.create_subscription()
        
        # Subscribe to data changes
        handle = await client.subscribe_data_change(
            sub,
            test_var_id,
            data_change_callback
        )
        
        # Update the variable to trigger the callback
        print("Updating variable to trigger callback...")
        await client.write_node(test_var_id, 200)
        await asyncio.sleep(1)  # Wait for the callback to be triggered
        
        # Create a test method
        test_object = await client.client.nodes.objects.add_object(
            ua.NodeId("TestClientObject", var_idx),
            "TestClientObject"
        )
        
        def add_method(parent, a, b):
            return [a + b]
        
        test_method = await test_object.add_method(
            ua.NodeId("TestClientMethod", var_idx),
            "TestClientMethod",
            add_method,
            [
                ua.VariantType.Int64,  # first input argument
                ua.VariantType.Int64   # second input argument
            ],
            [ua.VariantType.Int64]     # one output argument
        )
        
        # Call the method
        print("\nCalling method:")
        object_id = test_object.nodeid.to_string()
        method_id = test_method.nodeid.to_string()
        
        result = await client.call_method_with_params(
            object_id,
            method_id,
            [10, 20]
        )
        print(f"Method call result: {result}")
        
        # Delete the subscription
        print("\nDeleting subscription...")
        await client.delete_subscription(sub)
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        # Disconnect from the server
        print("\nDisconnecting...")
        await client.disconnect()
        print("Disconnected")


if __name__ == "__main__":
    setup_logging(level=logging.INFO)
    asyncio.run(run_client_example()) 