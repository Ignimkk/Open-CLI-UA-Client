"""
Utility module for OPC UA client.

This module provides utility functions for the OPC UA client.
"""

import logging
from typing import Any, Dict, List, Optional, Union

from asyncua import Client, ua

logger = logging.getLogger(__name__)


def variant_to_python(variant: ua.Variant) -> Any:
    """
    Convert an OPC UA Variant to a Python type.
    
    Args:
        variant: The OPC UA Variant to convert
        
    Returns:
        Python representation of the variant
    """
    if variant.is_array:
        return [variant_to_python(ua.Variant(v)) for v in variant.Value]
    
    # Handle scalar types
    value = variant.Value
    
    # Convert OPC UA specific types to Python types
    if isinstance(value, ua.DateTime):
        return value.to_datetime()
    if isinstance(value, ua.LocalizedText):
        return value.Text
    if isinstance(value, ua.QualifiedName):
        return value.Name
    if isinstance(value, ua.NodeId):
        return str(value)
    if isinstance(value, ua.ExtensionObject):
        return "ExtensionObject"
    
    return value


def python_to_variant(value: Any) -> ua.Variant:
    """
    Convert a Python value to an OPC UA Variant.
    
    Args:
        value: The Python value to convert
        
    Returns:
        OPC UA Variant
    """
    # Already a variant
    if isinstance(value, ua.Variant):
        return value
    
    # Handle lists/arrays
    if isinstance(value, (list, tuple)):
        return ua.Variant(value, ua.VariantType.Null)
    
    # Scalars
    return ua.Variant(value)


def setup_logging(level: int = logging.INFO) -> None:
    """
    Set up basic logging configuration.
    
    Args:
        level: The logging level to use
    """
    # 바이너리 데이터 필터 추가 로그 포맷터
    class BinaryFilter(logging.Filter):
        def filter(self, record):
            if hasattr(record, 'msg') and record.msg is not None:
                # 문자열로 변환
                if not isinstance(record.msg, str):
                    try:
                        msg_str = str(record.msg)
                    except Exception:
                        msg_str = "[변환 불가능한 메시지]"
                else:
                    msg_str = record.msg
                
                # 바이너리 데이터나 너무 긴 메시지 필터링
                if is_binary_data(msg_str) or len(msg_str) > 500:
                    # 메시지 시작 부분만 유지
                    record.msg = f"{msg_str[:50]}... [이진 데이터 필터링됨]"
                # 인증서 데이터 필터링
                elif 'certificate' in msg_str.lower() or 'ServerCertificate=' in msg_str:
                    if 'ServerCertificate=' in msg_str:
                        parts = msg_str.split('ServerCertificate=')
                        record.msg = parts[0] + 'ServerCertificate=[인증서 데이터 필터링됨]'
                    elif len(msg_str) > 200:
                        record.msg = f"{msg_str[:100]}... [인증서 데이터 필터링됨]"
                # NodeId 형식 필터링 - 너무 복잡한 NodeId 요약
                elif 'NodeId(' in msg_str and len(msg_str) > 300:
                    record.msg = f"{msg_str[:100]}... [NodeId 데이터 요약됨]"
                
                # 예외 메시지 필터링
                if hasattr(record, 'exc_info') and record.exc_info:
                    exception_text = logging.Formatter().formatException(record.exc_info)
                    if len(exception_text) > 500 or is_binary_data(exception_text):
                        # 예외 메시지 시작 부분만 유지
                        record.exc_text = f"{exception_text[:200]}... [상세 예외 정보 필터링됨]"
                        record.exc_info = None  # 원본 예외 정보 제거
            return True

    # 로그 핸들러 설정
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    
    # 기존 핸들러 모두 제거
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # 콘솔 핸들러
    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    console_handler.setFormatter(formatter)
    console_handler.addFilter(BinaryFilter())
    root_logger.addHandler(console_handler)
    
    # 파일 핸들러
    try:
        file_handler = logging.FileHandler("opcua_client.log")
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        file_handler.addFilter(BinaryFilter())
        root_logger.addHandler(file_handler)
    except (IOError, PermissionError):
        # 파일을 열 수 없는 경우 경고만 출력
        logging.warning("로그 파일을 생성할 수 없습니다. 콘솔 로깅만 활성화됩니다.")
    
    # asyncua 라이브러리의 로그 레벨 조정
    logging.getLogger('asyncua.client.ua_client').setLevel(logging.WARNING)
    logging.getLogger('asyncua.client.client').setLevel(logging.WARNING)
    logging.getLogger('asyncua.common.xmlimporter').setLevel(logging.WARNING)
    logging.getLogger('asyncua.common.xmlparser').setLevel(logging.WARNING)
    logging.getLogger('asyncua.common.ua_utils').setLevel(logging.WARNING)
    logging.getLogger('asyncua.common.connection').setLevel(logging.WARNING)
    
    # OPC UA 보안 관련 로거는 더 높은 레벨로 설정
    logging.getLogger('asyncua.crypto').setLevel(logging.ERROR)
    
    logger.info("로깅 시스템이 초기화되었습니다. 바이너리 데이터 필터링이 활성화되었습니다.")


def is_binary_data(data: Any) -> bool:
    """
    Check if the data is likely binary data.
    
    Args:
        data: Data to check
        
    Returns:
        True if the data is likely binary
    """
    if data is None:
        return False
        
    if isinstance(data, bytes):
        return True
    
    if isinstance(data, str):
        # 문자열이 이진 데이터를 포함하는지 확인
        binary_chars = ['\x00', '\x01', '\x02', '\x03', '\x04', '\x05', '\x06', '\x07',
                       '\x08', '\x0b', '\x0c', '\x0e', '\x0f', '\x10', '\x11', '\x12',
                       '\x13', '\x14', '\x15', '\x16', '\x17', '\x18', '\x19', '\x1a',
                       '\x1b', '\x1c', '\x1d', '\x1e', '\x1f', '\x7f', '\x80', '\x81',
                       '\x82', '\x83', '\x84', '\x85', '\x86', '\x87']
        
        # 이진 문자 포함 여부 확인
        has_binary = any(c in data for c in binary_chars)
        
        # 인증서 데이터 패턴 확인
        has_cert_pattern = 'certificate' in data.lower() or 'private key' in data.lower()
        
        # XML 또는 바이너리 데이터로 보이는 긴 문자열
        is_long_complex = len(data) > 500 and ('<' in data and '>' in data and len(data.split('<')) > 10)
        
        return has_binary or has_cert_pattern or is_long_complex
    
    return False


def safe_repr(obj: Any) -> str:
    """
    Create a safe string representation of an object, filtering binary data.
    
    Args:
        obj: The object to represent
        
    Returns:
        Safe string representation
    """
    if obj is None:
        return "None"
    
    if isinstance(obj, (int, float, bool)):
        return str(obj)
    
    if isinstance(obj, (list, tuple)):
        return f"[{type(obj).__name__} with {len(obj)} items]"
    
    if isinstance(obj, dict):
        return f"[Dictionary with {len(obj)} items]"
    
    try:
        s = str(obj)
        if is_binary_data(s) or len(s) > 100:
            return f"[{type(obj).__name__} object]"
        return s
    except:
        return f"[{type(obj).__name__} object]"


def format_node_id(namespace: int, identifier: Union[int, str]) -> str:
    """
    Format a node ID string from namespace and identifier.
    
    Args:
        namespace: The namespace index
        identifier: The identifier
        
    Returns:
        Formatted node ID string
    """
    if isinstance(identifier, int):
        return f"ns={namespace};i={identifier}"
    else:
        return f"ns={namespace};s={identifier}"


def parse_node_id(node_id_str: str) -> Dict[str, Union[int, str]]:
    """
    Parse a node ID string into its components.
    
    Args:
        node_id_str: The node ID string to parse
        
    Returns:
        Dictionary containing namespace and identifier
    """
    parts = node_id_str.split(';')
    result = {}
    
    for part in parts:
        if '=' in part:
            key, value = part.split('=', 1)
            if key == 'ns':
                result['namespace'] = int(value)
            elif key in ('i', 's', 'g', 'b'):
                result['identifier_type'] = key
                if key == 'i':
                    result['identifier'] = int(value)
                else:
                    result['identifier'] = value
    
    return result 


class DataChangeNotif:
    """
    데이터 변경 알림을 위한 클래스.
    """
    
    @staticmethod
    def handle_data_change(node, value, data):
        """
        데이터 변경 알림 핸들러.
        """
        try:
            node_name = str(node)
            if is_binary_data(value):
                value_str = "[이진 데이터 필터링됨]"
            elif isinstance(value, (list, tuple)) and len(value) > 10:
                value_str = f"[목록 데이터: {len(value)}개 항목]"
            else:
                value_str = safe_repr(value)
                
            logger.info(f"데이터 변경 감지: {node_name} = {value_str}")
            return value_str
        except Exception as e:
            logger.error(f"데이터 변경 처리 오류: {e}")
            return None 