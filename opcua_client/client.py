"""
Main client module for OPC UA client.

This module combines all the functionality from other modules.
"""

import asyncio
import logging
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

from asyncua import Client, ua
from asyncua.common.node import Node
from asyncua.common.subscription import Subscription

from opcua_client import connection, node, method, subscription, event, utils

logger = logging.getLogger(__name__)


class OpcUaClient:
    """
    OPC UA client class that combines all functionality.
    """
    
    def __init__(self, server_url: str):
        """
        Initialize the OPC UA client.
        
        Args:
            server_url: The URL of the OPC UA server
        """
        self.server_url = server_url
        self.client = None
        self.subscriptions = []
        
    async def connect(self, security: bool = False) -> None:
        """
        Connect to the OPC UA server.
        
        Args:
            security: Whether to use security (default: False)
        """
        self.client = await connection.create_session(self.server_url, security)
        logger.info(f"Connected to {self.server_url}")
        
    async def disconnect(self) -> None:
        """
        Disconnect from the OPC UA server.
        """
        if self.client:
            # Delete all subscriptions
            for sub in self.subscriptions:
                try:
                    await subscription.delete_subscription(sub)
                except Exception as e:
                    logger.error(f"Error deleting subscription: {e}")
                    
            # Close the session
            await connection.close_session(self.client)
            self.client = None
            logger.info("Disconnected from the server")
            
    async def get_endpoints(self) -> List[ua.EndpointDescription]:
        """
        Get available endpoints from the server.
        
        Returns:
            List of endpoint descriptions
        """
        return await connection.get_endpoints(self.server_url)
        
    async def browse_node(self, node_id: Optional[str] = None) -> List[Node]:
        """
        Browse a single node and return its children.
        
        Args:
            node_id: The ID of the node to browse (None for root node)
            
        Returns:
            List of child nodes
        """
        self._check_connection()
        return await node.browse_node(self.client, node_id)
        
    async def read_node(self, node_id: str, attribute: ua.AttributeIds = ua.AttributeIds.Value) -> Any:
        """
        Read an attribute from a node.
        
        Args:
            node_id: The ID of the node to read from
            attribute: The attribute to read (default: Value)
            
        Returns:
            The value of the attribute
        """
        self._check_connection()
        return await node.read_node_attribute(self.client, node_id, attribute)
        
    async def read_array_node(self, node_id: str) -> List[Any]:
        """
        Read an array attribute from a node.
        
        Args:
            node_id: The ID of the node to read from
            
        Returns:
            List of values
        """
        self._check_connection()
        return await node.read_array_node_attribute(self.client, node_id)
        
    async def write_node(
        self,
        node_id: str,
        value: Any,
        attribute: ua.AttributeIds = ua.AttributeIds.Value
    ) -> None:
        """
        Write a value to a node attribute.
        
        Args:
            node_id: The ID of the node to write to
            value: The value to write
            attribute: The attribute to write to (default: Value)
        """
        self._check_connection()
        await node.write_node_attribute(self.client, node_id, value, attribute)
        
    async def call_method(self, object_id: str, method_id: str) -> Any:
        """
        Call a method without input or output parameters.
        
        Args:
            object_id: The ID of the object node that contains the method
            method_id: The ID of the method node to call
            
        Returns:
            Result of the method call
        """
        self._check_connection()
        return await method.call_method(self.client, object_id, method_id)
        
    async def call_method_with_params(
        self,
        object_id: str,
        method_id: str,
        input_args: List[Any]
    ) -> Any:
        """
        Call a method with input parameters and return output parameters.
        
        Args:
            object_id: The ID of the object node that contains the method
            method_id: The ID of the method node to call
            input_args: List of input arguments for the method
            
        Returns:
            Result of the method call (typically a list of output arguments)
        """
        self._check_connection()
        return await method.call_method_with_params(self.client, object_id, method_id, input_args)
        
    async def create_subscription(
        self,
        period: float = 500,
        callback: Optional[Callable[[Node, Any, Any], None]] = None,
        node_id: Optional[str] = None
    ) -> Subscription:
        """
        Create a subscription.
        
        Args:
            period: The publishing interval in milliseconds
            callback: Optional callback function for data changes
            node_id: Optional node ID to subscribe to
            
        Returns:
            Subscription object
        """
        self._check_connection()
        sub = await subscription.create_subscription(self.client, period)
        self.subscriptions.append(sub)
        
        # If node_id and callback are provided, subscribe to data changes
        if node_id and callback:
            await subscription.subscribe_data_change(sub, node_id, callback)
            
        return sub
        
    async def subscribe_data_change(
        self,
        sub: Subscription,
        node_id: str,
        callback: Callable[[Node, Any, Any], None],
        sampling_interval: float = 100
    ) -> int:
        """
        Subscribe to data changes for a specific node.
        
        Args:
            sub: The subscription to use
            node_id: The ID of the node to subscribe to
            callback: The callback function to be called when the data changes
            sampling_interval: The sampling interval in milliseconds
            
        Returns:
            Handle ID for the monitored item
        """
        self._check_connection()
        return await subscription.subscribe_data_change(
            sub, node_id, callback, sampling_interval
        )
        
    async def subscribe_events(
        self,
        sub: Subscription,
        node_id: str,
        callback: Callable[[Any], None],
        event_filter: Optional[ua.EventFilter] = None
    ) -> int:
        """
        Subscribe to events from a specific node.
        
        Args:
            sub: The subscription to use
            node_id: The ID of the node to subscribe to
            callback: The callback function to be called when an event is received
            event_filter: Optional event filter to use
            
        Returns:
            Handle ID for the monitored item
        """
        self._check_connection()
        return await event.subscribe_events(sub, node_id, callback, event_filter)
        
    async def delete_subscription(self, sub: Subscription) -> None:
        """
        Delete a subscription.
        
        Args:
            sub: The subscription to delete
        """
        self._check_connection()
        await subscription.delete_subscription(sub)
        if sub in self.subscriptions:
            self.subscriptions.remove(sub)
            
    def _check_connection(self) -> None:
        """
        Check if the client is connected to the server.
        
        Raises:
            RuntimeError: If the client is not connected
        """
        if not self.client:
            raise RuntimeError("Client is not connected to the server") 