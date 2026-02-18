import base64
import hashlib
import json
import os

import requests
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, utils

PRIVY_API_BASE = "https://api.privy.io/v1"
USDC_CONTRACT_BASE = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"
USDC_DECIMALS = 6
BASE_CAIP2 = "eip155:8453"
BASE_RPC = "https://mainnet.base.org"


def get_usdc_balance(address):
    selector = "70a08231"
    addr = address.lower().replace("0x", "").zfill(64)
    calldata = f"0x{selector}{addr}"
    body = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "eth_call",
        "params": [{"to": USDC_CONTRACT_BASE, "data": calldata}, "latest"],
    }
    try:
        resp = requests.post(BASE_RPC, json=body, timeout=10)
        raw = resp.json().get("result", "0x0")
        return int(raw, 16) / (10 ** USDC_DECIMALS)
    except Exception:
        return 0.0


class PrivyClient:
    def __init__(self):
        self.app_id = os.getenv("PRIVY_APP_ID")
        self.app_secret = os.getenv("PRIVY_APP_SECRET")
        if not self.app_id or not self.app_secret:
            raise ValueError("PRIVY_APP_ID and PRIVY_APP_SECRET must be set in .env")

        auth_key_path = os.getenv("PRIVY_AUTH_KEY_PATH")
        auth_key_raw = os.getenv("PRIVY_AUTH_KEY")

        self._auth_private_key = None

        if auth_key_path and os.path.exists(auth_key_path):
            with open(auth_key_path, "rb") as f:
                content = f.read()
                try:
                    self._auth_private_key = serialization.load_pem_private_key(content, password=None)
                except ValueError:
                    try:
                        if b"-----" not in content:
                            try:
                                der_data = base64.b64decode(content)
                                self._auth_private_key = serialization.load_der_private_key(der_data, password=None)
                            except Exception:
                                self._auth_private_key = serialization.load_der_private_key(content, password=None)
                    except Exception:
                        pass

        if not self._auth_private_key and auth_key_raw:
            key_data = auth_key_raw.replace("\\n", "\n")
            if "-----BEGIN" in key_data:
                self._auth_private_key = serialization.load_pem_private_key(key_data.encode(), password=None)
            else:
                try:
                    der_data = base64.b64decode(key_data)
                    self._auth_private_key = serialization.load_der_private_key(der_data, password=None)
                except Exception:
                    pem = f"-----BEGIN EC PRIVATE KEY-----\n{key_data}\n-----END EC PRIVATE KEY-----"
                    self._auth_private_key = serialization.load_pem_private_key(pem.encode(), password=None)

        if not self._auth_private_key:
            raise ValueError("Could not load authorization key. Set PRIVY_AUTH_KEY or PRIVY_AUTH_KEY_PATH in .env")

    def _basic_auth(self):
        creds = base64.b64encode(f"{self.app_id}:{self.app_secret}".encode()).decode()
        return f"Basic {creds}"

    def _base_headers(self):
        return {
            "Authorization": self._basic_auth(),
            "privy-app-id": self.app_id,
            "Content-Type": "application/json",
        }

    def _sign_authorization(self, body_bytes):
        if not self._auth_private_key:
            raise ValueError("Authorization key not configured. Set PRIVY_AUTH_KEY_PATH or PRIVY_AUTH_KEY in .env")
        digest = hashlib.sha256(body_bytes).digest()
        signature = self._auth_private_key.sign(
            digest,
            ec.ECDSA(utils.Prehashed(hashes.SHA256())),
        )
        return base64.b64encode(signature).decode()

    def _signed_headers(self, body_dict):
        headers = self._base_headers()
        body_bytes = json.dumps(body_dict).encode()
        headers["privy-authorization-signature"] = self._sign_authorization(body_bytes)
        return headers

    def create_wallet(self):
        body = {"chain_type": "ethereum"}
        headers = self._base_headers()
        resp = requests.post(f"{PRIVY_API_BASE}/wallets", json=body, headers=headers)
        if resp.status_code not in (200, 201):
            raise Exception(f"Create wallet failed: {resp.status_code} {resp.text}")
        data = resp.json()
        return {
            "id": data["id"],
            "address": data["address"],
            "chain_type": data.get("chain_type", "ethereum"),
        }

    def get_wallet(self, wallet_id):
        headers = self._base_headers()
        resp = requests.get(f"{PRIVY_API_BASE}/wallets/{wallet_id}", headers=headers)
        if resp.status_code != 200:
            raise Exception(f"Get wallet failed: {resp.status_code} {resp.text}")
        return resp.json()

    def send_transaction(self, wallet_id, to, data_hex, value="0x0", sponsor=True):
        body = {
            "method": "eth_sendTransaction",
            "caip2": BASE_CAIP2,
            "params": {
                "transaction": {
                    "to": to,
                    "data": data_hex,
                    "value": value,
                },
            },
        }
        if sponsor:
            body["sponsor"] = True
        headers = self._signed_headers(body)
        resp = requests.post(f"{PRIVY_API_BASE}/wallets/{wallet_id}/rpc", json=body, headers=headers)
        if resp.status_code not in (200, 201):
            raise Exception(f"Send transaction failed: {resp.status_code} {resp.text}")
        result = resp.json()
        return {
            "hash": result.get("data", {}).get("hash"),
            "transaction_id": result.get("data", {}).get("transaction_id"),
            "caip2": result.get("data", {}).get("caip2"),
        }

    def encode_usdc_transfer(self, to_address, amount_usdc):
        selector = "a9059cbb"
        addr = to_address.lower().replace("0x", "").zfill(64)
        raw_amount = int(amount_usdc * (10 ** USDC_DECIMALS))
        amount_hex = hex(raw_amount)[2:].zfill(64)
        return f"0x{selector}{addr}{amount_hex}"

    def transfer_usdc(self, from_wallet_id, to_address, amount_usdc, sponsor=True):
        calldata = self.encode_usdc_transfer(to_address, amount_usdc)
        return self.send_transaction(
            wallet_id=from_wallet_id,
            to=USDC_CONTRACT_BASE,
            data_hex=calldata,
            sponsor=sponsor,
        )


_client = None


def get_client():
    global _client
    if _client is None:
        _client = PrivyClient()
    return _client
