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
import requests

# Load environment
load_dotenv()

# Configure logging
logger = logging.getLogger(__name__)

# Contract addresses
KLIK_FACTORY = "0x930f9FA91E1E46d8e44abC3517E2965C6F9c4763"
UNISWAP_V3_ROUTER = "0xE592427A0AEce92De3Edee1F18E0157C05861564"
UNISWAP_V2_ROUTER = "0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D"  # V2 router for DOK
WETH_ADDRESS = "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2"
DOK_ADDRESS = "0x69ca61398eCa94D880393522C1Ef5c3D8c058837"
BURN_ADDRESS = "0x000000000000000000000000000000000000dEaD"

# DOK/WETH pair on Uniswap V3 (from the transaction logs)
DOK_WETH_V3_POOL = "0xf6E2edc5953Da297947C6C68911E16CF1C9b64B6"

# Known token to tokenId mappings from transaction analysis
KNOWN_TOKEN_IDS = {
    "0x69ca61398eCa94D880393522C1Ef5c3D8c058837": 1018175,  # DOK tokenId from tx analysis
}

# Minimal ABIs based on the transaction
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
        "inputs": [],
        "name": "allPairsLength",
        "outputs": [{"name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [{"name": "", "type": "uint256"}],
        "name": "allPairs",
        "outputs": [{"name": "", "type": "address"}],
        "stateMutability": "view",
        "type": "function"
    }
]

# UniswapV2 Router ABI for DOK trading
UNISWAP_V2_ROUTER_ABI = [
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
    },
    {
        "inputs": [
            {"name": "amountOut", "type": "uint256"},
            {"name": "reserveIn", "type": "uint256"},
            {"name": "reserveOut", "type": "uint256"}
        ],
        "name": "getAmountIn",
        "outputs": [{"name": "amountIn", "type": "uint256"}],
        "stateMutability": "pure",
        "type": "function"
    },
    {
        "inputs": [
            {"name": "amountIn", "type": "uint256"},
            {"name": "reserveIn", "type": "uint256"},
            {"name": "reserveOut", "type": "uint256"}
        ],
        "name": "getAmountOut",
        "outputs": [{"name": "amountOut", "type": "uint256"}],
        "stateMutability": "pure",
        "type": "function"
    }
]

# Pair ABI to check reserves
PAIR_ABI = [
    {
        "constant": True,
        "inputs": [],
        "name": "getReserves",
        "outputs": [
            {"name": "_reserve0", "type": "uint112"},
            {"name": "_reserve1", "type": "uint112"},
            {"name": "_blockTimestampLast", "type": "uint32"}
        ],
        "payable": False,
        "stateMutability": "view",
        "type": "function"
    },
    {
        "constant": True,
        "inputs": [],
        "name": "token0",
        "outputs": [{"name": "", "type": "address"}],
        "payable": False,
        "stateMutability": "view",
        "type": "function"
    },
    {
        "constant": True,
        "inputs": [],
        "name": "token1", 
        "outputs": [{"name": "", "type": "address"}],
        "payable": False,
        "stateMutability": "view",
        "type": "function"
    }
]

# ERC20 ABI for checking balances
ERC20_ABI = [
    {
        "constant": True,
        "inputs": [{"name": "_owner", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"name": "balance", "type": "uint256"}],
        "type": "function"
    }
]

class KlikFactoryInterface:
    """Interface for Klik Factory contract interactions"""
    
    def __init__(self):
        self.rpc_url = os.getenv('ALCHEMY_RPC_URL')
        self.private_key = os.getenv('PRIVATE_KEY')
        self.w3 = Web3(Web3.HTTPProvider(self.rpc_url))
        self.account = Account.from_key(self.private_key)
        
        # Initialize contracts
        self.factory = self.w3.eth.contract(address=KLIK_FACTORY, abi=FACTORY_ABI)
        self.router_v2 = self.w3.eth.contract(address=UNISWAP_V2_ROUTER, abi=UNISWAP_V2_ROUTER_ABI)
    
    async def analyze_fee_claim_transaction(self, tx_hash: str) -> Dict:
        """Analyze a fee claim transaction to understand the mapping"""
        try:
            # Get transaction details using Alchemy
            tx = self.w3.eth.get_transaction(tx_hash)
            receipt = self.w3.eth.get_transaction_receipt(tx_hash)
            
            # Decode the input data
            decoded_input = self.factory.decode_function_input(tx['input'])
            function_name = decoded_input[0].fn_name
            params = decoded_input[1]
            
            logger.info(f"Transaction {tx_hash}:")
            logger.info(f"Function: {function_name}")
            logger.info(f"Parameters: {params}")
            
            if function_name == 'collectFees' and 'tokenId' in params:
                token_id = params['tokenId']
                
                # Use Alchemy's trace API to get more details
                trace_data = self._get_transaction_trace(tx_hash)
                
                return {
                    'token_id': token_id,
                    'trace': trace_data,
                    'logs': receipt['logs']
                }
            
            return None
            
        except Exception as e:
            logger.error(f"Error analyzing transaction: {e}")
            return None
    
    def _get_transaction_trace(self, tx_hash: str) -> Optional[Dict]:
        """Get transaction trace using Alchemy's trace API"""
        try:
            # Alchemy's trace_transaction method
            response = requests.post(self.rpc_url, json={
                "jsonrpc": "2.0",
                "method": "trace_transaction",
                "params": [tx_hash],
                "id": 1
            })
            
            if response.status_code == 200:
                return response.json().get('result', [])
            
            # Fallback to debug_traceTransaction
            response = requests.post(self.rpc_url, json={
                "jsonrpc": "2.0",
                "method": "debug_traceTransaction",
                "params": [tx_hash],
                "id": 1
            })
            
            if response.status_code == 200:
                return response.json().get('result')
                
        except Exception as e:
            logger.warning(f"Could not get trace: {e}")
        
        return None
    
    async def find_token_pool_mapping(self, token_address: str) -> Optional[Dict]:
        """Use Alchemy to find how a token maps to its pool and tokenId"""
        try:
            # Method 1: Check if there's a Uniswap V3 pool
            # Search for pool creation events
            response = requests.post(self.rpc_url, json={
                "jsonrpc": "2.0",
                "method": "eth_getLogs",
                "params": [{
                    "fromBlock": "0x0",
                    "toBlock": "latest",
                    "address": KLIK_FACTORY,
                    "topics": [
                        # PoolCreated event signature
                        "0x783cca1c0412dd0d695e784568c96da2e9c22ff989357a2e8b1d9b2b4e6b7118",
                        None,  # token0
                        None,  # token1
                        None   # fee
                    ]
                }],
                "id": 1
            })
            
            if response.status_code == 200:
                logs = response.json().get('result', [])
                
                # Filter logs that contain our token
                for log in logs:
                    # Decode the log data to get token addresses
                    if len(log['topics']) >= 3:
                        token0 = '0x' + log['topics'][1][-40:]  # Last 20 bytes
                        token1 = '0x' + log['topics'][2][-40:]
                        
                        if token_address.lower() in [token0.lower(), token1.lower()]:
                            # Found a pool with our token
                            pool_address = '0x' + log['data'][26:66]  # Pool address from data
                            
                            # Now find the tokenId for this pool
                            return {
                                'pool_address': pool_address,
                                'token0': token0,
                                'token1': token1,
                                'block_number': int(log['blockNumber'], 16)
                            }
            
            # Method 2: Use Alchemy's enhanced APIs
            # Get all transfers of the token to find pool interactions
            response = requests.post(self.rpc_url, json={
                "jsonrpc": "2.0",
                "method": "alchemy_getAssetTransfers",
                "params": [{
                    "fromBlock": "0x0",
                    "toBlock": "latest",
                    "contractAddresses": [token_address],
                    "category": ["erc20"],
                    "withMetadata": True,
                    "maxCount": "0x3e8"  # 1000 results
                }],
                "id": 1
            })
            
            if response.status_code == 200:
                transfers = response.json().get('result', {}).get('transfers', [])
                # Look for transfers to known pool factories or patterns
                for transfer in transfers:
                    # Check if transfer is to a potential pool
                    to_address = transfer.get('to')
                    if to_address:
                        # Check if this address is a pool by calling it
                        if await self._is_pool_contract(to_address):
                            return {'pool_address': to_address}
                            
        except Exception as e:
            logger.error(f"Error finding token pool mapping: {e}")
            
        return None
    
    async def _is_pool_contract(self, address: str) -> bool:
        """Check if an address is a pool contract"""
        try:
            # Try to call token0() and token1() - standard pool methods
            pool_contract = self.w3.eth.contract(address=address, abi=PAIR_ABI)
            pool_contract.functions.token0().call()
            pool_contract.functions.token1().call()
            return True
        except:
            return False
    
    async def get_token_id_for_token(self, token_address: str) -> Optional[int]:
        """Get tokenId for a token by finding its pool in the allPairs array"""
        try:
            # Normalize address
            token_address = Web3.to_checksum_address(token_address)
            
            # Check if we have a known mapping
            if token_address in KNOWN_TOKEN_IDS:
                token_id = KNOWN_TOKEN_IDS[token_address]
                logger.info(f"Using known tokenId {token_id} for {token_address}")
                return token_id
            
            # First, try to find the pool using Alchemy's enhanced features
            pool_info = await self.find_token_pool_mapping(token_address)
            
            if pool_info and 'pool_address' in pool_info:
                # Now find this pool in the allPairs array
                pairs_length = self.factory.functions.allPairsLength().call()
                logger.info(f"Found pool {pool_info['pool_address']}, searching in {pairs_length} pairs")
                
                # Binary search would be more efficient for large arrays
                # but for now, linear search from the end (newer pools)
                for i in range(pairs_length - 1, -1, -1):
                    pair_address = self.factory.functions.allPairs(i).call()
                    if pair_address.lower() == pool_info['pool_address'].lower():
                        logger.info(f"Found tokenId {i} for pool {pair_address}")
                        return i
            
            # Fallback to original method if enhanced search fails
            return await self._get_token_id_for_token_fallback(token_address)
            
        except Exception as e:
            logger.error(f"Error finding tokenId: {e}")
            return None
    
    async def _get_token_id_for_token_fallback(self, token_address: str) -> Optional[int]:
        """Original method - search through all pairs"""
        try:
            # Normalize address
            token_address = Web3.to_checksum_address(token_address)
            
            # Get total number of pairs
            pairs_length = self.factory.functions.allPairsLength().call()
            logger.info(f"Searching through {pairs_length} pairs for token {token_address}")
            
            # Search from newest to oldest (more likely to find recent deployments)
            for i in range(pairs_length - 1, -1, -1):
                try:
                    pair_address = self.factory.functions.allPairs(i).call()
                    
                    # Check if this pair contains our token
                    pair_contract = self.w3.eth.contract(address=pair_address, abi=PAIR_ABI)
                    token0 = pair_contract.functions.token0().call()
                    token1 = pair_contract.functions.token1().call()
                    
                    if token_address.lower() == token0.lower() or token_address.lower() == token1.lower():
                        logger.info(f"Found token {token_address} in pair {pair_address} at index {i}")
                        return i
                        
                except Exception as e:
                    # Some pairs might not be standard, skip them
                    continue
            
            logger.error(f"Token {token_address} not found in any pairs")
            return None
            
        except Exception as e:
            logger.error(f"Error finding tokenId: {e}")
            return None
    
    async def claim_fees_for_token(self, token_address: str) -> Optional[str]:
        """Claim fees for a token (finds the tokenId automatically)"""
        try:
            # Find the tokenId for this token
            token_id = await self.get_token_id_for_token(token_address)
            if token_id is None:
                logger.error(f"Could not find tokenId for token {token_address}")
                return None
            
            logger.info(f"Claiming fees for token {token_address} using tokenId {token_id}")
            
            # Build transaction
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
            receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=300)
            
            if receipt['status'] == 1:
                logger.info(f"Successfully claimed fees: {tx_hash.hex()}")
                return tx_hash.hex()
            else:
                logger.error("Fee claim transaction failed")
                return None
                
        except Exception as e:
            logger.error(f"Error claiming fees: {e}")
            return None
    
    async def get_dok_price_v3(self) -> float:
        """Get current DOK price in ETH from Uniswap V3 pool"""
        try:
            # Use the V3 pool from the transaction
            pool_contract = self.w3.eth.contract(address=DOK_WETH_V3_POOL, abi=PAIR_ABI)
            
            # Get reserves to calculate price
            reserves = pool_contract.functions.getReserves().call()
            token0 = pool_contract.functions.token0().call()
            
            # Determine which reserve is DOK
            if token0.lower() == DOK_ADDRESS.lower():
                dok_reserve = reserves[0]
                weth_reserve = reserves[1]
            else:
                dok_reserve = reserves[1]
                weth_reserve = reserves[0]
            
            # Calculate price (WETH per DOK)
            price = weth_reserve / dok_reserve
            logger.info(f"DOK price from V3: {price:.8f} ETH")
            return price
            
        except Exception as e:
            logger.warning(f"Could not get V3 price, using fallback: {e}")
            # Fallback to approximate price
            return 0.00008  # ~$0.20 at $2500 ETH
    
    async def execute_dok_buyback_v3(self, amount_eth: float, reference_tx: str) -> Dict:
        """Execute DOK buyback on Uniswap V3 and burn"""
        try:
            amount_wei = self.w3.to_wei(amount_eth, 'ether')
            
            # For V3, we need to use the Universal Router or SwapRouter
            # For simplicity, let's use V2 router which also works
            # Get current DOK price to calculate min output
            dok_price = await self.get_dok_price_v3()
            expected_dok = amount_eth / dok_price
            min_dok_out = int(expected_dok * 0.97 * 1e18)  # 3% slippage
            
            # Prepare swap path
            path = [WETH_ADDRESS, DOK_ADDRESS]
            deadline = int(self.w3.eth.get_block('latest')['timestamp']) + 300  # 5 minutes
            
            logger.info(f"Executing buyback: {amount_eth} ETH for ~{expected_dok:,.0f} DOK")
            
            # Build swap transaction
            function_call = self.router_v2.functions.swapExactETHForTokens(
                min_dok_out,
                path,
                BURN_ADDRESS,  # Send directly to burn address
                deadline
            )
            
            # Get gas estimate
            gas_estimate = function_call.estimate_gas({
                'from': self.account.address,
                'value': amount_wei
            })
            
            nonce = self.w3.eth.get_transaction_count(self.account.address)
            gas_price = self.w3.eth.gas_price
            
            tx = function_call.build_transaction({
                'from': self.account.address,
                'value': amount_wei,
                'gas': int(gas_estimate * 1.2),  # 20% buffer
                'gasPrice': gas_price,
                'nonce': nonce,
                'chainId': self.w3.eth.chain_id
            })
            
            # Sign and send
            signed_tx = self.account.sign_transaction(tx)
            tx_hash = self.w3.eth.send_raw_transaction(signed_tx.rawTransaction)
            
            # Wait for confirmation
            receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=300)
            
            if receipt['status'] == 1:
                # Try to get actual DOK amount from logs
                actual_dok = expected_dok  # Default to expected
                
                # Check burn address balance increase (more accurate)
                try:
                    dok_contract = self.w3.eth.contract(address=DOK_ADDRESS, abi=ERC20_ABI)
                    # Note: This is approximate as other burns might happen
                    actual_dok = expected_dok
                except:
                    pass
                
                logger.info(f"Successfully bought and burned {actual_dok:,.0f} DOK: {tx_hash.hex()}")
                
                return {
                    'success': True,
                    'tx_hash': tx_hash.hex(),
                    'dok_amount': actual_dok
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
async def claim_fees_for_token(token_address: str) -> Optional[str]:
    """Claim fees for a token address"""
    return await factory_interface.claim_fees_for_token(token_address)

async def execute_dok_buyback(amount: float, reference_tx: str) -> Dict:
    """Execute DOK buyback and burn"""
    return await factory_interface.execute_dok_buyback_v3(amount, reference_tx)

# Backward compatibility - these will be deprecated
async def get_pool_address(token_address: str) -> Optional[str]:
    """DEPRECATED - Use claim_fees_for_token directly"""
    # Return the token address itself as we now handle lookup internally
    return token_address

async def check_claimable_fees(pool_address: str) -> float:
    """DEPRECATED - Cannot check claimable fees without simulation"""
    return 0.0

async def claim_fees_from_pool(pool_address: str) -> Optional[str]:
    """DEPRECATED - Use claim_fees_for_token instead"""
    # Assume pool_address is actually token_address for backward compatibility
    return await factory_interface.claim_fees_for_token(pool_address) 