from web3 import Web3
from web3.providers.rpc import HTTPProvider
import requests
import json

bayc_address = "0xBC4CA0EdA7647A8aB7C2061c2E118A18a936f13D"
contract_address = Web3.to_checksum_address(bayc_address)

# You will need the ABI to connect to the contract
# The file 'abi.json' has the ABI for the bored ape contract
# In general, you can get contract ABIs from etherscan
# https://api.etherscan.io/api?module=contract&action=getabi&address=0xBC4CA0EdA7647A8aB7C2061c2E118A18a936f13D
with open('ape_abi.json', 'r') as f:
    abi = json.load(f)

############################
# Connect to an Ethereum node
api_url = "https://mainnet.infura.io/v3/198ba796b8a548cbb6b4ce669df25a6e"  # YOU WILL NEED TO PROVIDE THE URL OF AN ETHEREUM NODE
provider = HTTPProvider(api_url)
web3 = Web3(provider)


# Convert IPFS → HTTP
PINATA_GATEWAY = "https://silver-passive-dove-978.mypinata.cloud/ipfs/"
PUBLIC_PINATA  = "https://gateway.pinata.cloud/ipfs/"

def _ipfs_to_http(uri: str, gateway: str = PINATA_GATEWAY) -> str:
    """
    Convert an IPFS URI like 'ipfs://CID/path' to an HTTP URL for a gateway.
    Ensures correct prefix and handles a few common variants.
    """
    if not isinstance(uri, str):
        return uri

    if uri.startswith("ipfs://"):
        path = uri[len("ipfs://"):]
    elif uri.startswith("/ipfs/"):
        path = uri[len("/ipfs/"):]
    else:
        # Already an http(s) URL or an unexpected format; return as-is
        return uri

    if not gateway.endswith("/"):
        gateway += "/"
    # Ensure gateway ends with .../ipfs/
    if not gateway.rstrip("/").endswith("/ipfs"):
        gateway = gateway.rstrip("/") + "/ipfs/"
    return gateway + path

def get_ape_info(ape_id):
    assert isinstance(ape_id, int), f"{ape_id} is not an int"
    assert 0 <= ape_id, f"{ape_id} must be at least 0"
    assert 9999 >= ape_id, f"{ape_id} must be less than 10,000"

    data = {'owner': "", 'image': "", 'eyes': ""}

    # Instantiate the contract
    contract = web3.eth.contract(address=contract_address, abi=abi)

    # 1) On-chain: owner + tokenURI
    owner_addr = contract.functions.ownerOf(ape_id).call()
    token_uri = contract.functions.tokenURI(ape_id).call()

    # 2) Off-chain: fetch metadata JSON from IPFS via Pinata gateway
    metadata_url = _ipfs_to_http(token_uri, gateway=PINATA_GATEWAY)
    try:
        resp = requests.get(metadata_url, timeout=20)
        resp.raise_for_status()
    except Exception:
        # Fallback to public Pinata gateway if custom gateway hiccups
        metadata_url = _ipfs_to_http(token_uri, gateway=PUBLIC_PINATA)
        resp = requests.get(metadata_url, timeout=20)
        resp.raise_for_status()

    meta = resp.json()

    # Pull fields from metadata
    image_uri = meta.get("image", "")
    eyes_value = ""

    # Standard BAYC metadata uses attributes: [{trait_type: "...", value: "..."}]
    attrs = meta.get("attributes") or meta.get("traits") or []
    for attr in attrs:
        if isinstance(attr, dict) and attr.get("trait_type", "").lower() == "eyes":
            eyes_value = attr.get("value", "")
            break

    data['owner'] = Web3.to_checksum_address(owner_addr)
    data['image'] = image_uri              # keep as ipfs:// 
    data['eyes']  = eyes_value

    assert isinstance(data, dict), f'get_ape_info{ape_id} should return a dict'
    assert all([a in data.keys() for a in
                ['owner', 'image', 'eyes']]), f"return value should include the keys 'owner','image' and 'eyes'"
    return data
