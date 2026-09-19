from __future__ import annotations

from dataclasses import dataclass

from web3 import Web3
from web3.middleware import ExtraDataToPOAMiddleware

from .config import Settings

try:
    from py_clob_client.config import ContractConfig, get_contract_config
except ImportError as exc:  # pragma: no cover
    raise ImportError("Install the 'live' extra (`pip install -e '.[live]'`) to use onboarding.py") from exc

_ERC20_ABI = [
    {
        "constant": True,
        "inputs": [{"name": "owner", "type": "address"}, {"name": "spender", "type": "address"}],
        "name": "allowance",
        "outputs": [{"name": "", "type": "uint256"}],
        "type": "function",
    },
    {
        "constant": True,
        "inputs": [{"name": "owner", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"name": "", "type": "uint256"}],
        "type": "function",
    },
    {
        "constant": False,
        "inputs": [{"name": "spender", "type": "address"}, {"name": "amount", "type": "uint256"}],
        "name": "approve",
        "outputs": [{"name": "", "type": "bool"}],
        "type": "function",
    },
]

_ERC1155_ABI = [
    {
        "constant": True,
        "inputs": [{"name": "account", "type": "address"}, {"name": "operator", "type": "address"}],
        "name": "isApprovedForAll",
        "outputs": [{"name": "", "type": "bool"}],
        "type": "function",
    },
    {
        "constant": False,
        "inputs": [{"name": "operator", "type": "address"}, {"name": "approved", "type": "bool"}],
        "name": "setApprovalForAll",
        "outputs": [],
        "type": "function",
    },
]

# Polymarket's CLOB needs approvals against both the standard exchange and
# the "neg-risk" exchange (used for multi-outcome markets grouped into a
# single negative-risk contract) — a market's `negRisk` flag decides which
# one an order for it needs. Trading a mix of markets means approving both.
_USDC_MAX_ALLOWANCE = 2**256 - 1


@dataclass(frozen=True)
class ExchangeApprovalStatus:
    label: str
    exchange_address: str
    usdc_allowance: int
    ctf_approved: bool

    @property
    def ready(self) -> bool:
        return self.usdc_allowance > 0 and self.ctf_approved


@dataclass(frozen=True)
class WalletStatus:
    address: str
    usdc_balance: float
    matic_balance: float
    exchanges: list[ExchangeApprovalStatus]

    @property
    def ready_to_trade(self) -> bool:
        return all(e.ready for e in self.exchanges) and self.usdc_balance > 0 and self.matic_balance > 0


def _web3(settings: Settings) -> Web3:
    # Polygon is a POA-style chain — without this middleware, web3.py's
    # block/gas-estimation calls fail with ExtraDataLengthError (verified
    # against the live public RPC while building this).
    w3 = Web3(Web3.HTTPProvider(settings.polygon_rpc_url))
    w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)
    return w3


def check_wallet(settings: Settings, address: str) -> WalletStatus:
    """Read-only: reports USDC/MATIC balances and current approval status
    against both Polymarket exchange contracts. Needs only a public
    address — never a private key."""
    w3 = _web3(settings)
    checksum_address = Web3.to_checksum_address(address)

    regular = get_contract_config(137, neg_risk=False)
    neg_risk = get_contract_config(137, neg_risk=True)
    usdc = w3.eth.contract(address=Web3.to_checksum_address(regular.collateral), abi=_ERC20_ABI)
    ctf = w3.eth.contract(address=Web3.to_checksum_address(regular.conditional_tokens), abi=_ERC1155_ABI)

    exchanges = []
    for label, cfg in (("standard", regular), ("neg-risk", neg_risk)):
        exchange_addr = Web3.to_checksum_address(cfg.exchange)
        exchanges.append(
            ExchangeApprovalStatus(
                label=label,
                exchange_address=exchange_addr,
                usdc_allowance=usdc.functions.allowance(checksum_address, exchange_addr).call(),
                ctf_approved=ctf.functions.isApprovedForAll(checksum_address, exchange_addr).call(),
            )
        )

    return WalletStatus(
        address=checksum_address,
        usdc_balance=usdc.functions.balanceOf(checksum_address).call() / 1_000_000,  # USDC has 6 decimals
        matic_balance=w3.eth.get_balance(checksum_address) / 1e18,
        exchanges=exchanges,
    )


def ensure_approvals(settings: Settings) -> list[str]:
    """Sends whichever approve()/setApprovalForAll() transactions are
    missing, for both the standard and neg-risk exchanges. Requires
    POLYGON_WALLET_PRIVATE_KEY and MATIC in the wallet for gas. Returns the
    tx hashes of whatever it actually sent (empty if already fully approved).
    """
    if not settings.polygon_private_key:
        raise RuntimeError("POLYGON_WALLET_PRIVATE_KEY is not set")

    w3 = _web3(settings)
    account = w3.eth.account.from_key(settings.polygon_private_key)
    address = account.address

    status = check_wallet(settings, address)
    regular = get_contract_config(137, neg_risk=False)
    neg_risk = get_contract_config(137, neg_risk=True)
    usdc = w3.eth.contract(address=Web3.to_checksum_address(regular.collateral), abi=_ERC20_ABI)
    ctf = w3.eth.contract(address=Web3.to_checksum_address(regular.conditional_tokens), abi=_ERC1155_ABI)

    tx_hashes: list[str] = []
    nonce = w3.eth.get_transaction_count(address)

    for exchange_status, cfg in zip(status.exchanges, (regular, neg_risk)):
        exchange_addr = Web3.to_checksum_address(cfg.exchange)

        if exchange_status.usdc_allowance == 0:
            tx = usdc.functions.approve(exchange_addr, _USDC_MAX_ALLOWANCE).build_transaction(
                {"from": address, "nonce": nonce, "chainId": 137}
            )
            nonce += 1
            tx_hashes.append(_sign_and_send(w3, tx, account))

        if not exchange_status.ctf_approved:
            tx = ctf.functions.setApprovalForAll(exchange_addr, True).build_transaction(
                {"from": address, "nonce": nonce, "chainId": 137}
            )
            nonce += 1
            tx_hashes.append(_sign_and_send(w3, tx, account))

    return tx_hashes


def _sign_and_send(w3: Web3, tx: dict, account) -> str:
    signed = account.sign_transaction(tx)
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
    return tx_hash.hex()
