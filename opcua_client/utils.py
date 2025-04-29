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
            if hasattr(record, 'msg'):
                # 바이너리 데이터가 포함될 가능성이 있는 경우 필터링
                if isinstance(record.msg, bytes) or (isinstance(record.msg, str) and any(c in record.msg for c in ['\x00', '\x82', '\x01', '\x0f'])):
                    record.msg = "[이진 데이터 필터링됨]"
                    return True
                # 인증서 데이터가 포함된 경우 필터링
                elif isinstance(record.msg, str):
                    if 'certificate' in record.msg.lower() or 'security' in record.msg.lower():
                        if len(record.msg) > 200:  # 너무 긴 메시지는 이진 데이터일 가능성이 높음
                            record.msg = f"{record.msg[:100]} ... [이진 데이터 필터링됨]"
                    # ServerCertificate 문자열이 포함된 경우 필터링
                    elif 'ServerCertificate=' in record.msg:
                        parts = record.msg.split('ServerCertificate=')
                        if len(parts) > 1:
                            # ServerCertificate 값을 필터링
                            record.msg = parts[0] + 'ServerCertificate=[인증서 데이터 필터링됨]'
            return True

    # 로그 핸들러 설정
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    
    # 기존 핸들러 모두 제거
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # 새 핸들러 생성
    handler = logging.StreamHandler()
    handler.setLevel(level)
    handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    
    # 바이너리 필터 추가
    handler.addFilter(BinaryFilter())
    root_logger.addHandler(handler)
    
    # asyncua 라이브러리의 로그 레벨 조정
    # 민감한 데이터가 포함된 로거의 레벨을 높여 출력 차단
    logging.getLogger('asyncua.client.ua_client').setLevel(logging.WARNING)
    logging.getLogger('asyncua.client.client').setLevel(logging.WARNING)
    logging.getLogger('asyncua.common.xmlimporter').setLevel(logging.WARNING)
    logging.getLogger('asyncua.common.xmlparser').setLevel(logging.WARNING)
    
    # find_endpoint 메시지가 있는 로거는 필터 추가
    endpoint_logger = logging.getLogger('asyncua.client.client')
    endpoint_logger.addFilter(BinaryFilter())


def is_binary_data(data: Any) -> bool:
    """
    Check if the data is likely binary data.
    
    Args:
        data: Data to check
        
    Returns:
        True if the data is likely binary
    """
    if isinstance(data, bytes):
        return True
    
    if isinstance(data, str):
        # 문자열이 이진 데이터를 포함하는지 확인
        binary_chars = ['\x00', '\x01', '\x02', '\x03', '\x04', '\x05', '\x06', '\x07',
                       '\x08', '\x0b', '\x0c', '\x0e', '\x0f', '\x10', '\x11', '\x12',
                       '\x13', '\x14', '\x15', '\x16', '\x17', '\x18', '\x19', '\x1a',
                       '\x1b', '\x1c', '\x1d', '\x1e', '\x1f', '\x7f', '\x80', '\x81',
                       '\x82', '\x83', '\x84', '\x85', '\x86', '\x87']
        return any(c in data for c in binary_chars)
    
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