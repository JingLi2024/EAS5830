import eth_account
import random
import string
import json
from pathlib import Path
from web3 import Web3
from web3.middleware import ExtraDataToPOAMiddleware  # Necessary for POA chains


def merkle_assignment():
    """
        The only modifications you need to make to this method are to assign
        your "random_leaf_index" and uncomment the last line when you are
        ready to attempt to claim a prime. You will need to complete the
        methods called by this method to generate the proof.
    """
    # Generate the list of primes as integers
    num_of_primes = 8192
    primes = generate_primes(num_of_primes)

    # Create a version of the list of primes in bytes32 format
    leaves = convert_leaves(primes)

    # Build a Merkle tree using the bytes32 leaves as the Merkle tree's leaves
    tree = build_merkle(leaves)

    # Select a random leaf and create a proof for that leaf
    random_leaf_index = random.randint(1, num_of_primes - 1) #TODO generate a random index from primes to claim (0 is already claimed)
    proof = prove_merkle(tree, random_leaf_index)

    # This is the same way the grader generates a challenge for sign_challenge()
    challenge = ''.join(random.choice(string.ascii_letters) for i in range(32))
    # Sign the challenge to prove to the grader you hold the account
    addr, sig = sign_challenge(challenge)

    if sign_challenge_verify(challenge, addr, sig):
        tx_hash = '0x'
        # TODO, when you are ready to attempt to claim a prime (and pay gas fees),
        #  complete this method and run your code with the following line un-commented
        # tx_hash = send_signed_msg(proof, leaves[random_leaf_index])
        tx_hash = send_signed_msg(proof, leaves[random_leaf_index])
        print("Claim submitted!")
        print("Your address:", addr)
        print("Chosen index:", random_leaf_index)
        print("Prime (int):", primes[random_leaf_index])
        print("Leaf (bytes32):", leaves[random_leaf_index].hex())
        print("Proof length:", len(proof))
        print("Tx hash:", tx_hash)


def generate_primes(num_primes):
    """
        Function to generate the first 'num_primes' prime numbers
        returns list (with length n) of primes (as ints) in ascending order
    """
    primes_list = []

    #TODO YOUR CODE HERE
    import math

    if num_primes <= 0:
        return []

    # Upper bound estimate for the nth prime: n(ln n + ln ln n) + 10  for n >= 6
    if num_primes < 6:
        bound = 15
    else:
        n = num_primes
        bound = int(n * (math.log(n) + math.log(math.log(n))) + 10)

    def sieve(limit: int):
        # Sieve of Eratosthenes
        is_prime = bytearray(b'\x01') * (limit + 1)
        if limit >= 0:
            is_prime[0] = 0
        if limit >= 1:
            is_prime[1] = 0
        p = 2
        while p * p <= limit:
            if is_prime[p]:
                start = p * p
                step = p
                is_prime[start:limit + 1:step] = b'\x00' * (((limit - start) // step) + 1)
            p += 1
        return [i for i in range(limit + 1) if is_prime[i]]

    primes = sieve(bound)
    while len(primes) < num_primes:
        bound *= 2
        primes = sieve(bound)

    primes_list = primes[:num_primes]

    return primes_list


def convert_leaves(primes_list):
    """
        Converts the leaves (primes_list) to bytes32 format
        returns list of primes where list entries are bytes32 encodings of primes_list entries
    """

    # TODO YOUR CODE HERE

    # Each prime as 32-byte big-endian (no hashing at the leaf level).
    leaves = [int(p).to_bytes(32, 'big') for p in primes_list]

    return leaves

def build_merkle(leaves):
    """
        Function to build a Merkle Tree from the list of prime numbers in bytes32 format
        Returns the Merkle tree (tree) as a list where tree[0] is the list of leaves,
        tree[1] is the parent hashes, and so on until tree[n] which is the root hash
        the root hash produced by the "hash_pair" helper function
    """

    #TODO YOUR CODE HERE
    # Build successive levels by hashing sorted pairs via hash_pair().
    if not leaves:
        levels = [[]]
    else:
        level = list(leaves)
        levels = [level]
        while len(level) > 1:
            # If odd number of nodes, duplicate the last (defensive).
            if len(level) % 2 == 1:
                level = level + [level[-1]]
            next_level = []
            for i in range(0, len(level), 2):
                next_level.append(hash_pair(level[i], level[i + 1]))
            level = next_level
            levels.append(level)

    tree = []
    tree.extend(levels)

    return tree


def prove_merkle(merkle_tree, random_indx):
    """
        Takes a random_index to create a proof of inclusion for and a complete Merkle tree
        as a list of lists where index 0 is the list of leaves, index 1 is the list of
        parent hash values, up to index -1 which is the list of the root hash.
        returns a proof of inclusion as list of values
    """
    merkle_proof = []
    # TODO YOUR CODE HERE
    idx = random_indx
    # For each level except the root, append the sibling node.
    for lvl in range(0, len(merkle_tree) - 1):
        nodes = merkle_tree[lvl]
        # sibling index is idx ^ 1 (flip last bit)
        sib_idx = idx ^ 1
        # Defensive for odd-length duplication case
        if sib_idx >= len(nodes):
            sib_idx = len(nodes) - 1
        merkle_proof.append(nodes[sib_idx])
        idx //= 2

    return merkle_proof


def sign_challenge(challenge):
    """
        Takes a challenge (string)
        Returns address, sig
        where address is an ethereum address and sig is a signature (in hex)
        This method is to allow the auto-grader to verify that you have
        claimed a prime
    """
    acct = get_account()

    addr = acct.address
    eth_sk = acct.key

    # TODO YOUR CODE HERE
    # Correct signing per EIP-191 / OpenZeppelin's verify
    from eth_account.messages import encode_defunct
    msg = encode_defunct(text=challenge)
    eth_sig_obj = eth_account.Account.sign_message(msg, private_key=eth_sk)

    # Strip leading '0x' if present to avoid “Non-hexadecimal digit found” error
    if isinstance(eth_sig_obj.signature, (bytes, bytearray)):
        # convert bytes to hex string without '0x'
        sig_hex = eth_sig_obj.signature.hex()
    else:
        # handle if signature is already a string with 0x
        sig_hex = str(eth_sig_obj.signature)
        if sig_hex.startswith("0x"):
            sig_hex = sig_hex[2:]
        # convert back to bytes to make .hex() work safely
        sig_hex = bytes.fromhex(sig_hex).hex()

    # Reassign the sanitized signature to the object before returning
    eth_sig_obj.signature = bytes.fromhex(sig_hex)

    return addr, eth_sig_obj.signature.hex()


def send_signed_msg(proof, random_leaf):
    """
        Takes a Merkle proof of a leaf, and that leaf (in bytes32 format)
        builds signs and sends a transaction claiming that leaf (prime)
        on the contract
    """
    chain = 'bsc'

    acct = get_account()
    address, abi = get_contract_info(chain)
    w3 = connect_to(chain)

    # TODO YOUR CODE HERE
    contract = w3.eth.contract(address=Web3.to_checksum_address(address), abi=abi)

    # Build transaction to call submit(bytes32[] proof, bytes32 leaf)
    tx = contract.functions.submit(proof, random_leaf).build_transaction({
        "from": acct.address,
        "nonce": w3.eth.get_transaction_count(acct.address),
        "chainId": w3.eth.chain_id,
        "gasPrice": w3.eth.gas_price,
    })

    # Estimate gas with a small buffer; fall back if estimation fails
    try:
        gas_est = w3.eth.estimate_gas(tx)
        tx["gas"] = int(gas_est * 1.2)
    except Exception:
        tx["gas"] = 300000

    signed = w3.eth.account.sign_transaction(tx, private_key=acct.key)
    tx_hash = w3.eth.send_raw_transaction(signed.rawTransaction).hex()


    return tx_hash


# Helper functions that do not need to be modified
def connect_to(chain):
    """
        Takes a chain ('avax' or 'bsc') and returns a web3 instance
        connected to that chain.
    """
    if chain not in ['avax','bsc']:
        print(f"{chain} is not a valid option for 'connect_to()'")
        return None
    if chain == 'avax':
        api_url = f"https://api.avax-test.network/ext/bc/C/rpc"  # AVAX C-chain testnet
    else:
        api_url = f"https://data-seed-prebsc-1-s1.binance.org:8545/"  # BSC testnet
    w3 = Web3(Web3.HTTPProvider(api_url))
    # inject the poa compatibility middleware to the innermost layer
    w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)

    return w3


def get_account():
    """
        Returns an account object recovered from the secret key
        in "sk.txt"
    """
    cur_dir = Path(__file__).parent.absolute()
    with open(cur_dir.joinpath('sk.txt'), 'r') as f:
        sk = f.readline().rstrip()
    if sk[0:2] == "0x":
        sk = sk[2:]
    return eth_account.Account.from_key(sk)


def get_contract_info(chain):
    """
        Returns a contract address and contract abi from "contract_info.json"
        for the given chain
    """
    contract_file = Path(__file__).parent.absolute() / "contract_info.json"
    if not contract_file.is_file():
        contract_file = Path(__file__).parent.parent.parent / "tests" / "contract_info.json"
    with open(contract_file, "r") as f:
        d = json.load(f)
        d = d[chain]
    return d['address'], d['abi']


def sign_challenge_verify(challenge, addr, sig):
    """
        Helper to verify signatures, verifies sign_challenge(challenge)
        the same way the grader will. No changes are needed for this method
    """
    eth_encoded_msg = eth_account.messages.encode_defunct(text=challenge)

    if eth_account.Account.recover_message(eth_encoded_msg, signature=sig) == addr:
        print(f"Success: signed the challenge {challenge} using address {addr}!")
        return True
    else:
        print(f"Failure: The signature does not verify!")
        print(f"signature = {sig}\naddress = {addr}\nchallenge = {challenge}")
        return False


def hash_pair(a, b):
    """
        The OpenZeppelin Merkle Tree Validator we use sorts the leaves
        https://github.com/OpenZeppelin/openzeppelin-contracts/blob/master/contracts/utils/cryptography/MerkleProof.sol#L217
        So you must sort the leaves as well

        Also, hash functions like keccak are very sensitive to input encoding, so the solidity_keccak function is the function to use

        Another potential gotcha, if you have a prime number (as an int) bytes(prime) will *not* give you the byte representation of the integer prime
        Instead, you must call int.to_bytes(prime,'big').
    """
    if a < b:
        return Web3.solidity_keccak(['bytes32', 'bytes32'], [a, b])
    else:
        return Web3.solidity_keccak(['bytes32', 'bytes32'], [b, a])


if __name__ == "__main__":
    merkle_assignment()
