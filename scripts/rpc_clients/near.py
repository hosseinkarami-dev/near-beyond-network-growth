"""Typed client wrapper for reusable NEAR JSON-RPC calls."""

from inspect import signature

from near_jsonrpc_client import NearClientSync
from near_jsonrpc_models import (
    BlockId,
    BlockIdBlockHeight,
    RpcBlockRequest,
    RpcBlockRequestBlockId,
    RpcBlockResponse,
    AccountId,
    Finality,
    RpcQueryRequest,
    RpcQueryRequestViewAccountByFinality,
    RpcValidatorRequest,
    RpcValidatorRequestEpochId,
    RpcValidatorResponse,
)


class NearRpcClient:
    """Small reusable facade over the generated, typed NEAR RPC client."""

    def __init__(self, endpoint: str, timeout: float = 30) -> None:
        parameters = signature(NearClientSync).parameters
        url_parameter = "rpc_urls" if "rpc_urls" in parameters else "base_url"
        self._client = NearClientSync(**{url_parameter: endpoint}, timeout=timeout)

    def block(self, height: int) -> RpcBlockResponse:
        params = RpcBlockRequest(
            RpcBlockRequestBlockId(block_id=BlockId(BlockIdBlockHeight(height)))
        )
        return self._client.block(params=params)

    def validators(self, epoch_id: str) -> RpcValidatorResponse:
        params = RpcValidatorRequest(RpcValidatorRequestEpochId(epoch_id=epoch_id))
        return self._client.validators(params=params)

    def account(self, account_id: str, *, finality: str = "final"):
        """Read a typed account-view snapshot at the requested finality."""
        params = RpcQueryRequest(
            RpcQueryRequestViewAccountByFinality(
                finality=Finality(finality),
                account_id=AccountId(account_id),
                request_type="view_account",
            )
        )
        return self._client.query(params=params)

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "NearRpcClient":
        return self

    def __exit__(self, *_exc) -> None:
        self.close()
