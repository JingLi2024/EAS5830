import random
import json
from web3 import Web3
from web3.middleware import ExtraDataToPOAMiddleware
from web3.providers.rpc import HTTPProvider


# If you use one of the suggested infrastructure providers, the url will be of the form
# now_url  = f"https://eth.nownodes.io/{now_token}"
# alchemy_url = f"https://eth-mainnet.alchemyapi.io/v2/{alchemy_token}"
# infura_url = f"https://mainnet.infura.io/v3/{infura_token}"

def connect_to_eth():
	# TODO insert your code for this method from last week's assignment
	url = "https://mainnet.infura.io/v3/198ba796b8a548cbb6b4ce669df25a6e"  # FILL THIS IN
	w3 = Web3(HTTPProvider(url))
	assert w3.is_connected(), f"Failed to connect to provider at {url}"
	return w3


def connect_with_middleware(contract_json):
	# TODO insert your code for this method from last week's assignment
	with open(contract_json, "r") as f:
		d = json.load(f)
		d = d['bsc']
		address = d['address']
		abi = d['abi']

	bnb_testnet_url = "https://bsc-testnet.infura.io/v3/198ba796b8a548cbb6b4ce669df25a6e"
	w3 = Web3(HTTPProvider(bnb_testnet_url))
	assert w3.is_connected(), f"Failed to connect to BNB testnet provider at {bnb_testnet_url}"
	return w3, contract


def is_ordered_block(w3, block_num):
	"""
	Takes a block number
	Returns a boolean that tells whether all the transactions in the block are ordered by priority fee

	Before EIP-1559, a block is ordered if and only if all transactions are sorted in decreasing order of the gasPrice field

	After EIP-1559, there are two types of transactions
		*Type 0* The priority fee is tx.gasPrice - block.baseFeePerGas
		*Type 2* The priority fee is min( tx.maxPriorityFeePerGas, tx.maxFeePerGas - block.baseFeePerGas )

	Conveniently, most type 2 transactions set the gasPrice field to be min( tx.maxPriorityFeePerGas + block.baseFeePerGas, tx.maxFeePerGas )
	"""
	block = w3.eth.get_block(block_num, full_transactions=True)
	ordered = False

	# TODO YOUR CODE HERE
  def _get(tx, key):
		try:
			if isinstance(tx, dict):
				val = tx.get(key)
			else:
				val = getattr(tx, key, None)
			return int(val) if val is not None else None
		except Exception:
			return None

	base_fee = block.get('baseFeePerGas', None)
	txs = block.get('transactions', [])

	# Always call get_transaction() for each tx as required
	full_txs = []
	for tx in txs:
		tx_hash = None
		if isinstance(tx, dict):
			tx_hash = tx.get('hash')
		else:
			tx_hash = getattr(tx, 'hash', None)
		try:
			if tx_hash is not None:
				full_txs.append(w3.eth.get_transaction(tx_hash))
			else:
				full_txs.append(tx)  # fallback
		except Exception:
			full_txs.append(tx)  # fallback if provider can’t refetch

	txs = full_txs

	# 0 or 1 transaction => trivially ordered
	if len(txs) <= 1:
		ordered = True
	else:
		def is_nonincreasing(seq):
			prev = None
			for x in seq:
				if prev is not None and x > prev:
					return False
				prev = x
			return True

		# Pre-EIP-1559: order by gasPrice only
		if base_fee is None:
			gps = [(_get(tx, 'gasPrice') or 0) for tx in txs]
			ordered = is_nonincreasing(gps)
		else:
			base_fee = int(base_fee)
			all_have_gasprice = all(_get(tx, 'gasPrice') is not None for tx in txs)

			if all_have_gasprice:
				gps = [_get(tx, 'gasPrice') for tx in txs]
				ordered = is_nonincreasing(gps)
			else:
				# Compute effective priority fee per gas for each tx
				def tip(tx):
					mp = _get(tx, 'maxPriorityFeePerGas')
					mf = _get(tx, 'maxFeePerGas')
					gp = _get(tx, 'gasPrice')

					# Type 2 if maxPriorityFeePerGas present (even if gasPrice exists)
					if mp is not None:
						if mf is not None:
							return min(mp, max(mf - base_fee, 0))
						return max(mp, 0)

					# Legacy type 0: priority = gasPrice - baseFee
					if gp is not None:
						return max(gp - base_fee, 0)

					# Missing fields => treat as 0
					return 0

				tips = [tip(tx) for tx in txs]
				ordered = is_nonincreasing(tips)

	return ordered


def get_contract_values(contract, admin_address, owner_address):
	"""
	Takes a contract object, and two addresses (as strings) to be used for calling
	the contract to check current on chain values.
	The provided "default_admin_role" is the correctly formatted solidity default
	admin value to use when checking with the contract
	To complete this method you need to make three calls to the contract to get:
	  onchain_root: Get and return the merkleRoot from the provided contract
	  has_role: Verify that the address "admin_address" has the role "default_admin_role" return True/False
	  prime: Call the contract to get and return the prime owned by "owner_address"

	check on available contract functions and transactions on the block explorer at
	https://testnet.bscscan.com/address/0xaA7CAaDA823300D18D3c43f65569a47e78220073
	"""
	default_admin_role = int.to_bytes(0, 32, byteorder="big")

	# TODO complete the following lines by performing contract calls
	onchain_root = contract.functions.merkleRoot().call()  # Get and return the merkleRoot from the provided contract
  # role key (prefer reading from contract; fall back to provided zero-bytes default)
	try:
		role_key = contract.functions.DEFAULT_ADMIN_ROLE().call()
	except Exception:
		role_key = default_admin_role
	has_role = contract.functions.hasRole(role_key, Web3.to_checksum_address(admin_address)).call()  # Check the contract to see if the address "admin_address" has the role "default_admin_role"
	prime = contract.functions.getPrimeByOwner(Web3.to_checksum_address(owner_address)).call()  # Call the contract to get the prime owned by "owner_address"

	return onchain_root, has_role, prime


"""
	This might be useful for testing (main is not run by the grader feel free to change 
	this code anyway that is helpful)
"""
if __name__ == "__main__":
	# These are addresses associated with the Merkle contract (check on contract
	# functions and transactions on the block explorer at
	# https://testnet.bscscan.com/address/0xaA7CAaDA823300D18D3c43f65569a47e78220073
	admin_address = "0xAC55e7d73A792fE1A9e051BDF4A010c33962809A"
	owner_address = "0x793A37a85964D96ACD6368777c7C7050F05b11dE"
	contract_file = "contract_info.json"

	eth_w3 = connect_to_eth()
	cont_w3, contract = connect_with_middleware(contract_file)

	latest_block = eth_w3.eth.get_block_number()
	london_hard_fork_block_num = 12965000
	assert latest_block > london_hard_fork_block_num, f"Error: the chain never got past the London Hard Fork"

	n = 5
	for _ in range(n):
		block_num = random.randint(1, latest_block)
		ordered = is_ordered_block(block_num)
		if ordered:
			print(f"Block {block_num} is ordered")
		else:
			print(f"Block {block_num} is not ordered")
