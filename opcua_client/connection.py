"""
Connection module for OPC UA client.

This module provides functions to manage connections to OPC UA servers.
"""

import asyncio
import logging
import traceback
from typing import Dict, List, Optional, Tuple

from asyncua import Client, ua
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
            # 속성이 있는지 확인한 후 접근 (인증서 데이터는 로깅하지 않음)
            security_mode = getattr(endpoint, 'SecurityMode', None) or getattr(endpoint, 'security_mode', 'Unknown')
            security_policy = getattr(endpoint, 'SecurityPolicyUri', None) or getattr(endpoint, 'security_policy_uri', 'Unknown')
            
            # 간결한 로깅 정보만 출력
            logger.info(f"Endpoint {i}: Mode={security_mode}, Policy={security_policy}")
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
    try:
        # 명시적으로 보안 정책 없는 엔드포인트 URL 사용
        if not security and not server_url.endswith("/"):
            # None 엔드포인트를 명시적으로 선택
            server_url = f"{server_url}"
            
        logger.info(f"Creating client for URL: {server_url}")
        client = Client(server_url)
        
        # 보안 설정을 건너뛰고 바로 연결 시도
        logger.info(f"Connecting to {server_url}...")
        await client.connect()
        logger.info(f"Successfully connected to {server_url}")
        
        # 연결 성공 확인을 위해 namespace 배열 가져오기
        namespaces = await client.get_namespace_array()
        # 네임스페이스 배열이 너무 길면 간결하게 표시
        if len(namespaces) > 5:
            ns_log = f"{len(namespaces)} namespaces: [{', '.join(str(ns)[:20] for ns in namespaces[:3])}...]"
        else:
            ns_log = f"{len(namespaces)} namespaces: {namespaces}"
        
        logger.info(f"Connection verified. Server has {ns_log}")
        
        return client
    except Exception as e:
        # 상세한 예외 정보 출력 (바이너리 데이터 필터링)
        logger.error(f"Failed to create session: {str(e)[:200]}")
        logger.error(f"Exception type: {type(e)}")
        # 트레이스백은 바이너리 데이터가 없으므로 그대로 출력
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise


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