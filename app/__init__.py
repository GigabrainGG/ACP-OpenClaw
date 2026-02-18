import os
import threading
import time

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from . import volume
from .acp import run_cli
from .config import cfg
from .fund import do_fund
from .privy import get_client, get_usdc_balance
from .wallets import get_agents_with_keys, load_wallets, save_wallets


def _do_setup():
    try:
        privy = get_client()
    except ValueError as e:
        return {"ok": False, "error": str(e)}

    wallets = load_wallets()
    remaining = cfg.num_agents - len(wallets)
    if remaining <= 0:
        return {"ok": True, "message": f"Already have {len(wallets)} wallets.", "wallets": len(wallets)}

    created = 0
    for _ in range(remaining):
        name = f"acp-client-{len(wallets) + 1:02d}"
        try:
            wallet = privy.create_wallet()
        except Exception as e:
            return {"ok": False, "error": f"Privy wallet: {e}"}

        acp_data, err = run_cli("agent", "create", name)
        acp_wallet = acp_data.get("walletAddress") if isinstance(acp_data, dict) else None
        api_key = acp_data.get("apiKey") if isinstance(acp_data, dict) else None

        wallets.append({
            "name": name,
            "privy_wallet_id": wallet["id"],
            "privy_address": wallet["address"],
            "acp_wallet": acp_wallet,
            "acp_api_key": api_key,
        })
        save_wallets(wallets)
        created += 1
        time.sleep(1)

    return {"ok": True, "message": f"Created {created} agents.", "wallets": len(wallets)}


def _log(msg):
    print(msg, flush=True)


def _auto_start():
    try:
        _log("[auto] Running setup...")
        result = _do_setup()
        _log(f"[auto] Setup: {result.get('message', result.get('error', 'unknown'))}")

        if not get_agents_with_keys():
            _log("[auto] No agents with keys, skipping fund and volume start.")
            return

        _log("[auto] Funding wallets...")
        result = do_fund()
        _log(f"[auto] Fund: {result.get('successful', 0)}/{result.get('total', 0)} succeeded, {result.get('skipped', 0)} skipped")
        if result.get("errors"):
            for e in result["errors"]:
                _log(f"[auto]   {e['name']}: {e['error']}")

        _log("[auto] Starting volume bot...")
        ok, msg = volume.start()
        _log(f"[auto] Volume: {msg}")
    except Exception as e:
        _log(f"[auto] FATAL: {e}")


def create_app():
    app = FastAPI()

    @app.on_event("startup")
    def on_startup():
        threading.Thread(target=_auto_start, daemon=True).start()

    @app.get("/health")
    def health():
        return {
            "status": "ok",
            "volume_running": volume.running(),
            "agents": len(get_agents_with_keys()),
        }

    @app.post("/volume/start")
    def volume_start():
        ok, msg = volume.start()
        if not ok:
            return JSONResponse({"ok": ok, "message": msg}, status_code=400)
        return {"ok": ok, "message": msg}

    @app.post("/volume/stop")
    def volume_stop():
        volume.stop()
        return {"ok": True, "message": "Volume bot stop requested."}

    @app.get("/volume/status")
    def volume_status():
        return {"running": volume.running(), "stats": volume.stats()}

    return app
