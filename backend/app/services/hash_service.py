from web3 import Web3
class HashService:
    @staticmethod
    def hash_bytes(data: bytes) -> str:
        return Web3.to_hex(Web3.keccak(data))
    @staticmethod
    def hash_text(text: str) -> str:
        return Web3.to_hex(Web3.keccak(text=text))
    @staticmethod
    def combine_manifest(file_hashes: list[str]) -> str:
        sorted_hashes = "".join(sorted(file_hashes))
        return Web3.to_hex(Web3.keccak(text=sorted_hashes))
