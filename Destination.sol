// SPDX-License-Identifier: MIT
pragma solidity ^0.8.17;

import "@openzeppelin/contracts/token/ERC20/ERC20.sol";
import "@openzeppelin/contracts/access/AccessControl.sol";
import "./BridgeToken.sol";

contract Destination is AccessControl {
    bytes32 public constant WARDEN_ROLE = keccak256("BRIDGE_WARDEN_ROLE");
    bytes32 public constant CREATOR_ROLE = keccak256("CREATOR_ROLE");
	mapping( address => address) public underlying_tokens;
	mapping( address => address) public wrapped_tokens;
	address[] public tokens;

	event Creation( address indexed underlying_token, address indexed wrapped_token );
	event Wrap( address indexed underlying_token, address indexed wrapped_token, address indexed to, uint256 amount );
	event Unwrap( address indexed underlying_token, address indexed wrapped_token, address frm, address indexed to, uint256 amount );

    constructor( address admin ) {
        _grantRole(DEFAULT_ADMIN_ROLE, admin);
        _grantRole(CREATOR_ROLE, admin);
        _grantRole(WARDEN_ROLE, admin);
    }

	function wrap(address _underlying_token, address _recipient, uint256 _amount ) public onlyRole(WARDEN_ROLE) {
		//YOUR CODE HERE
		  // Ensure the underlying is registered and get the wrapped token
    address wrapped = underlying_tokens[_underlying_token];
    require(wrapped != address(0), "Underlying not registered");

    // Mint to recipient (amount may be zero; OZ ERC20 handles 0 safely)
    BridgeToken(wrapped).mint(_recipient, _amount);

    emit Wrap(_underlying_token, wrapped, _recipient, _amount);
}

	function unwrap(address _wrapped_token, address _recipient, uint256 _amount ) public {
		//YOUR CODE HERE
		// Ensure this wrapped token is one we registered
    address underlying = wrapped_tokens[_wrapped_token];
    require(underlying != address(0), "Wrapped token not recognized");

    // Burn caller's tokens. Since this contract has MINTER_ROLE on the BridgeToken
    // it may burn without allowance; ERC20 will still enforce sufficient balance.
    BridgeToken(_wrapped_token).burnFrom(msg.sender, _amount);

    emit Unwrap(underlying, _wrapped_token, msg.sender, _recipient, _amount);
	}

	function createToken(address _underlying_token, string memory name, string memory symbol ) public onlyRole(CREATOR_ROLE) returns(address) {
		//YOUR CODE HERE
	  require(_underlying_token != address(0), "Invalid underlying");
    require(underlying_tokens[_underlying_token] == address(0), "Already registered");

    // Make this Destination contract the admin/minter on the BridgeToken
    BridgeToken token = new BridgeToken(_underlying_token, name, symbol, address(this));
    address wrapped = address(token);

    // Register mappings in both directions and track the new token
    underlying_tokens[_underlying_token] = wrapped;
    wrapped_tokens[wrapped] = _underlying_token;
    tokens.push(wrapped);

    emit Creation(_underlying_token, wrapped);
    return wrapped;
	}

}


