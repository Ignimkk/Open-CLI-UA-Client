"""
Connection module for OPC UA client.

This module provides functions to manage connections to OPC UA servers.
"""

import asyncio
import logging
import traceback
from typing import Dict, List, Optional, Tuple
import time

from asyncua import Client, ua
from asyncua.common.node import Node
from asyncua.crypto.security_policies import SecurityPolicyBasic256Sha256
from asyncua.ua import EndpointDescription, MessageSecurityMode

logger = logging.getLogger(__name__)

# 글로벌 변수로 keep-alive 태스크 관리
_keep_alive_tasks = {}

async def _keep_alive_worker(client: Client, interval: float = 3.0):
    """
    클라이언트 연결을 유지하기 위한 백그라운드 작업입니다.
    주기적으로 서버에 요청을 보내 연결이 유지되도록 합니다.
    
    Args:
        client: OPC UA 클라이언트 인스턴스
        interval: 연결 유지 요청 간격(초)
    """
    reconnect_attempts = 0
    max_reconnect_attempts = 5
    last_success_time = time.time()
    
    try:
        logger.info(f"연결 유지(keep-alive) 태스크 시작, 간격: {interval}초")
        while True:
            current_time = time.time()
            try:
                # 서버 시간 노드 ID (모든 OPC UA 서버에서 지원)
                time_node = client.get_node("ns=0;i=2258")
                # 노드 값을 읽어 연결 유지
                await time_node.read_value()
                logger.debug("Keep-alive 요청 성공")
                
                # 성공한 경우 재시도 카운터 초기화
                reconnect_attempts = 0
                last_success_time = current_time
                
            except Exception as e:
                # 마지막 성공으로부터 경과한 시간 확인
                elapsed = current_time - last_success_time
                logger.warning(f"Keep-alive 요청 실패 (마지막 성공으로부터 {elapsed:.1f}초): {e}")
                
                # 연결이 끊어졌을 때 재연결 시도
                reconnect_attempts += 1
                
                if reconnect_attempts <= max_reconnect_attempts:
                    try:
                        logger.info(f"연결 재시도 {reconnect_attempts}/{max_reconnect_attempts}...")
                        
                        # 기존 연결 닫기 시도
                        try:
                            await client.disconnect()
                        except Exception as disc_err:
                            logger.debug(f"연결 닫기 중 오류 (무시됨): {disc_err}")
                        
                        # 새로 연결 시도
                        await asyncio.sleep(0.5)  # 잠시 대기 후 재연결
                        await client.connect()
                        
                        # 연결 확인
                        await client.get_namespace_array()
                        logger.info("재연결 성공")
                        
                        # 재연결 성공 시 카운터 및 타임스탬프 초기화
                        reconnect_attempts = 0
                        last_success_time = time.time()
                        
                    except Exception as reconnect_error:
                        logger.error(f"재연결 시도 {reconnect_attempts} 실패: {reconnect_error}")
                else:
                    logger.error(f"최대 재연결 시도 횟수({max_reconnect_attempts})에 도달. 일시적으로 중단합니다.")
                    # 일정 시간 대기 후 재시도 카운터 초기화
                    await asyncio.sleep(10)
                    reconnect_attempts = 0
                    
            # 다음 keep-alive 주기까지 대기
            await asyncio.sleep(interval)
    except asyncio.CancelledError:
        logger.info("연결 유지(keep-alive) 태스크가 취소되었습니다.")
    except Exception as e:
        logger.error(f"연결 유지(keep-alive) 태스크 오류: {e}")
        # 예외 전파하지 않고 로깅만 수행


class Connection:
    """
    Connection class for OPC UA client.
    """
    
    def __init__(self, server_url: str):
        """
        Initialize the OPC UA connection.
        
        Args:
            server_url: The URL of the OPC UA server
        """
        self.server_url = server_url
        self.client = None
        self.is_connected = False
        
    async def connect(self, security: bool = False) -> None:
        """
        Connect to the OPC UA server.
        
        Args:
            security: Whether to use security (default: False)
        """
        try:
            logger.info(f"Connecting to {self.server_url}...")
            self.client = Client(self.server_url)
            await self.client.connect()
            self.is_connected = True
            logger.info(f"Successfully connected to {self.server_url}")
            
            # 연결 성공 확인을 위해 namespace 배열 가져오기
            namespaces = await self.client.get_namespace_array()
            logger.info(f"Connection verified. Server has {len(namespaces)} namespaces")
            
        except Exception as e:
            self.is_connected = False
            logger.error(f"Failed to connect: {str(e)[:200]}")
            logger.error(f"Exception type: {type(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            raise
            
    async def disconnect(self) -> None:
        """
        Disconnect from the OPC UA server.
        """
        if self.client and self.is_connected:
            try:
                await self.client.disconnect()
                logger.info(f"Disconnected from {self.server_url}")
            except Exception as e:
                logger.error(f"Error during disconnect: {e}")
            finally:
                self.is_connected = False
                self.client = None
                
    async def get_endpoints(self) -> List[EndpointDescription]:
        """
        Get available endpoints from the server.
        
        Returns:
            List of endpoint descriptions
        """
        temp_client = Client(self.server_url)
        try:
            endpoints = await temp_client.connect_and_get_server_endpoints()
            return endpoints
        finally:
            await temp_client.disconnect()
                
    def get_client(self) -> Optional[Client]:
        """
        Get the underlying asyncua Client instance.
        
        Returns:
            Client instance or None if not connected
        """
        return self.client if self.is_connected else None


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


async def create_session(server_url: str, security: bool = False, keep_alive: bool = True, keep_alive_interval: float = 3.0) -> Client:
    """
    Create a session without security.
    
    Args:
        server_url: The URL of the OPC UA server
        security: Whether to use security (default: False)
        keep_alive: Whether to enable keep-alive mechanism (default: True)
        keep_alive_interval: Interval for keep-alive requests in seconds (default: 3.0)
        
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
        
        # 세션 타임아웃 설정을 늘림 (기본값보다 길게)
        client.session_timeout = 3600000  # 1시간 (밀리초 단위)
        
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
        
        # Keep-alive 메커니즘 활성화
        if keep_alive:
            global _keep_alive_tasks
            # 이전 태스크가 있다면 취소
            if server_url in _keep_alive_tasks and not _keep_alive_tasks[server_url].done():
                _keep_alive_tasks[server_url].cancel()
                
            # 새로운 keep-alive 태스크 생성
            _keep_alive_tasks[server_url] = asyncio.create_task(
                _keep_alive_worker(client, keep_alive_interval)
            )
            logger.info(f"Keep-alive mechanism activated for {server_url}")
        
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
    # Keep-alive 태스크 찾기 및 취소
    global _keep_alive_tasks
    for url, task in list(_keep_alive_tasks.items()):
        if not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            del _keep_alive_tasks[url]
            logger.info(f"Keep-alive task for {url} cancelled")
            
    # 연결 종료
    await client.disconnect()
    logger.info("Session closed and keep-alive tasks cancelled")


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