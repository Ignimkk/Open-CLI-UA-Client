"""
Connection module for OPC UA client.

This module provides functions to manage connections to OPC UA servers.
"""

import asyncio
import logging
from typing import Dict, List, Optional, Tuple

from asyncua import Client
from asyncua.common.node import Node
from asyncua.crypto.security_policies import SecurityPolicyBasic256Sha256
from asyncua.ua import EndpointDescription, MessageSecurityMode

logger = logging.getLogger(__name__)


async def get_endpoints(server_url: str) -> List[EndpointDescription]:
    """
    Get available endpoints from the server.
    
    Args:
        server_url: The URL of the OPC UA server
        
    Returns:
        List of endpoint descriptions
    """
    client = Client(server_url)
    try:
        endpoints = await client.connect_and_get_server_endpoints()
        for i, endpoint in enumerate(endpoints):
            logger.info(f"Endpoint {i}: {endpoint.security_mode} {endpoint.security_policy_uri}")
        return endpoints
    finally:
        await client.disconnect()


async def create_session(server_url: str, security: bool = False) -> Client:
    """
    Create a session without security.
    
    Args:
        server_url: The URL of the OPC UA server
        security: Whether to use security (default: False)
        
    Returns:
        Client instance
    """
    client = Client(server_url)
    # 보안 설정을 무시하고 직접 연결합니다
    if not security:
        # 보안 설정을 명시적으로 호출하지 않고 기본값 사용
        pass
    await client.connect()
    return client


async def activate_session(client: Client) -> bool:
    """
    Activate an existing session.
    
    Args:
        client: The client with an established connection
        
    Returns:
        True if session was activated successfully
    """
    try:
        # Session is automatically activated during connect()
        # This is just to check if it's active
        await client.get_namespace_array()
        return True
    except Exception as e:
        logger.error(f"Failed to activate session: {e}")
        return False


async def close_session(client: Client) -> None:
    """
    Close an existing session.
    
    Args:
        client: The client with an established connection
    """
    await client.disconnect()


class MultiSessionManager:
    """
    Manager for handling multiple OPC UA sessions.
    """
    
    def __init__(self):
        self.sessions: Dict[str, Client] = {}
        
    async def create_session(self, session_id: str, server_url: str) -> Client:
        """
        Create a new session with a unique identifier.
        
        Args:
            session_id: Unique identifier for the session
            server_url: The URL of the OPC UA server
            
        Returns:
            Client instance
        """
        if session_id in self.sessions:
            raise ValueError(f"Session with ID '{session_id}' already exists")
            
        client = await create_session(server_url)
        self.sessions[session_id] = client
        return client
        
    def get_session(self, session_id: str) -> Optional[Client]:
        """
        Get an existing session by ID.
        
        Args:
            session_id: The ID of the session to retrieve
            
        Returns:
            Client instance or None if not found
        """
        return self.sessions.get(session_id)
        
    async def close_session(self, session_id: str) -> None:
        """
        Close and remove a session by ID.
        
        Args:
            session_id: The ID of the session to close
        """
        if session_id in self.sessions:
            await self.sessions[session_id].disconnect()
            del self.sessions[session_id]
            
    async def close_all_sessions(self) -> None:
        """
        Close all active sessions.
        """
        for session_id in list(self.sessions.keys()):
            await self.close_session(session_id) 