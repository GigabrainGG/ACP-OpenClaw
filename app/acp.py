import json
import subprocess

import requests

from .config import cfg


def create_job(agent, question):
    url = f"{cfg.api_base_url}/acp/jobs"
    headers = {"x-api-key": agent["acp_api_key"], "Content-Type": "application/json"}
    payload = {
        "providerWalletAddress": cfg.provider_wallet,
        "jobOfferingName": cfg.job_offering,
        "serviceRequirements": {"question": question},
    }
    try:
        r = requests.post(url, json=payload, headers=headers, timeout=30)
        if r.status_code not in (200, 201):
            return None, f"HTTP {r.status_code}: {r.text}"
        return r.json().get("data", {}).get("jobId"), None
    except Exception as e:
        return None, str(e)


def job_status(agent, job_id):
    url = f"{cfg.api_base_url}/acp/jobs/{job_id}"
    headers = {"x-api-key": agent["acp_api_key"]}
    try:
        r = requests.get(url, headers=headers, timeout=30)
        if r.status_code != 200:
            return None, f"HTTP {r.status_code}"
        return r.json(), None
    except Exception as e:
        return None, str(e)


def run_cli(*args):
    cmd = cfg.acp_cmd + list(args) + ["--json"]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60, cwd=cfg.acp_cli_path)
        if result.returncode != 0:
            return None, (result.stderr or result.stdout or "").strip()
        return json.loads(result.stdout.strip()), None
    except json.JSONDecodeError:
        return None, f"Invalid JSON: {(result.stdout[:200] if result.stdout else '')}"
    except Exception as e:
        return None, str(e)
