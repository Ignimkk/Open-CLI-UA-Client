"""
Examples for subscriptions, monitored items, and event handling.
"""

import asyncio
import logging
import sys
sys.path.insert(0, '..')

from asyncua import ua

from opcua_client import connection, subscription, event
from opcua_client.utils import setup_logging


# Define callback functions for data changes and events
def data_change_callback(node, val, data):
    print(f"Data change from {node}: {val}")


def event_callback(event_data):
    print(f"Event received: {event_data}")


async def example_empty_subscription():
    """Example showing how to create an empty subscription."""
    server_url = "opc.tcp://mk:62541/Quickstarts/ReferenceServer"
    
    print("Creating empty subscription...")
    client = await connection.create_session(server_url)
    
    try:
        # Create an empty subscription
        sub = await subscription.create_subscription(client, period=500)
        print(f"Created subscription with ID {sub.subscription_id}")
        
        # Let it run for a while
        await asyncio.sleep(2)
        
        # Delete the subscription
        await subscription.delete_subscription(sub)
        print("Subscription deleted")
        
    finally:
        await connection.close_session(client)


async def example_modify_subscription():
    """Example showing how to modify a subscription."""
    server_url = "opc.tcp://mk:62541/Quickstarts/ReferenceServer"
    
    print("Modifying subscription...")
    client = await connection.create_session(server_url)
    
    try:
        # Create a subscription
        sub = await subscription.create_subscription(client, period=1000)
        print(f"Created subscription with period 1000ms")
        
        # Let it run for a while
        await asyncio.sleep(2)
        
        # Modify the subscription to have a faster publishing interval
        await subscription.modify_subscription(sub, period=200)
        print(f"Modified subscription to period 200ms")
        
        # Let it run for a while
        await asyncio.sleep(2)
        
        # Delete the subscription
        await subscription.delete_subscription(sub)
        print("Subscription deleted")
        
    finally:
        await connection.close_session(client)


async def example_subscription_publishing_mode():
    """Example showing how to set the publishing mode of a subscription."""
    server_url = "opc.tcp://mk:62541/Quickstarts/ReferenceServer"
    
    print("Setting subscription publishing mode...")
    client = await connection.create_session(server_url)
    
    try:
        # Create a subscription
        sub = await subscription.create_subscription(client)
        print(f"Created subscription with ID {sub.subscription_id}")
        
        # Create a variable to monitor
        var_idx = await client.get_namespace_index("urn:example:testing")
        if var_idx == 0:  # If namespace doesn't exist, create it
            var_idx = await client.register_namespace("urn:example:testing")
        
        test_var = await client.nodes.objects.add_variable(
            ua.NodeId("MonitoredVar", var_idx),
            "MonitoredVar",
            0
        )
        
        # Subscribe to data changes
        handle = await subscription.subscribe_data_change(
            sub, 
            test_var.nodeid.to_string(), 
            data_change_callback
        )
        
        # Disable publishing
        await subscription.set_publishing_mode(sub, False)
        print("Publishing mode disabled")
        
        # Update the variable (should not trigger callback)
        await test_var.write_value(1)
        print("Updated variable to 1 (no notification expected)")
        await asyncio.sleep(1)
        
        # Enable publishing
        await subscription.set_publishing_mode(sub, True)
        print("Publishing mode enabled")
        
        # Update the variable (should trigger callback)
        await test_var.write_value(2)
        print("Updated variable to 2 (notification expected)")
        await asyncio.sleep(1)
        
        # Delete the subscription
        await subscription.delete_subscription(sub)
        print("Subscription deleted")
        
    except Exception as e:
        print(f"Error in publishing mode example: {e}")
    finally:
        await connection.close_session(client)


async def example_data_change_subscription():
    """Example showing how to subscribe to data changes."""
    server_url = "opc.tcp://mk:62541/Quickstarts/ReferenceServer"
    
    print("Subscribing to data changes...")
    client = await connection.create_session(server_url)
    
    try:
        # Create a subscription
        sub = await subscription.create_subscription(client, period=200)
        print(f"Created subscription with ID {sub.subscription_id}")
        
        # Create a variable to monitor
        var_idx = await client.get_namespace_index("urn:example:testing")
        if var_idx == 0:  # If namespace doesn't exist, create it
            var_idx = await client.register_namespace("urn:example:testing")
        
        test_var = await client.nodes.objects.add_variable(
            ua.NodeId("MonitoredVar2", var_idx),
            "MonitoredVar2",
            0
        )
        
        # Subscribe to data changes
        handle = await subscription.subscribe_data_change(
            sub, 
            test_var.nodeid.to_string(), 
            data_change_callback,
            sampling_interval=100
        )
        
        # Update the variable several times
        for i in range(1, 6):
            await test_var.write_value(i)
            print(f"Updated variable to {i}")
            await asyncio.sleep(0.5)
        
        # Delete the subscription
        await subscription.delete_subscription(sub)
        print("Subscription deleted")
        
    finally:
        await connection.close_session(client)


async def example_keep_alive():
    """Example showing how to keep the connection alive."""
    server_url = "opc.tcp://mk:62541/Quickstarts/ReferenceServer"
    
    print("Keeping connection alive...")
    client = await connection.create_session(server_url)
    
    try:
        print("Starting keep-alive for 5 seconds...")
        await subscription.keep_alive(client, duration=5)
        print("Keep-alive completed")
        
    finally:
        await connection.close_session(client)


async def example_parallel_subscriptions():
    """Example showing how to create parallel subscriptions."""
    server_url = "opc.tcp://mk:62541/Quickstarts/ReferenceServer"
    
    print("Creating parallel subscriptions...")
    client = await connection.create_session(server_url)
    
    try:
        # Create variables to monitor
        var_idx = await client.get_namespace_index("urn:example:testing")
        if var_idx == 0:  # If namespace doesn't exist, create it
            var_idx = await client.register_namespace("urn:example:testing")
        
        vars_to_monitor = []
        for i in range(3):
            test_var = await client.nodes.objects.add_variable(
                ua.NodeId(f"ParallelVar{i}", var_idx),
                f"ParallelVar{i}",
                i
            )
            vars_to_monitor.append(test_var.nodeid.to_string())
        
        # Create parallel subscriptions (2 subscriptions for 3 variables)
        subs = await subscription.create_parallel_subscriptions(
            client,
            vars_to_monitor,
            data_change_callback,
            count=2,
            period=200
        )
        
        print(f"Created {len(subs)} subscriptions")
        
        # Update the variables
        for i, var_id in enumerate(vars_to_monitor):
            var_node = client.get_node(var_id)
            await var_node.write_value(i + 10)
            print(f"Updated variable {i} to {i + 10}")
        
        # Let the callbacks run
        await asyncio.sleep(1)
        
        # Delete the subscriptions
        for sub in subs:
            await subscription.delete_subscription(sub)
        print("Subscriptions deleted")
        
    finally:
        await connection.close_session(client)


async def example_event_subscription():
    """Example showing how to subscribe to events."""
    server_url = "opc.tcp://mk:62541/Quickstarts/ReferenceServer"
    
    print("Subscribing to events...")
    client = await connection.create_session(server_url)
    
    try:
        # Create a subscription
        sub = await subscription.create_subscription(client, period=500)
        print(f"Created subscription with ID {sub.subscription_id}")
        
        # Subscribe to events from the server object
        server_node = client.nodes.server
        handle = await event.subscribe_events(
            sub,
            server_node.nodeid.to_string(),
            event_callback
        )
        
        print("Subscribed to events, waiting for events to occur...")
        # Let it run for a while (in a real scenario, events would be triggered by the server)
        await asyncio.sleep(5)
        
        # Delete the subscription
        await subscription.delete_subscription(sub)
        print("Subscription deleted")
        
    except Exception as e:
        print(f"Error in event subscription example: {e}")
    finally:
        await connection.close_session(client)


async def example_monitored_item():
    """Example showing how to add, modify, and delete monitored items."""
    server_url = "opc.tcp://mk:62541/Quickstarts/ReferenceServer"
    
    print("Working with monitored items...")
    client = await connection.create_session(server_url)
    
    try:
        # Create a subscription
        sub = await subscription.create_subscription(client, period=500)
        print(f"Created subscription with ID {sub.subscription_id}")
        
        # Create a variable to monitor
        var_idx = await client.get_namespace_index("urn:example:testing")
        if var_idx == 0:  # If namespace doesn't exist, create it
            var_idx = await client.register_namespace("urn:example:testing")
        
        test_var = await client.nodes.objects.add_variable(
            ua.NodeId("MonitoredItemVar", var_idx),
            "MonitoredItemVar",
            0
        )
        
        # Add a monitored item
        handle = await event.add_monitored_item(
            sub,
            test_var.nodeid.to_string(),
            data_change_callback,
            sampling_interval=1000
        )
        print(f"Added monitored item with handle {handle}")
        
        # Update the variable
        await test_var.write_value(1)
        print("Updated variable to 1")
        await asyncio.sleep(2)
        
        # Modify the monitored item to have a faster sampling rate
        await event.modify_monitored_item(
            sub,
            handle,
            sampling_interval=100
        )
        print("Modified monitored item to have faster sampling rate")
        
        # Update the variable again
        await test_var.write_value(2)
        print("Updated variable to 2")
        await asyncio.sleep(1)
        
        # Delete the monitored item
        await event.delete_monitored_item(sub, handle)
        print("Deleted monitored item")
        
        # Update the variable again (should not trigger callback)
        await test_var.write_value(3)
        print("Updated variable to 3 (no notification expected)")
        await asyncio.sleep(1)
        
        # Delete the subscription
        await subscription.delete_subscription(sub)
        print("Subscription deleted")
        
    finally:
        await connection.close_session(client)


async def example_monitoring_mode():
    """Example showing how to set the monitoring mode."""
    server_url = "opc.tcp://mk:62541/Quickstarts/ReferenceServer"
    
    print("Setting monitoring mode...")
    client = await connection.create_session(server_url)
    
    try:
        # Create a subscription
        sub = await subscription.create_subscription(client, period=500)
        print(f"Created subscription with ID {sub.subscription_id}")
        
        # Create a variable to monitor
        var_idx = await client.get_namespace_index("urn:example:testing")
        if var_idx == 0:  # If namespace doesn't exist, create it
            var_idx = await client.register_namespace("urn:example:testing")
        
        test_var = await client.nodes.objects.add_variable(
            ua.NodeId("MonitoringModeVar", var_idx),
            "MonitoringModeVar",
            0
        )
        
        # Add a monitored item
        handle = await event.add_monitored_item(
            sub,
            test_var.nodeid.to_string(),
            data_change_callback
        )
        print(f"Added monitored item with handle {handle}")
        
        # Update the variable (should trigger callback)
        await test_var.write_value(1)
        print("Updated variable to 1 (notification expected)")
        await asyncio.sleep(1)
        
        # Set monitoring mode to Disabled
        await event.set_monitoring_mode(
            sub,
            handle,
            ua.MonitoringMode.Disabled
        )
        print("Set monitoring mode to Disabled")
        
        # Update the variable (should not trigger callback)
        await test_var.write_value(2)
        print("Updated variable to 2 (no notification expected)")
        await asyncio.sleep(1)
        
        # Set monitoring mode back to Reporting
        await event.set_monitoring_mode(
            sub,
            handle,
            ua.MonitoringMode.Reporting
        )
        print("Set monitoring mode to Reporting")
        
        # Update the variable (should trigger callback)
        await test_var.write_value(3)
        print("Updated variable to 3 (notification expected)")
        await asyncio.sleep(1)
        
        # Delete the subscription
        await subscription.delete_subscription(sub)
        print("Subscription deleted")
        
    finally:
        await connection.close_session(client)


async def run_examples():
    """Run all subscription and event examples."""
    try:
        await example_empty_subscription()
        print("\n" + "-"*50 + "\n")
        
        await example_modify_subscription()
        print("\n" + "-"*50 + "\n")
        
        await example_subscription_publishing_mode()
        print("\n" + "-"*50 + "\n")
        
        await example_data_change_subscription()
        print("\n" + "-"*50 + "\n")
        
        await example_keep_alive()
        print("\n" + "-"*50 + "\n")
        
        await example_parallel_subscriptions()
        print("\n" + "-"*50 + "\n")
        
        await example_event_subscription()
        print("\n" + "-"*50 + "\n")
        
        await example_monitored_item()
        print("\n" + "-"*50 + "\n")
        
        await example_monitoring_mode()
    except Exception as e:
        print(f"Error running examples: {e}")


if __name__ == "__main__":
    setup_logging(level=logging.INFO)
    asyncio.run(run_examples())