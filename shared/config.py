"""Environment-driven settings for Credit App+ (Pydantic Settings v2)."""
from __future__ import annotations

import os
from decimal import Decimal
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # Coinbase Developer Platform credentials
    cdp_api_key_name: str = ""
    cdp_api_key_private_key: str = ""
    cdp_api_key_id: str = ""
    cdp_api_key_secret: str = ""
    cdp_project_id: str = ""
    cdp_wallet_secret: str = ""

    # vLLM inference endpoint (OpenAI-compatible). Default base model is
    # Qwen2.5-72B-Instruct (BF16); MI300X-class hardware is required to serve
    # it alongside the 5 per-lender LoRA adapters. Override to the 7B for
    # cheap local iteration without LoRA.
    vllm_url: str = "http://localhost:8000/v1"
    vllm_model: str = "Qwen/Qwen2.5-72B-Instruct"

    # LoRA serving mode. "multi" uses vLLM multi-LoRA serving (one adapter per
    # lender, routed by lora_alias) — the rate sheet is in the LoRA weights.
    # "prompt" disables LoRA and inlines each lender's rate_sheet_text as the
    # system prompt against the base model.
    lora_mode: str = "multi"

    # Network
    base_sepolia_rpc: str = "https://sepolia.base.org"

    # Wallet IDs (populated by scripts/setup_wallets.py)
    marketplace_wallet_id: str = ""
    reserve_wallet_id: str = ""

    # Marketplace economics
    insertion_fee_usdc: Decimal = Decimal("0.10")
    win_premium_rate: Decimal = Decimal("0.015")
    settlement_mode: str = "live"
    payment_mode: str = "live"

    # X402 facilitator mode:
    #   local  - deterministic in-process facilitator (default, dev/test)
    #   remote - HTTP facilitator client at x402_facilitator_url
    x402_facilitator_mode: str = "local"
    x402_facilitator_url: str = "https://x402.org/facilitator"

    # Marketplace HTTP server
    marketplace_host: str = "127.0.0.1"
    marketplace_port: int = 8001

    # Database
    database_url: str = "sqlite+aiosqlite:///./appbid.db"

    # Logging
    log_level: str = "INFO"

    @property
    def marketplace_url(self) -> str:
        return f"http://{self.marketplace_host}:{self.marketplace_port}"

    @property
    def cdp_effective_key_name(self) -> str:
        # Newer CDP portals label this as API key ID.
        return self.cdp_api_key_name or self.cdp_api_key_id

    @property
    def cdp_effective_key_secret(self) -> str:
        # Legacy env used "private key"; newer env uses API key secret.
        return self.cdp_api_key_private_key or self.cdp_api_key_secret

    @property
    def cdp_effective_wallet_secret(self) -> str:
        # SDK also supports reading this from process env.
        return self.cdp_wallet_secret or os.getenv("CDP_WALLET_SECRET", "")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
