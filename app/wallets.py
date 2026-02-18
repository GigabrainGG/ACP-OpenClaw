import json
import os

from .config import cfg


def load_wallets():
    if not os.path.exists(cfg.wallets_file):
        return []
    with open(cfg.wallets_file) as f:
        return json.load(f)


def save_wallets(wallets):
    with open(cfg.wallets_file, "w") as f:
        json.dump(wallets, f, indent=2)


def get_agents_with_keys():
    return [w for w in load_wallets() if w.get("acp_api_key")]
