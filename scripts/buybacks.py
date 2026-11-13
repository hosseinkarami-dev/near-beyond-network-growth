"""Shared NEAR buyback wallet and transfer-source definitions."""

BUYBACK_WALLET = "buybacks.multisignature.near"

BUYBACK_TRANSFER_LABELS = {
    "intents_transfer": "NEAR Intents",
    "frontend_revenue": "Frontend Revenue",
    "oneclick_and_other_revenue": "1Click & Other Revenue",
}
BUYBACK_TRANSFER_TYPES = frozenset(BUYBACK_TRANSFER_LABELS)
BUYBACK_TRANSFER_SENDERS = {
    "intents_transfer": "intents.near",
    "frontend_revenue": "fefundsadmin.sputnik-dao.near",
    "oneclick_and_other_revenue": "1csfundsadmin.sputnik-dao.near",
}

__all__ = [
    "BUYBACK_TRANSFER_LABELS",
    "BUYBACK_TRANSFER_SENDERS",
    "BUYBACK_TRANSFER_TYPES",
    "BUYBACK_WALLET",
]
