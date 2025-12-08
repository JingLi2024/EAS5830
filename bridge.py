from web3 import Web3
from web3.providers.rpc import HTTPProvider
from web3.middleware import ExtraDataToPOAMiddleware #Necessary for POA chains
from datetime import datetime
import json
import pandas as pd
from pathlib import Path


def connect_to(chain):
    if chain == 'source':  # The source contract chain is avax
        api_url = f"https://api.avax-test.network/ext/bc/C/rpc" #AVAX C-chain testnet

    if chain == 'destination':  # The destination contract chain is bsc
        # Reverting to the original public RPC, using fallback logic to manage rate limits
        api_url = f"https://data-seed-prebsc-1-s1.binance.org:8545/" #BSC testnet

    if chain in ['source','destination']:
        w3 = Web3(Web3.HTTPProvider(api_url))
        # inject the poa compatibility middleware to the innermost layer
        w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)
    return w3


def get_contract_info(chain, contract_info):
    """
        Load the contract_info file into a dictionary
    """
    try:
        with open(contract_info, 'r') as f:
            contracts = json.load(f)
    except Exception as e:
        print( f"Failed to read contract info\nPlease contact your instructor\n{e}" )
        return 0
    return contracts[chain]


def scan_blocks(chain, contract_info="contract_info.json"):
    """
        chain - (string) should be either "source" or "destination"
        Scan for 'Deposit' events on the source chain and 'Unwrap' events on the destination chain
    """

    if chain not in ['source','destination']:
        print( f"Invalid chain: {chain}" )
        return 0

    other_chain = 'destination' if chain == 'source' else 'source'

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
    
    # ------------------------------------------------------------------
    # FIX: Load private key from external file using robust pathing
    # ------------------------------------------------------------------
    # 1. Get the directory of the currently running script (bridge.py)
    script_path = Path(__file__).resolve()
    
    # 2. Key is assumed to be in the same folder as bridge.py
    key_path = script_path.parent / 'secret_key.txt'
    
    # 3. Handle cases where the script might be run from a sub-directory 
    # (e.g., if bridge.py is in a subfolder but the key is in the repo root)
    if not key_path.exists():
        key_path = script_path.parent.parent / 'secret_key.txt'
    
    try:
        if not key_path.exists():
            raise FileNotFoundError("Key file not found in script folder or parent folder.")
        
        with open(key_path, 'r') as f:
            warden_pk = f.read().strip()
            
    except FileNotFoundError as e:
        print(f"ERROR: secret_key.txt not found. Cannot proceed without the private key. (Checked: {key_path})")
        return 0
    except Exception as e:
        print(f"ERROR: Could not read secret_key.txt: {e}")
        return 0

    # ------------------------------------------------------------------
    
    # Connect to both chains
    w3_this = connect_to(chain)
    w3_other = connect_to(other_chain)

    if
