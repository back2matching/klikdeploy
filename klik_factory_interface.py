#!/usr/bin/env python3
"""
Klik Factory Contract Interface
Handles fee claiming and pool interactions
"""

import os
import json
from typing import Optional, Dict, Tuple
from web3 import Web3
from eth_account import Account
import logging
from dotenv import load_dotenv

# Load environment
load_dotenv()

# Configure logging
logger = logging.getLogger(__name__)

# Contract ABIs
FACTORY_ABI = [
    {
        "inputs": [{"name": "tokenId", "type": "uint256"}],
        "name": "collectFees",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "inputs": [{"name": "", "type": "address"}],
        "name": "getPool",
        "outputs": [{"name": "", "type": "address"}],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [{"name": "", "type": "address"}],
        "name": "viewClaimableFees",
        "outputs": [{"name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function"
    }
]

UNISWAP_ROUTER_ABI = [
    {
        "inputs": [
            {"name": "amountOutMin", "type": "uint256"},
            {"name": "path", "type": "address[]"},
            {"name": "to", "type": "address"},
            {"name": "deadline", "type": "uint256"}
        ],
        "name": "swapExactETHForTokens",
        "outputs": [{"name": "amounts", "type": "uint256[]"}],
        "stateMutability": "payable",
        "type": "function"
    }
]

# Contract addresses
KLIK_FACTORY = os.getenv('KLIK_FACTORY_ADDRESS')
UNISWAP_V3_ROUTER = "0xE592427A0AEce92De3Edee1F18E0157C05861564"
WETH_ADDRESS = "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2"
DOK_ADDRESS = "0x69ca61398eCa94D880393522C1Ef5c3D8c058837"
BURN_ADDRESS = "0x000000000000000000000000000000000000dEaD"

class KlikFactoryInterface:
    """Interface for Klik Factory contract interactions"""
    
    def __init__(self):
        self.rpc_url = os.getenv('ALCHEMY_RPC_URL')
        self.private_key = os.getenv('PRIVATE_KEY')
        self.w3 = Web3(Web3.HTTPProvider(self.rpc_url))
        self.account = Account.from_key(self.private_key)
        
        # Initialize contracts
        self.factory = self.w3.eth.contract(address=KLIK_FACTORY, abi=FACTORY_ABI)
        self.router = self.w3.eth.contract(address=UNISWAP_V3_ROUTER, abi=UNISWAP_ROUTER_ABI)
    
    async def get_pool_address(self, token_address: str) -> Optional[str]:
        """Get pool address for a token"""
        try:
            pool_address = self.factory.functions.getPool(token_address).call()
            if pool_address and pool_address != "0x0000000000000000000000000000000000000000":
                return pool_address
            return None
        except Exception as e:
            logger.error(f"Error getting pool address: {e}")
            return None
    
    async def check_claimable_fees(self, pool_address: str) -> float:
        """Check claimable fees from a pool"""
        try:
            # Note: You'll need to check the actual function name in your factory
            # This is a placeholder - adapt to your contract's actual interface
            claimable_wei = self.factory.functions.viewClaimableFees(pool_address).call()
            return float(self.w3.from_wei(claimable_wei, 'ether'))
        except Exception as e:
            logger.error(f"Error checking claimable fees: {e}")
            return 0.0
    
    async def claim_fees_from_pool(self, pool_address: str) -> Optional[str]:
        """Execute fee claim transaction"""
        try:
            # Build transaction
            # Note: You need to determine the tokenId from pool_address
            # This is contract-specific - adjust based on your factory
            token_id = 0  # Placeholder - implement based on your contract
            
            function_call = self.factory.functions.collectFees(token_id)
            
            # Get gas estimate
            gas_estimate = function_call.estimate_gas({
                'from': self.account.address
            })
            
            # Build transaction
            nonce = self.w3.eth.get_transaction_count(self.account.address)
            gas_price = self.w3.eth.gas_price
            
            tx = function_call.build_transaction({
                'from': self.account.address,
                'gas': int(gas_estimate * 1.1),
                'gasPrice': gas_price,
                'nonce': nonce,
                'chainId': self.w3.eth.chain_id
            })
            
            # Sign and send
            signed_tx = self.account.sign_transaction(tx)
            tx_hash = self.w3.eth.send_raw_transaction(signed_tx.rawTransaction)
            
            # Wait for confirmation
            receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash)
            
            if receipt['status'] == 1:
                return tx_hash.hex()
            else:
                logger.error("Fee claim transaction failed")
                return None
                
        except Exception as e:
            logger.error(f"Error claiming fees: {e}")
            return None
    
    async def execute_dok_buyback(self, amount_eth: float, reference_tx: str) -> Dict:
        """Execute DOK buyback and burn"""
        try:
            amount_wei = self.w3.to_wei(amount_eth, 'ether')
            
            # Prepare swap path
            path = [WETH_ADDRESS, DOK_ADDRESS]
            deadline = int(self.w3.eth.get_block('latest')['timestamp']) + 300  # 5 minutes
            
            # Estimate output (with 2% slippage)
            # You'd need to implement proper price fetching here
            min_amount_out = 0  # Implement proper calculation
            
            # Build swap transaction
            function_call = self.router.functions.swapExactETHForTokens(
                min_amount_out,
                path,
                BURN_ADDRESS,  # Send directly to burn address
                deadline
            )
            
            nonce = self.w3.eth.get_transaction_count(self.account.address)
            gas_price = self.w3.eth.gas_price
            
            tx = function_call.build_transaction({
                'from': self.account.address,
                'value': amount_wei,
                'gas': 300000,
                'gasPrice': gas_price,
                'nonce': nonce,
                'chainId': self.w3.eth.chain_id
            })
            
            # Sign and send
            signed_tx = self.account.sign_transaction(tx)
            tx_hash = self.w3.eth.send_raw_transaction(signed_tx.rawTransaction)
            
            # Wait for confirmation
            receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash)
            
            if receipt['status'] == 1:
                # Calculate DOK amount from events (placeholder)
                dok_amount = amount_eth * 3000  # Placeholder - get from events
                
                return {
                    'success': True,
                    'tx_hash': tx_hash.hex(),
                    'dok_amount': dok_amount
                }
            else:
                return {
                    'success': False,
                    'error': 'Transaction failed'
                }
                
        except Exception as e:
            logger.error(f"Buyback failed: {e}")
            return {
                'success': False,
                'error': str(e)
            }

# Singleton instance
factory_interface = KlikFactoryInterface()

# Export the functions for use in telegram bot
async def get_pool_address(token_address: str) -> Optional[str]:
    return await factory_interface.get_pool_address(token_address)

async def check_claimable_fees(pool_address: str) -> float:
    return await factory_interface.check_claimable_fees(pool_address)

async def claim_fees_from_pool(pool_address: str) -> Optional[str]:
    return await factory_interface.claim_fees_from_pool(pool_address)

async def execute_dok_buyback(amount: float, reference_tx: str) -> Dict:
    return await factory_interface.execute_dok_buyback(amount, reference_tx) 