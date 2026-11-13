"""Normalize a raw NEAR RPC account-balance view."""

from decimal import Decimal, localcontext

from buybacks import BUYBACK_WALLET
from sources import SourceName, get_source, source_metadata
from units import YOCTO_PER_NEAR


def _amount_near(raw_value: object, field: str) -> Decimal:
    if not isinstance(raw_value, str) or not raw_value.isdigit():
        raise ValueError(f"Raw {field} must be an unsigned yoctoNEAR integer string")
    with localcontext() as context:
        context.prec = 60
        return Decimal(int(raw_value)) / Decimal(YOCTO_PER_NEAR)


def parse_buyback_wallet_balance(raw_data):
    if not isinstance(raw_data, dict):
        raise ValueError("Buyback wallet balance raw data must be an object")
    if raw_data.get("account_id") != BUYBACK_WALLET:
        raise ValueError("Unexpected buyback wallet account_id")
    amount = _amount_near(raw_data.get("amount_yocto"), "amount_yocto")
    locked = _amount_near(raw_data.get("locked_yocto"), "locked_yocto")
    block_height = raw_data.get("block_height")
    if isinstance(block_height, bool) or not isinstance(block_height, int) or block_height < 0:
        raise ValueError("Buyback wallet block_height must be a non-negative integer")

    return {
        "buyback_wallet_balance.json": {
            "schema_version": "1.0.0",
            "network": "NEAR mainnet",
            "source": source_metadata(
                SourceName.FASTNEAR_BUYBACK_WALLET_BALANCE,
                dataset=get_source(SourceName.FASTNEAR_BUYBACK_WALLET_BALANCE).dataset,
                method="query",
                request_type="view_account",
                finality="final",
            ),
            "account_id": raw_data["account_id"],
            "snapshot_date": raw_data["snapshot_date"],
            "updated_at": raw_data["updated_at"],
            "block_height": block_height,
            "block_hash": raw_data.get("block_hash"),
            "metrics": {
                "balance_near": amount,
                "locked_near": locked,
                "balance_type": raw_data.get("balance_type"),
            },
        }
    }
