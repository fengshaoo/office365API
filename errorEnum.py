from enum import Enum
from dataclasses import dataclass

@dataclass
class ErrorInfo:
    code: int
    message: str

class ErrorCode(Enum):
    INVALID_TOKEN = ErrorInfo(1001, 'Access token is invalid or expired')
    UNAUTHORIZED = ErrorInfo(1002, 'Unauthorized access')
    USER_NOT_FOUND = ErrorInfo(1003, 'User does not exist')
    INTERNAL_ERROR = ErrorInfo(1004, 'Internal server error')