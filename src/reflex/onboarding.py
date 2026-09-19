from __future__ import annotations

from dataclasses import dataclass

from web3 import Web3
from web3.middleware import ExtraDataToPOAMiddleware

from .config import Settings

# Current Polymarket collateral token (replaces the deprecated USDC.e-direct
# model): https://docs.polymarket.com/concepts/pusd — pUSD is a standard
# ERC-20 wrapper backed by USDC, minted via the CollateralOnramp contract.
# Address confirmed against Polymarket's own published contracts page
# (docs.polymarket.com/resources/contracts) on 2026-09-19.
_PUSD_ADDRESS = "0xC011a7E12a19f7B1f670d46F03B03f3342E82DFB"

_ERC20_BALANCE_ABI = [
    {
        "constant": True,
        "inputs": [{"name": "owner", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"name": "", "type": "uint256"}],
        "type": "function",
    },
]


@dataclass(frozen=True)
class WalletStatus:
    address: str
    pusd_balance: float
    matic_balance: float

    @property
    def ready_to_trade(self) -> bool:
        # The current SDK (polymarket-client) sets any missing token
        # allowance itself the first time you place an order — there is no
        # separate manual-approval step to check here anymore. MATIC is
        # still needed to pay gas for that first approval + each order.
        return self.pusd_balance > 0 and self.matic_balance > 0


def _web3(settings: Settings) -> Web3:
    # Polygon is a POA-style chain — without this middleware, web3.py's
    # block/gas-estimation calls fail with ExtraDataLengthError (verified
    # against the live public RPC while building this).
    w3 = Web3(Web3.HTTPProvider(settings.polygon_rpc_url))
    w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)
    return w3


def check_wallet(settings: Settings, address: str) -> WalletStatus:
    """Read-only: reports pUSD (Polymarket's trading collateral) and MATIC
    (for gas) balances. Needs only a public address — never a private key.

    Note: if you deposited through polymarket.com, your tradeable balance
    lives here as pUSD already — you should NOT need to wrap anything
    yourself. If this shows 0 pUSD despite having deposited, check whether
    your funds landed in a separate Deposit Wallet address rather than this
    EOA (see README) before assuming something is wrong.
    """
    w3 = _web3(settings)
    checksum_address = Web3.to_checksum_address(address)
    pusd = w3.eth.contract(address=Web3.to_checksum_address(_PUSD_ADDRESS), abi=_ERC20_BALANCE_ABI)

    return WalletStatus(
        address=checksum_address,
        pusd_balance=pusd.functions.balanceOf(checksum_address).call() / 1_000_000,  # 6 decimals
        matic_balance=w3.eth.get_balance(checksum_address) / 1e18,
    )
