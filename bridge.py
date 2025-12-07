from web3 import Web3
from web3.providers.rpc import HTTPProvider
from web3.middleware import ExtraDataToPOAMiddleware  # Necessary for POA chains
from datetime import datetime
import json
import pandas as pd


def connect_to(chain):
    if chain == 'source':  # The source contract chain is avax
        api_url = "https://api.avax-test.network/ext/bc/C/rpc"  # AVAX C-chain testnet

    if chain == 'destination':  # The destination contract chain is bsc
        api_url = "https://data-seed-prebsc-1-s1.binance.org:8545/"  # BSC testnet

    if chain in ['source', 'destination']:
        w3 = Web3(Web3.HTTPProvider(api_url))
        # inject the poa compatibility middleware to the innermost layer
        w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)
        return w3

    return None


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
        Scan recent blocks of the source and destination chains
        Look for 'Deposit' events on the source chain and 'Unwrap' events on the destination chain
        When Deposit events are found on the source chain, call the 'wrap' function on the destination chain
        When Unwrap events are found on the destination chain, call the 'withdraw' function on the source chain
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

    # Scan recent blocks (look back ~40 blocks to be safe)
    latest_block = w3_this.eth.block_number
    from_block = max(latest_block - 40, 0)
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

    # -------- SOURCE CHAIN: handle Deposit -> wrap() on destination --------
    if chain == "source":
        try:
            # web3.py v7 uses snake_case params; it converts to JSON "fromBlock"/"toBlock"
            events = this_contract.events.Deposit().get_logs(
                from_block=from_block,
                to_block=to_block,
            )
        except Exception as e:
            print(f"Error fetching Deposit logs on source: {e}")
            return 0

        if len(events) == 0:
            print("No Deposit events found on source in recent blocks")
            return 1

        base_nonce = w3_other.eth.get_transaction_count(warden_addr)

        for i, ev in enumerate(events):
            args = ev["args"]
            # event Deposit(address token, address recipient, uint256 amount)
            token = args["token"]
            recipient = args["recipient"]
            amount = args["amount"]

            print(f"Found Deposit on source: tx={ev['transactionHash'].hex()}")
            print(f"  token={token}, recipient={recipient}, amount={amount}")

            try:
                tx = other_contract.functions.wrap(
                    token,
                    recipient,
                    amount
                ).build_transaction({
                    "from": warden_addr,
                    "nonce": base_nonce + i,
                    "gas": 300000,
                    "gasPrice": w3_other.eth.gas_price,
                    "chainId": w3_other.eth.chain_id,
                })

                signed = w3_other.eth.account.sign_transaction(tx, private_key=warden_pk)
                raw_tx = get_raw_tx(signed)
                tx_hash = w3_other.eth.send_raw_transaction(raw_tx)
                print(f"Sent wrap() on destination: {tx_hash.hex()}")
            except Exception as e:
                print(f"Error sending wrap() tx on destination: {e}")

        return 1

    # -------- DESTINATION CHAIN: handle Unwrap -> withdraw() on source --------
    # Instead of eth_getLogs (which hits 'limit exceeded' on BSC), we:
    #   - iterate over blocks
    #   - fetch each block's transactions
    #   - fetch each transaction receipt
    #   - scan logs for Unwrap events from our Destination contract
    unwrap_topic0 = Web3.keccak(
        text="Unwrap(address,address,address,address,uint256)"
    ).hex().lower()

    events = []

    for b in range(from_block, to_block + 1):
        try:
            block = w3_this.eth.get_block(b, full_transactions=True)
        except Exception as e:
            print(f"Error fetching block {b} on {chain}: {e}")
            continue

        # block["transactions"] can be a list of tx dicts or hashes depending on full_transactions
        for tx in block["transactions"]:
            try:
                if isinstance(tx, dict):
                    tx_hash = tx["hash"]
                else:
                    tx_hash = tx

                receipt = w3_this.eth.get_transaction_receipt(tx_hash)

                for log in receipt["logs"]:
                    # only care about logs from our Destination contract
                    if log["address"].lower() != this_address.lower():
                        continue
                    if not log["topics"]:
                        continue
                    if log["topics"][0].hex().lower() != unwrap_topic0:
                        continue
                    try:
                        ev = this_contract.events.Unwrap().process_log(log)
                        events.append(ev)
                    except Exception:
                        # if decoding fails, skip this log
                        continue
            except Exception:
                # receipt or log issues: skip this tx
                continue

    if len(events) == 0:
        print("No Unwrap events found on destination in recent blocks")
        return 1

    base_nonce = w3_other.eth.get_transaction_count(warden_addr)

    for i, ev in enumerate(events):
        args = ev["args"]
        # event Unwrap(
        #   address underlying_token,
        #   address wrapped_token,
        #   address frm,
        #   address to,
        #   uint256 amount
        # );
        underlying = args["underlying_token"]
        recipient = args["to"]
        amount = args["amount"]

        print(f"Found Unwrap on destination: tx={ev['transactionHash'].hex()}")
        print(f"  underlying={underlying}, to={recipient}, amount={amount}")

        try:
            tx = other_contract.functions.withdraw(
                underlying,
                recipient,
                amount
            ).build_transaction({
                "from": warden_addr,
                "nonce": base_nonce + i,
                "gas": 300000,
                "gasPrice": w3_other.eth.gas_price,
                "chainId": w3_other.eth.chain_id,
            })

            signed = w3_other.eth.account.sign_transaction(tx, private_key=warden_pk)
            raw_tx = get_raw_tx(signed)
            tx_hash = w3_other.eth.send_raw_transaction(raw_tx)
            print(f"Sent withdraw() on source: {tx_hash.hex()}")
        except Exception as e:
            print(f"Error sending withdraw() tx on source: {e}")

    return 1
