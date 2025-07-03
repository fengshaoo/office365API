from dataclasses import dataclass
from typing import Optional

@dataclass
class AccountContext:
    account_key: str
    refresh_token: str
    account_token: Optional[str] = None
    proxy: Optional[str] = None
    user_agent: Optional[str] = None
