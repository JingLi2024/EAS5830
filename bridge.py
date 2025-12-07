from web3 import Web3
from web3.providers.rpc import HTTPProvider
from web3.middleware import ExtraDataToPOAMiddleware #Necessary for POA chains
from datetime import datetime
import json
import pandas as pd


def connect_to(chain):
    if chain == 'source':  # The source contract chain is avax
        api_url = f"https://api.avax-test.network/ext/bc/C/rpc" #AVAX C-chain testnet

    if chain == 'destination':  # The destination contract chain is bsc
        api_url = f"https://data-seed-prebsc-1-s1.binance.org:8545/" #BSC testnet

    if chain in ['source','destination']:
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
        with open(contract_info, 'r')  as f:
            contracts = json.load(f)
    except Exception as e:
        print( f"Failed to read contract info\nPlease contact your instructor\n{e}" )
        return 0
    return contracts[chain]



def scan_blocks(chain, contract_info="contract_info.json"):
    """
        chain - (string) should be either "source" or "destination"
        Scan the last 5 blocks of the source and destination chains
        Look for 'Deposit' events on the source chain and 'Unwrap' events on the destination chain
        When Deposit events are found on the source chain, call the 'wrap' function the destination chain
        When Unwrap events are found on the destination chain, call the 'withdraw' function on the source chain
    """

    # This is different from Bridge IV where chain was "avax" or "bsc"
    if chain not in ['source','destination']:
        print( f"Invalid chain: {chain}" )
        return 0
    
        #YOUR CODE HERE
 # ---- load full contract_info so we can see both chains + (optionally) warden key ----
    try:
        with open(contract_info, "r") as f:
            all_contracts = json.load(f)
    except Exception as e:
        print(f"Failed to read contract info\nPlease contact your instructor\n{e}")
        return 0

    try:
        source_info = all_contracts["source"]
        dest_info   = all_contracts["destination"]
    except KeyError as e:
        print(f"Missing contract info section: {e}")
        return 0

    # addresses / ABIs from your JSON
    try:
        source_address = Web3.to_checksum_address(source_info["address"])
        source_abi     = source_info["abi"]
        dest_address   = Web3.to_checksum_address(dest_info["address"])
        dest_abi       = dest_info["abi"]
    except KeyError as e:
        print(f"Missing key in contract info: {e}")
        return 0

    # ---- find warden private key ----
    warden_pk = None
    # optional top-level warden object
    if "warden" in all_contracts and "private_key" in all_contracts["warden"]:
        warden_pk = all_contracts["warden"]["private_key"]
    # or generic top-level private_key
    elif "private_key" in all_contracts:
        warden_pk = all_contracts["private_key"]
    # or per-chain
    elif "private_key" in source_info:
        warden_pk = source_info["private_key"]
    elif "private_key" in dest_info:
        warden_pk = dest_info["private_key"]
    else:
        # fallback: reuse the key from secret_key.txt (same as sign_message)
        try:
            with open("secret_key.txt", "r") as f:
                lines = f.readlines()
            assert len(lines) > 0, "secret_key.txt is empty"
            warden_pk = lines[0].strip()
        except Exception as e:
            print(f"Could not find warden private key: {e}")
            return 0

    if not str(warden_pk).startswith("0x"):
        warden_pk = "0x" + str(warden_pk)

    # ---- connect to both chains ----
    w3_source      = connect_to("source")
    w3_destination = connect_to("destination")

    # warden account (same key on both chains)
    warden_account = w3_source.eth.account.privateKeyToAccount(warden_pk)
    warden_address = warden_account.address

    # contract instances
    source_contract = w3_source.eth.contract(address=source_address, abi=source_abi)
    dest_contract   = w3_destination.eth.contract(address=dest_address, abi=dest_abi)

    # decide which chain we’re scanning and which is “other”
    if chain == "source":
        # scan Avalanche, send txs to BSC
        w3_scan        = w3_source
        scan_contract  = source_contract
        w3_other       = w3_destination
        other_contract = dest_contract
    else:
        # scan BSC, send txs to Avalanche
        w3_scan        = w3_destination
        scan_contract  = dest_contract
        w3_other       = w3_source
        other_contract = source_contract

    # ---- scan last 5 blocks on selected chain ----
    latest_block = w3_scan.eth.block_number
    from_block   = max(latest_block - 4, 0)
    to_block     = latest_block

    if from_block == to_block:
        print(f"[{datetime.utcnow()}] Scanning block {from_block} on {chain}")
    else:
        print(f"[{datetime.utcnow()}] Scanning blocks {from_block}-{to_block} on {chain}")

    # ---- handle events ----
    if chain == "source":
        # Look for Deposit(token, recipient, amount) on source
        try:
            events = scan_contract.events.Deposit().get_logs(
                fromBlock=from_block,
                toBlock=to_block
            )
        except Exception as e:
            print(f"Error fetching Deposit logs on source: {e}")
            return 0

        if len(events) == 0:
            print("No Deposit events found on source in last 5 blocks")
            return 1

        base_nonce = w3_other.eth.get_transaction_count(warden_address)

        for i, ev in enumerate(events):
            args = ev["args"]
            token     = args["token"]
            recipient = args["recipient"]
            amount    = args["amount"]

            print(f"Found Deposit on source: tx={ev['transactionHash'].hex()}")
            print(f"  token={token}, recipient={recipient}, amount={amount}")

            try:
                tx = other_contract.functions.wrap(
                    token,
                    recipient,
                    amount
                ).build_transaction({
                    "from": warden_address,
                    "nonce": base_nonce + i,
                    "gas": 300000,
                    "gasPrice": w3_other.eth.gas_price,
                    "chainId": w3_other.eth.chain_id
                })

                signed = w3_other.eth.account.sign_transaction(tx, private_key=warden_pk)
                tx_hash = w3_other.eth.send_raw_transaction(signed.rawTransaction)
                print(f"Sent wrap() on destination: {tx_hash.hex()}")
            except Exception as e:
                print(f"Error sending wrap() tx on destination: {e}")

    else:  # chain == "destination"
        # Look for Unwrap(underlying_token, wrapped_token, frm, to, amount) on destination
        try:
            events = scan_contract.events.Unwrap().get_logs(
                fromBlock=from_block,
                toBlock=to_block
            )
        except Exception as e:
            print(f"Error fetching Unwrap logs on destination: {e}")
            return 0

        if len(events) == 0:
            print("No Unwrap events found on destination in last 5 blocks")
            return 1

        base_nonce = w3_other.eth.get_transaction_count(warden_address)

        for i, ev in enumerate(events):
            args = ev["args"]
            underlying = args["underlying_token"]
            recipient  = args["to"]
            amount     = args["amount"]

            print(f"Found Unwrap on destination: tx={ev['transactionHash'].hex()}")
            print(f"  underlying={underlying}, to={recipient}, amount={amount}")

            try:
                tx = other_contract.functions.withdraw(
                    underlying,
                    recipient,
                    amount
                ).build_transaction({
                    "from": warden_address,
                    "nonce": base_nonce + i,
                    "gas": 300000,
                    "gasPrice": w3_other.eth.gas_price,
                    "chainId": w3_other.eth.chain_id
                })

                signed = w3_other.eth.account.sign_transaction(tx, private_key=warden_pk)
                tx_hash = w3_other.eth.send_raw_transaction(signed.rawTransaction)
                print(f"Sent withdraw() on source: {tx_hash.hex()}")
            except Exception as e:
                print(f"Error sending withdraw() tx on source: {e}")

    return 1