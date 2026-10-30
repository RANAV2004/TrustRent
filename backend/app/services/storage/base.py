from abc import ABC, abstractmethod
from typing import Tuple
class StorageProvider(ABC):
    @abstractmethod
    def store(self, key: str, data: bytes) -> Tuple[str, str]:
        pass
    @abstractmethod
    def retrieve(self, storage_reference: str, iv_hex: str) -> bytes:
        pass
