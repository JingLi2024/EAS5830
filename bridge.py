from web3 import Web3
from web3.providers.rpc import HTTPProvider
from web3.middleware import ExtraDataToPOAMiddleware  # Necessary for POA chains
from datetime import datetime
import json
import pandas as pd


def connect_to(chain):
    if chain == 'source':  # The source contract chain is avax
        api_url = "https://api.avax-test.network/ext/bc/C/rpc"  # AVAX C-chain testnet
    elif chain == 'destination':  # The destination contract chain is bsc
        # Public RPC for BSC testnet
        api_url = "https://data-seed-prebsc-1-s1.binance.org:8545/"
    else:
        return None

    w3 = Web3(Web3.HTTPProvider(api_url))
    # inject the poa compatibility middleware to the innermost layer
    w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)
    return w3


def get_contract_info(chain, contract_info):
    """
        Load the contract_info file into a dictionary
        This function is used by the autograder and will likely be useful to you
    """
    try:
        with open(contract_info, 'r') as f:
            contracts = json.load(f)
    except Exception as e:
        print(f"Failed to read contract info\nPlease contact your instructor\n{e}")
        return 0
    return contracts[chain]


def scan_blocks(chain, contract_info="contract_info.json"):
    """
        chain - (string) should be either "source" or "destination"
        Scan recent blocks.
        - On 'source': look for Deposit events and call wrap() on destination
        - On 'destination': look for Unwrap events and call withdraw() on source
    """

    if chain not in ['source', 'destination']:
        print(f"Invalid chain: {chain}")
        return 0

    # Determine the opposite chain
    other_chain = 'destination' if chain == 'source' else 'source'

    # Load contract info for this chain and the other chain
    this_info = get_contract_info(chain, contract_info)
    other_info = get_contract_info(other_chain, contract_info)

    if this_info == 0 or other_info == 0:
        print("Error: could not load contract info")
        return 0

    try:
        this_address = Web3.to_checksum_address(this_info["address"])
        this_abi = this_info["abi"]
        other_address = Web3.to_checksum_address(other_info["address"])
        other_abi = other_info["abi"]
    except KeyError as e:
        print(f"Missing key in contract_info.json: {e}")
        return 0

    # Warden private key (same as the deployer / your account)
    # NOTE: this is OK here only because it's a testnet key with no real funds.
    warden_pk = "0x20f749266735fdb006af4fe73aacc24b4d6aca494e262c4555eee277d87fdbd1"

    # Connect to both chains
    w3_this = connect_to(chain)
    w3_other = connect_to(other_chain)

    if w3_this is None or w3_other is None:
        print("Error: could not connect to one of the chains")
        return 0

    # Derive warden address (same account used on both chains)
    warden_acct = w3_this.eth.account.from_key(warden_pk)
    warden_addr = warden_acct.address

    # Build contract objects
    this_contract = w3_this.eth.contract(address=this_address, abi=this_abi)
    other_contract = w3_other.eth.contract(address=other_address, abi=other_abi)

    latest_block = w3_this.eth.block_number

    # Window size: keep it small to keep RPC happy
    if chain == "source":
        window_size = 10
    else:
        window_size = 10  # small on destination too, receipts fallback will do the heavy lifting

    from_block = max(latest_block - window_size, 0)
    to_block = latest_block

    if from_block == to_block:
        print(f"[{datetime.utcnow()}] Scanning block {from_block} on {chain}")
    else:
        print(f"[{datetime.utcnow()}] Scanning blocks {from_block}-{to_block} on {chain}")

    # Helper to extract raw tx safely
    def get_raw_tx(signed_tx):
        if hasattr(signed_tx, "rawTransaction"):
            return signed_tx.rawTransaction
        if isinstance(signed_tx, dict) and "rawTransaction" in signed_tx:
            return signed_tx["rawTransaction"]
        if hasattr(signed_tx, "raw_transaction"):
            return signed_tx.raw_transaction
        if isinstance(signed_tx, dict) and "raw_transaction" in signed_tx:
            return signed_tx["raw_transaction"]
        raise RuntimeError("Could not extract rawTransaction from signed tx")

    # ------------------------------------------------------------------
    # SOURCE SIDE: look for Deposit events and call wrap() on destination
    # ------------------------------------------------------------------
    if chain == "source":
        try:
            events = this_contract.events.Deposit().get_logs(
                from_block=from_block,
                to_block=to_block
            )
        except Exception as e:
            # Fatal error fetching logs on Source chain
            print(f"Error fetching Deposit logs on source: {e}")
            return 0  # Fail hard if Source logging fails

        if len(events) == 0:
            print("No Deposit events found on source in recent blocks")
            return 1

        try:
            base_nonce = w3_other.eth.get_transaction_count(warden_addr)
        except Exception as e:
            # Fatal error: cannot get nonce on destination chain. The RPC is dead.
            print(f"Error fetching nonce on destination: {e}")
            return 0

        for i, ev in enumerate(events):
            args = ev["args"]
            # event Deposit(address token, add
