"""Fetch and persist the latest finalized buyback-wallet account balance."""

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from atomic_io import atomic_write_text
from buybacks import BUYBACK_WALLET
from console_ui import console
from rpc_clients.near import NearRpcClient
from sources import Source, SourceName, get_source, raw_path


def _field(value: Any, name: str) -> Any:
    return value.get(name) if isinstance(value, dict) else getattr(value, name, None)


def _root(value: Any) -> Any:
    return _field(value, "root")


def _yocto(value: Any, name: str) -> int:
    raw = _root(value)
    if raw is None:
        raw = value
    if isinstance(raw, bool):
        raise ValueError(f"RPC account {name} must be a non-negative yoctoNEAR integer")
    if isinstance(raw, int):
        result = raw
    elif isinstance(raw, str) and raw.isdigit():
        result = int(raw)
    else:
        raise ValueError(f"RPC account {name} must be a non-negative yoctoNEAR integer")
    if result < 0:
        raise ValueError(f"RPC account {name} must be non-negative")
    return result


def collect_buyback_wallet_balance(
    source: Source | None = None,
    *,
    output_path: Path | None = None,
    timeout: float = 30,
    attempts: int = 3,
    sleep=time.sleep,
) -> bool:
    """Refresh one finalized wallet snapshot; preserve old data if RPC fails."""

    source = source or get_source(SourceName.FASTNEAR_BUYBACK_WALLET_BALANCE)
    output = Path(output_path) if output_path is not None else raw_path(source)
    if source.url is None:
        console.print("[yellow]![/yellow] Buyback wallet balance RPC endpoint is missing")
        return False

    last_error: Exception | None = None
    for attempt in range(attempts):
        try:
            with NearRpcClient(source.url, timeout=timeout) as rpc:
                response = rpc.account(BUYBACK_WALLET, finality="final")
            account = _root(response)
            amount = _yocto(_field(account, "amount"), "amount")
            locked = _yocto(_field(account, "locked"), "locked")
            block_height = _field(account, "block_height")
            block_hash = _root(_field(account, "block_hash"))
            if isinstance(block_height, bool) or not isinstance(block_height, int) or block_height < 0:
                raise ValueError("RPC account response has an invalid block_height")
            snapshot = {
                "schema_version": "1.0.0",
                "dataset": "Buyback Wallet Balance",
                "network": "NEAR mainnet",
                "source": {
                    "provider": source.provider.value,
                    "endpoint": source.url,
                    "method": "query",
                    "request_type": "view_account",
                    "finality": "final",
                },
                "account_id": BUYBACK_WALLET,
                "snapshot_date": datetime.now(timezone.utc).date().isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                "block_height": block_height,
                "block_hash": block_hash,
                "amount_yocto": str(amount),
                "locked_yocto": str(locked),
                "balance_type": "liquid_amount_excludes_locked_stake",
            }
            atomic_write_text(output, json.dumps(snapshot, indent=2, ensure_ascii=False) + "\n")
            console.print(f"[green]OK[/green] Buyback wallet balance [dim]updated at block {block_height}[/dim]")
            return True
        except Exception as exc:
            last_error = exc
            if attempt + 1 < attempts:
                delay = min(2 ** attempt, 8)
                console.print(f"[yellow]![/yellow] Buyback balance RPC retrying in {delay}s [dim]{exc}[/dim]")
                sleep(delay)

    console.print(f"[yellow]![/yellow] Buyback wallet balance unavailable [dim]{last_error}[/dim]")
    return False
