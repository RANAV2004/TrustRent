from app.services.storage.local_encrypted import LocalEncryptedStorageProvider
from app.services.storage.ipfs import IPFSStorageProvider
def test_local_encrypted_storage_roundtrip(tmp_path):
    storage = LocalEncryptedStorageProvider(storage_dir=str(tmp_path))
    data = b"CONFIDENTIAL_TENANCY_LEASE_AGREEMENT_2026"
    key = "lease_test_001"
    path, iv_hex = storage.store(key, data)
    assert path.endswith(".enc")
    assert len(iv_hex) == 24
    decrypted = storage.retrieve(path, iv_hex)
    assert decrypted == data
def test_ipfs_storage_simulation():
    ipfs = IPFSStorageProvider()
    data = b"MOVE_IN_PHOTO_EVIDENCE"
    cid, iv_hex = ipfs.store("photo_1", data)
    assert cid.startswith("Qm")
    assert len(iv_hex) == 24
