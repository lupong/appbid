"""Async wrappers around the Coinbase CDP SDK for Base Sepolia USDC.

The cdp-sdk Python API is synchronous; we offload calls onto a thread pool
with asyncio.to_thread so we never block the event loop. If the installed
SDK version differs from what's expected here, adjust the imports and the
method calls inside _sync closures — the public async signatures should
remain stable.
"""
from __future__ import annotations

import asyncio
from decimal import Decimal
from typing import Any
from uuid import uuid4

from shared.config import get_settings
from shared.logging import get_logger

logger = get_logger("appbid.wallets")

_NETWORK_ID = "base-sepolia"
_USDC = "usdc"
_configured = False
_cdp_mode: str | None = None
_cdp_client: Any | None = None


def _usdc_to_atomic(amount: Decimal) -> int:
    return int((amount * Decimal(10**6)).quantize(Decimal("1")))


def _resolve_maybe_async(value: Any) -> Any:
    """Run coroutine results to completion for SDK methods that became async."""
    if asyncio.iscoroutine(value):
        return asyncio.run(value)
    return value


async def _resolve_maybe_async_await(value: Any) -> Any:
    """Await coroutine results for async CDP SDK calls."""
    if asyncio.iscoroutine(value):
        return await value
    return value


def _import_cdp() -> tuple[str, Any, Any]:
    """Return (mode, configure_or_client, wallet_or_evm_client)."""
    try:
        from cdp import Cdp, Wallet  # type: ignore[import-not-found]

        return "legacy", Cdp, Wallet
    except ImportError:
        pass
    try:
        from cdp import CdpClient  # type: ignore[import-not-found]

        return "modern", CdpClient, None
    except ImportError as e:
        raise RuntimeError(
            "cdp-sdk not installed; run `pip install cdp-sdk` (or `uv pip install cdp-sdk`)"
        ) from e


def _configure() -> None:
    global _configured, _cdp_mode, _cdp_client
    if _configured:
        return
    settings = get_settings()
    key_id = settings.cdp_effective_key_name
    key_secret = settings.cdp_effective_key_secret
    wallet_secret = settings.cdp_effective_wallet_secret
    if not key_id or not key_secret:
        raise RuntimeError(
            "CDP API credentials must be set in .env (CDP_API_KEY_NAME/CDP_API_KEY_ID and "
            "CDP_API_KEY_PRIVATE_KEY/CDP_API_KEY_SECRET)."
        )
    mode, cfg_or_client, _ = _import_cdp()
    if mode == "legacy":
        cfg_or_client.configure(
            api_key_name=key_id,
            private_key=key_secret,
        )
    else:
        client_kwargs: dict[str, Any] = {
            "api_key_id": key_id,
            "api_key_secret": key_secret,
        }
        if wallet_secret:
            client_kwargs["wallet_secret"] = wallet_secret
        _cdp_client = cfg_or_client(**client_kwargs)
    _cdp_mode = mode
    _configured = True
    logger.debug("CDP SDK configured mode=%s", _cdp_mode)


async def create_wallet(network_id: str = _NETWORK_ID) -> str:
    """Create a new CDP wallet on Base Sepolia. Returns wallet_id (string)."""
    _configure()
    mode, _, Wallet = _import_cdp()
    if mode == "legacy":
        def _sync() -> str:
            wallet = Wallet.create(network_id=network_id)
            return str(wallet.id)

        wid = await asyncio.to_thread(_sync)
    else:
        if _cdp_client is None:
            raise RuntimeError("CDP client not initialized")
        acct = await _resolve_maybe_async_await(
            _cdp_client.evm.create_account(name=f"appbid-{network_id}-{uuid4().hex[:8]}")
        )
        # Modern SDK account addressing is the stable lookup key.
        wid = str(acct.address)
    logger.info("created wallet wallet_id=%s network=%s", wid, network_id)
    return wid


async def get_wallet(wallet_id: str) -> Any:
    """Fetch a hydrated wallet object by id."""
    _configure()
    mode, _, Wallet = _import_cdp()
    if mode == "legacy":
        return await asyncio.to_thread(lambda: Wallet.fetch(wallet_id))
    if _cdp_client is None:
        raise RuntimeError("CDP client not initialized")
    return await _resolve_maybe_async_await(_cdp_client.evm.get_account(address=wallet_id))


async def get_address(wallet_id: str) -> str:
    """Return the wallet's default on-chain address."""
    _configure()
    if wallet_id.startswith("0x"):
        return wallet_id
    mode, _, Wallet = _import_cdp()
    if mode == "legacy":
        def _sync() -> str:
            wallet = Wallet.fetch(wallet_id)
            return str(wallet.default_address.address_id)

        return await asyncio.to_thread(_sync)
    if _cdp_client is None:
        raise RuntimeError("CDP client not initialized")
    wallet = await _resolve_maybe_async_await(_cdp_client.evm.get_account(address=wallet_id))
    return str(wallet.address)


async def get_balance(wallet_id: str, asset: str = _USDC) -> Decimal:
    """Return on-chain balance of `asset` for the wallet, in human units."""
    _configure()
    mode, _, Wallet = _import_cdp()
    if mode == "legacy":
        def _sync() -> Decimal:
            wallet = Wallet.fetch(wallet_id)
            return Decimal(str(wallet.balance(asset)))

        return await asyncio.to_thread(_sync)
    if _cdp_client is None:
        raise RuntimeError("CDP client not initialized")
    wallet = await _resolve_maybe_async_await(_cdp_client.evm.get_account(address=wallet_id))
    balances = await _resolve_maybe_async_await(wallet.list_token_balances(network=_NETWORK_ID))
    items = getattr(balances, "balances", None) or getattr(balances, "items", None) or []
    for entry in items:
        token = (getattr(entry, "token", "") or getattr(entry, "symbol", "")).lower()
        if asset.lower() in token:
            raw = getattr(entry, "amount", None) or getattr(entry, "value", None) or "0"
            # Modern SDK commonly reports atomic token units for ERC20 balances.
            return Decimal(str(raw)) / Decimal(10**6)
    return Decimal("0")


async def fund_wallet(wallet_id: str, asset: str = _USDC) -> str:
    """Request testnet faucet drip for the wallet. Returns tx hash."""
    _configure()
    mode, _, Wallet = _import_cdp()
    if mode == "legacy":
        def _sync() -> str:
            wallet = Wallet.fetch(wallet_id)
            faucet_tx = wallet.faucet(asset_id=asset)
            if hasattr(faucet_tx, "wait"):
                faucet_tx.wait()
            tx_hash = getattr(faucet_tx, "transaction_hash", None) or getattr(
                faucet_tx, "tx_hash", ""
            )
            return str(tx_hash)

        tx_hash = await asyncio.to_thread(_sync)
    else:
        if _cdp_client is None:
            raise RuntimeError("CDP client not initialized")
        wallet = await _resolve_maybe_async_await(_cdp_client.evm.get_account(address=wallet_id))
        tx_hash = str(await _resolve_maybe_async_await(wallet.request_faucet(network=_NETWORK_ID, token=asset)))
    logger.info("faucet wallet_id=%s asset=%s tx=%s", wallet_id, asset, tx_hash)
    return tx_hash


async def transfer_usdc(from_wallet_id: str, to_address: str, amount: Decimal) -> str:
    """Send `amount` USDC from `from_wallet_id` to `to_address`. Returns tx hash."""
    if amount <= 0:
        raise ValueError(f"transfer amount must be positive, got {amount}")

    _configure()
    mode, _, Wallet = _import_cdp()
    if mode == "legacy":
        def _sync() -> str:
            wallet = Wallet.fetch(from_wallet_id)
            transfer = wallet.transfer(
                amount=str(amount),
                asset_id=_USDC,
                destination=to_address,
                gasless=True,
            )
            if hasattr(transfer, "wait"):
                transfer.wait()
            return str(getattr(transfer, "transaction_hash", "") or "")

        tx_hash = await asyncio.to_thread(_sync)
    else:
        if _cdp_client is None:
            raise RuntimeError("CDP client not initialized")
        wallet = await _resolve_maybe_async_await(_cdp_client.evm.get_account(address=from_wallet_id))
        tx_hash = str(
            await _resolve_maybe_async_await(
                wallet.transfer(
                    to=to_address,
                    amount=_usdc_to_atomic(amount),
                    token=_USDC,
                    network=_NETWORK_ID,
                )
            )
        )
    logger.info(
        "transfer from=%s to=%s amount=%s tx=%s",
        from_wallet_id,
        to_address,
        amount,
        tx_hash,
    )
    return tx_hash


async def batched_transfer(
    from_wallet_id: str,
    recipients: list[tuple[str, Decimal]],
) -> list[str]:
    """Send USDC to multiple recipients from one source wallet.

    For atomic batching a Coinbase Smart Wallet would be used; we fall back
    to sequential transfers, which is acceptable for the hackathon scope. A
    failure mid-list raises and leaves earlier transfers landed.
    """
    txs: list[str] = []
    for to_address, amount in recipients:
        tx = await transfer_usdc(from_wallet_id, to_address, amount)
        txs.append(tx)
    return txs
