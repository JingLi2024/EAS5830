import os
import json
from web3 import Web3
from web3.middleware import geth_poa_middleware
from eth_account import Account
from dotenv import load_dotenv

# -------------------- Config --------------------
load_dotenv()

RPC_URL = os.getenv("RPC_URL", "https://api.avax-test.network/ext/bc/C/rpc")
CHAIN_ID = 43113  # Avalanche Fuji Testnet
CONTRACT_ADDRESS = "0x85ac2e065d4526FBeE6a2253389669a12318A412"

# Your funded Fuji account (keep these secret!)
PRIVATE_KEY = os.environ["PRIVATE_KEY"]
SENDER = os.environ["ADDRESS"]

ABI_FILE = "NFT.abi"  # Provided by Codio

# -------------------- Setup Web3 --------------------
w3 = Web3(Web3.HTTPProvider(RPC_URL))
# Fuji/Testnets often require POA middleware
w3.middleware_onion.inject(geth_poa_middleware, layer=0)

if not w3.is_connected():
    raise RuntimeError("Unable to reach RPC. Check RPC_URL / network connectivity.")

SENDER = Web3.to_checksum_address(SENDER)
acct = Account.from_key(PRIVATE_KEY)
if acct.address.lower() != SENDER.lower():
    raise ValueError("ADDRESS does not match PRIVATE_KEY signer.")

# Load ABI
with open(ABI_FILE, "r") as f:
    ABI = json.load(f)

contract = w3.eth.contract(address=Web3.to_checksum_address(CONTRACT_ADDRESS), abi=ABI)

# -------------------- Helpers --------------------
def safe_call(fn, default=None, *args):
    """Call a contract view fn safely, return default on error."""
    try:
        return fn(*args).call()
    except Exception:
        return default

def token0_exists():
    # Prefer exists(0) if present; fall back to ownerOf(0)
    ex = safe_call(contract.functions.exists, None, 0)
    if ex is not None:
        return bool(ex)
    try:
        contract.functions.ownerOf(0).call()
        return True
    except Exception:
        return False

def find_smallest_existing_token_id():
    """Scan Enumerable extension to find min tokenId (optional)."""
    supply = safe_call(contract.functions.totalSupply, None)
    if not isinstance(supply, int) or supply <= 0:
        return None
    smallest = None
    # This is fine for a few thousand tokens in a script (all view calls)
    for i in range(supply):
        tid = safe_call(contract.functions.tokenByIndex, None, i)
        if tid is None:
            # Not enumerable or read failed — abort
            return None
        if smallest is None or tid < smallest:
            smallest = tid
    return smallest

def get_last_minted_token_id_from_receipt(receipt):
    """
    Parse standard ERC-721 Transfer events to find the mint
    (from == 0x0...0, to == SENDER). Return tokenId or None.
    """
    zero = "0x0000000000000000000000000000000000000000"
    try:
        transfers = contract.events.Transfer().process_receipt(receipt)
    except Exception:
        return None
    for ev in transfers:
        args = ev["args"]
        if args["from"].lower() == zero and args["to"].lower() == SENDER.lower():
            return int(args["tokenId"])
    return None

# -------------------- Pre-mint state --------------------
total_supply_before = safe_call(contract.functions.totalSupply, None)
print("Connected to Fuji ✅")
print("Contract:", CONTRACT_ADDRESS)
print("Your address:", SENDER)
print("totalSupply (before):", total_supply_before)
print("tokenId 0 exists (before)?", token0_exists())

# -------------------- Build & send claim(tx) --------------------
# bytes32 nonce: unique random 32 bytes each attempt
nonce_bytes32 = w3.keccak(os.urandom(32))

tx = contract.functions.claim(SENDER, nonce_bytes32).build_transaction({
    "from": SENDER,
    "nonce": w3.eth.get_transaction_count(SENDER),
    "chainId": CHAIN_ID,
    # EIP-1559 fields (Fuji supports them)
    "maxFeePerGas": w3.to_wei("60", "gwei"),
    "maxPriorityFeePerGas": w3.to_wei("2", "gwei"),
})

# Estimate gas with buffer
try:
    gas_est = w3.eth.estimate_gas(tx)
    tx["gas"] = int(gas_est * 1.2)
except Exception:
    # Fallback gas limit if estimation fails (typical mint fits well below this)
    tx["gas"] = 300_000

signed = w3.eth.account.sign_transaction(tx, private_key=PRIVATE_KEY)
tx_hash = w3.eth.send_raw_transaction(signed.rawTransaction)
print("Submitted claim tx:", tx_hash.hex())

receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
print(f"Mined in block {receipt.blockNumber}, status {receipt.status}")

if receipt.status != 1:
    raise RuntimeError("Transaction failed on-chain.")

# -------------------- Determine minted tokenId --------------------
minted_token_id = get_last_minted_token_id_from_receipt(receipt)

# Fallback: try to infer via totalSupply / tokenByIndex if enumerable
if minted_token_id is None:
    ts_after = safe_call(contract.functions.totalSupply, None)
    if isinstance(ts_after, int) and ts_after and ts_after > 0:
        minted_token_id = safe_call(contract.functions.tokenByIndex, None, ts_after - 1)

print("Your minted tokenId:", minted_token_id)

# -------------------- Post checks --------------------
# Who owns token 0 now (if it exists)?
try:
    owner0 = contract.functions.ownerOf(0).call()
    print("ownerOf(0):", owner0)
except Exception:
    print("ownerOf(0): token 0 does not exist or ownerOf(0) reverted (expected if token 0 was never minted).")

# Optional: smallest existing tokenId on-chain (if enumerable)
smallest_existing = find_smallest_existing_token_id()
print("Smallest existing tokenId (scan):", smallest_existing)
