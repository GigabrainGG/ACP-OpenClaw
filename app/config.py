import os
from dataclasses import dataclass, field

from dotenv import load_dotenv

load_dotenv()


@dataclass
class Config:
    wallets_file: str = "wallets.json"
    api_base_url: str = "https://claw-api.virtuals.io"
    provider_wallet: str = "0xa51AC6fE439ba7c29AD978a92Ef29BBeF2c313dd"
    job_offering: str = "ask_gigabrain"
    min_sleep: int = 30
    max_sleep: int = 120
    poll_interval: int = 5
    job_timeout_sec: int = 300
    num_agents: int = 10
    amount_usdc: float = 1.0
    acp_cli_path: str = field(default_factory=lambda: os.getenv("ACP_CLI_PATH", "./openclaw-acp"))

    @property
    def acp_cmd(self):
        return ["npx", "tsx", os.path.join(self.acp_cli_path, "bin", "acp.ts")]


cfg = Config()
