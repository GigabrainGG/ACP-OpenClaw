import random
import threading
import time

from .acp import create_job, job_status
from .config import cfg
from .privy import get_usdc_balance
from .questions import get_random_question
from .wallets import get_agents_with_keys

_stop_event = threading.Event()
_threads = []
_lock = threading.Lock()

_stats = {"completed": 0, "failed": 0, "timeout": 0, "errors": 0}


def _log(msg):
    print(msg, flush=True)


def _run_single_job(agent):
    name = agent["name"]
    question = get_random_question()
    _log(f"[{name}] Creating job: {question[:60]}...")

    job_id, err = create_job(agent, question)
    if err:
        _log(f"[{name}] Job creation failed: {err}")
        with _lock:
            _stats["errors"] += 1
        return

    _log(f"[{name}] Job {job_id} created, polling...")
    deadline = time.time() + cfg.job_timeout_sec
    last_phase = None
    poll_errors = 0

    while not _stop_event.is_set() and time.time() < deadline:
        data, err = job_status(agent, job_id)

        if err:
            poll_errors += 1
            _log(f"[{name}] Job {job_id} poll error ({poll_errors}): {err}")
            if poll_errors >= 5:
                _log(f"[{name}] Job {job_id} too many poll errors, giving up")
                with _lock:
                    _stats["errors"] += 1
                return
            time.sleep(cfg.poll_interval)
            continue

        poll_errors = 0

        # Check for hard errors (e.g. insufficient balance)
        job_errors = data.get("errors") or []
        if job_errors:
            _log(f"[{name}] Job {job_id} error: {job_errors[0]}")
            with _lock:
                _stats["failed"] += 1
            return

        job_data = data.get("data", {})
        phase = job_data.get("phase")

        if phase and phase != last_phase:
            _log(f"[{name}] Job {job_id} phase: {phase}")
            last_phase = phase

        if phase == "COMPLETED":
            deliverable = job_data.get("deliverable") or {}
            response = deliverable.get("value", "no response")
            _log(f"[{name}] Job {job_id} COMPLETED")
            _log(f"[{name}] BRAIN RESPONSE:\n{'-'*60}\n{response}\n{'-'*60}\n")
            with _lock:
                _stats["completed"] += 1
            return

        if phase in ("REJECTED", "CANCELLED", "EXPIRED"):
            _log(f"[{name}] Job {job_id} FAILED: {phase}")
            with _lock:
                _stats["failed"] += 1
            return

        time.sleep(cfg.poll_interval)

    _log(f"[{name}] Job {job_id} TIMEOUT (last phase: {last_phase})")
    with _lock:
        _stats["timeout"] += 1


def _ensure_funded(agent):
    """Returns True if agent has enough balance to run a job, False otherwise."""
    from .fund import do_fund
    name = agent["name"]
    acp_wallet = agent.get("acp_wallet")
    if not acp_wallet:
        return False
    balance = get_usdc_balance(acp_wallet)
    if balance >= 0.5:
        return True
    _log(f"[{name}] Low balance ({balance:.4f} USDC), triggering refund...")
    result = do_fund()
    if result.get("error"):
        _log(f"[{name}] Refund failed: {result['error']} — waiting for master wallet top-up")
        return False
    master_bal = result.get("master_balance_before", 0)
    funded = result.get("successful", 0)
    _log(f"[{name}] Refund: {funded} agents funded (master had {master_bal:.4f} USDC)")
    # Re-check balance after refund
    balance = get_usdc_balance(acp_wallet)
    if balance < 0.5:
        _log(f"[{name}] Still insufficient after refund ({balance:.4f} USDC) — skipping job")
        return False
    return True


def _agent_loop(agent):
    name = agent["name"]
    _log(f"[{name}] Agent thread started")
    while not _stop_event.is_set():
        if _ensure_funded(agent):
            _run_single_job(agent)
        else:
            _log(f"[{name}] No funds, sleeping 60s before retry...")
            for _ in range(60):
                if _stop_event.is_set():
                    break
                time.sleep(1)
            continue
        sleep_sec = random.randint(cfg.min_sleep, cfg.max_sleep)
        for _ in range(sleep_sec):
            if _stop_event.is_set():
                break
            time.sleep(1)
    _log(f"[{name}] Agent thread stopped")


def start():
    global _threads
    if _threads and any(t.is_alive() for t in _threads):
        return True, "already running"
    agents = get_agents_with_keys()[:cfg.num_agents]
    if not agents:
        return False, "no agents with API keys; run POST /setup first"
    _stop_event.clear()
    with _lock:
        _stats.update({"completed": 0, "failed": 0, "timeout": 0, "errors": 0})
    _threads = []
    for agent in agents:
        t = threading.Thread(target=_agent_loop, args=(agent,), daemon=True)
        t.start()
        _threads.append(t)
    return True, f"started {len(_threads)} agent threads"


def stop():
    _stop_event.set()
    return True, "stop requested"


def running():
    return bool(_threads) and any(t.is_alive() for t in _threads)


def stats():
    with _lock:
        return dict(_stats)
