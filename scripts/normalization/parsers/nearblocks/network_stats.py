"""Normalize selected NearBlocks V3 network-stat snapshot fields."""
from datetime import datetime, timezone

from sources import SourceName, source_metadata
from units import yocto_near_to_near


TOKENOMICS_FIELDS = {
    "change_24h", "circulating_supply", "daily_burn", "market_cap",
    "near_btc_price", "near_price", "net_supply_change", "total_supply",
    "volume_24h",
}

def _source_data(raw_data):
    if not isinstance(raw_data, dict) or not isinstance(raw_data.get("data"), dict):
        raise ValueError("Expected NearBlocks response object containing a data object")
    return raw_data["data"]


def _source_metadata():
    return source_metadata(
        SourceName.NEAR_BLOCKS_NETWORK_STATS,
        attribution="Powered by NearBlocks.io APIs",
    )


def parse_network_stats(raw_data):
    source_data = _source_data(raw_data)
    metrics = {
        field: {"metric_id": f"near.{field}", "value": value}
        for field, value in source_data.items() if field not in TOKENOMICS_FIELDS
    }

    return {
        "summary.json": {
            "schema_version": "1.0.0",
            "network": "NEAR mainnet",
            "source": _source_metadata(),
            "snapshot_type": "network_level",
            "frequency": "snapshot",
            "updated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "metrics": metrics,
        }
    }


def parse_tokenomics_summary(raw_data):
    source_data = _source_data(raw_data)
    names = {
        "change_24h": "24 Hour Change",
        "circulating_supply": "Circulating Supply",
        "daily_burn": "Daily Burn",
        "market_cap": "Market Capitalization",
        "near_btc_price": "NEAR Price in BTC",
        "near_price": "NEAR Price",
        "net_supply_change": "Net Supply Change",
        "total_supply": "Total Supply",
        "volume_24h": "24 Hour Volume",
    }
    metrics = {}
    for field, name in names.items():
        if field in source_data:
            if field in {"total_supply", "circulating_supply", "daily_burn", "net_supply_change"}:
                metrics[field] = {
                    "metric_id": f"near.{field}",
                    "name": name,
                    "value": yocto_near_to_near(source_data[field]),
                    "unit": "NEAR",
                    "value_type": "decimal",
                }
            else:
                metrics[field] = {"metric_id": f"near.{field}", "name": name,
                                  "value": source_data[field]}

    return {
        "summary.json": {
            "schema_version": "1.0.0",
            "network": "NEAR mainnet",
            "source": _source_metadata(),
            "snapshot_type": "network_level",
            "frequency": "snapshot",
            "updated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "metrics": metrics,
        }
    }
