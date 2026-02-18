import os

from .config import cfg
from .privy import get_client, get_usdc_balance
from .wallets import get_agents_with_keys

MAX_FUND_PER_WALLET = 5.0


def _log(msg):
    print(msg, flush=True)


def do_fund():
    master_id = os.getenv("PRIVY_MASTER_WALLET_ID")
    master_addr = os.getenv("PRIVY_MASTER_WALLET_ADDRESS")
    if not master_id:
        return {"ok": False, "error": "PRIVY_MASTER_WALLET_ID not set in .env"}
    if not master_addr:
        return {"ok": False, "error": "PRIVY_MASTER_WALLET_ADDRESS not set in .env"}

    try:
        privy = get_client()
    except ValueError as e:
        return {"ok": False, "error": str(e)}

    agents = get_agents_with_keys()[:cfg.num_agents]
    if not agents:
        return {"ok": False, "error": f"No agents in {cfg.wallets_file}"}

    master_balance = get_usdc_balance(master_addr)
    _log(f"[fund] Master balance: {master_balance:.4f} USDC for {len(agents)} agents")

    if master_balance < 0.01:
        return {"ok": False, "error": f"Master wallet has no USDC ({master_balance:.4f})"}

    amount_each = min(round(master_balance / len(agents), 6), MAX_FUND_PER_WALLET)
    _log(f"[fund] Distributing {amount_each:.4f} USDC per agent")

    successful = 0
    skipped = 0
    errors = []

    for w in agents:
        to = w.get("acp_wallet")
        if not to:
            continue
        balance = get_usdc_balance(to)
        if balance >= amount_each:
            _log(f"[fund] {w.get('name')} already has {balance:.4f} USDC, skipping")
            skipped += 1
            continue
        try:
            privy.transfer_usdc(from_wallet_id=master_id, to_address=to, amount_usdc=amount_each, sponsor=False)
            _log(f"[fund] {w.get('name')} funded {amount_each:.4f} USDC")
            successful += 1
        except Exception as e:
            errors.append({"name": w.get("name"), "error": str(e)})

    return {
        "ok": True,
        "successful": successful,
        "skipped": skipped,
        "failed": len(errors),
        "total": len(agents),
        "amount_per_wallet": amount_each,
        "master_balance_before": master_balance,
        "errors": errors[:10],
    }
