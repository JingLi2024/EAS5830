from web3 import Web3
from eth_account.messages import encode_defunct
import eth_account
import os

def sign_message(challenge, filename="secret_key.txt"):
    """
    challenge - byte string
    filename - filename of the file that contains your account secret key
    To pass the tests, your signature must verify, and the account you use
    must have testnet funds on both the bsc and avalanche test networks.
    """
    # This code will read your "sk.txt" file
    # If the file is empty, it will raise an exception
    with open(filename, "r") as f:
        key = f.readlines()
    assert(len(key) > 0), "Your account secret_key.txt is empty"

    w3 = Web3()
    message = encode_defunct(challenge)

    # TODO recover your account information for your private key and sign the given challenge
    # Use the code from the signatures assignment to sign the given challenge
    priv_key = key[0].strip()
    if not priv_key.startswith("0x"):
        priv_key = "0x" + priv_key

    # Recover account info
    account_object = eth_account.Account.from_key(priv_key)        # using existing key
    eth_addr = account_object.address                              # public key / address
    private_key = account_object.key                               # private key bytes

    # Sign the given challenge
    signed_message = w3.eth.account.sign_message(message, private_key=private_key)





    assert eth_account.Account.recover_message(message,signature=signed_message.signature.hex()) == eth_addr, f"Failed to sign message properly"

    #return signed_message, account associated with the private key
    return signed_message, eth_addr


if __name__ == "__main__":
    for i in range(4):
        challenge = os.urandom(64)
        sig, addr= sign_message(challenge=challenge)
        print( addr )
