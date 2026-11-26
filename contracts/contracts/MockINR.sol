// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

import "@openzeppelin/contracts/token/ERC20/ERC20.sol";
import "@openzeppelin/contracts/access/Ownable.sol";

contract MockINR is ERC20, Ownable { // test rupee token
    uint256 public constant FAUCET_AMOUNT = 50_000 * 10 ** 18;
    mapping(address => uint256) public lastFaucetRequest;
    uint256 public constant FAUCET_COOLDOWN = 1 hours;

    error FaucetCooldownActive(uint256 remainingSeconds);

    event FaucetDispensed(address indexed recipient, uint256 amount);

    constructor() ERC20("TrustRent Mock INR", "mINR") Ownable(msg.sender) {

        _mint(msg.sender, 10_000_000 * 10 ** 18);
    }

    function requestFaucet() external {
        if (block.timestamp < lastFaucetRequest[msg.sender] + FAUCET_COOLDOWN) {
            revert FaucetCooldownActive((lastFaucetRequest[msg.sender] + FAUCET_COOLDOWN) - block.timestamp);
        }
        lastFaucetRequest[msg.sender] = block.timestamp;
        _mint(msg.sender, FAUCET_AMOUNT);
        emit FaucetDispensed(msg.sender, FAUCET_AMOUNT);
    }

    function mint(address to, uint256 amount) external onlyOwner {
        _mint(to, amount);
    }
}
