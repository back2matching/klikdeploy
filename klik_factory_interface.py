#!/usr/bin/env python3
"""
Klik Factory Contract Interface
Handles fee detection and pool interactions
"""

import os
import json
import asyncio
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
WETH_ADDRESS = "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2"
DOK_ADDRESS = "0x69ca61398eCa94D880393522C1Ef5c3D8c058837"

# DOK/WETH pair on Uniswap V3 (from the transaction logs)
DOK_WETH_V3_POOL = "0xf6E2edc5953Da297947C6C68911E16CF1C9b64B6"

# Known token to tokenId mappings from transaction analysis
KNOWN_TOKEN_IDS = {
    "0x69ca61398eCa94D880393522C1Ef5c3D8c058837": 1018175,  # DOK tokenId from tx analysis
    "0x692Ea3f6E92000a966874715A6cC53c6E74E269F": 1018890,  # MOON tokenId from your example
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

# Pair ABI to check reserves
PAIR_ABI = [
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

# Uniswap V3 Router ABI (SwapRouter)
UNISWAP_V3_ROUTER_ABI = [
    {
        "inputs": [
            {
                "components": [
                    {"name": "tokenIn", "type": "address"},
                    {"name": "tokenOut", "type": "address"},
                    {"name": "fee", "type": "uint24"},
                    {"name": "recipient", "type": "address"},
                    {"name": "deadline", "type": "uint256"},
                    {"name": "amountIn", "type": "uint256"},
                    {"name": "amountOutMinimum", "type": "uint256"},
                    {"name": "sqrtPriceLimitX96", "type": "uint160"}
                ],
                "name": "params",
                "type": "tuple"
            }
        ],
        "name": "exactInputSingle",
        "outputs": [{"name": "amountOut", "type": "uint256"}],
        "stateMutability": "payable",
        "type": "function"
    }
]

# Compatibility for older Python versions
if hasattr(asyncio, 'to_thread'):
    to_thread = asyncio.to_thread
else:
    # Fallback for Python < 3.9
    import concurrent.futures
    _executor = concurrent.futures.ThreadPoolExecutor(max_workers=10)
    
    async def to_thread(func, *args, **kwargs):
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(_executor, func, *args, **kwargs)

class KlikFactoryInterface:
    """Interface for Klik Factory contract interactions"""
    
    def __init__(self):
        self.rpc_url = os.getenv('ALCHEMY_RPC_URL')
        self.private_key = os.getenv('PRIVATE_KEY')
        self.w3 = Web3(Web3.HTTPProvider(self.rpc_url))
        self.account = Account.from_key(self.private_key)
        
        # Initialize contracts
        self.factory = self.w3.eth.contract(address=KLIK_FACTORY, abi=FACTORY_ABI)
        self.router_v3 = self.w3.eth.contract(address=UNISWAP_V3_ROUTER, abi=UNISWAP_V3_ROUTER_ABI)
    
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
            # Get current block
            current_block = self.w3.eth.block_number
            # Start from a reasonable recent block (e.g., 1 million blocks back ~4 months)
            from_block = max(0, current_block - 1000000)
            
            response = requests.post(self.rpc_url, json={
                "jsonrpc": "2.0",
                "method": "eth_getLogs",
                "params": [{
                    "fromBlock": hex(from_block),
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
    
    async def get_token_id_from_deployment_event(self, token_address: str) -> Optional[int]:
        """Find tokenId by looking for the pool creation event"""
        try:
            token_address = Web3.to_checksum_address(token_address)
            
            # Use Alchemy's enhanced API to find pool creation events
            # Get current block and work in chunks to avoid hitting limits
            current_block = self.w3.eth.block_number
            start_block = 0x13B8A00  # Block ~20M
            chunk_size = 500  # Alchemy's limit
            
            all_logs = []
            
            # Process in chunks of 500 blocks
            for from_block in range(start_block, current_block, chunk_size):
                to_block = min(from_block + chunk_size - 1, current_block)
                
                response = requests.post(self.rpc_url, json={
                    "jsonrpc": "2.0",
                    "method": "eth_getLogs",
                    "params": [{
                        "fromBlock": hex(from_block),
                        "toBlock": hex(to_block),
                        "address": KLIK_FACTORY,
                        "topics": [
                            # PairCreated event signature
                            "0x0d3648bd0f6ba80134a33ba9275ac585d9d315f0ad8355cddefde31afa28d0e9",
                            None,  # token0
                            None   # token1
                        ]
                    }],
                    "id": 1
                })
                
                if response.status_code == 200:
                    logs = response.json().get('result', [])
                    all_logs.extend(logs)
                    
                    # Check if we found the token in this batch
                    for log in logs:
                        # Check if this log contains our token
                        data = log['data']
                        pool_address = '0x' + data[26:66]
                        token_id_hex = data[-64:]
                        token_id = int(token_id_hex, 16)
                        
                        if len(log['topics']) >= 3:
                            token0 = '0x' + log['topics'][1][-40:]
                            token1 = '0x' + log['topics'][2][-40:]
                            
                            if token_address.lower() in [token0.lower(), token1.lower()]:
                                logger.info(f"Found tokenId {token_id} for {token_address} in pool {pool_address}")
                                
                                # Cache and return immediately
                                KNOWN_TOKEN_IDS[token_address] = token_id
                                
                                # Update database
                                try:
                                    import sqlite3
                                    conn = sqlite3.connect('deployments.db')
                                    
                                    cursor = conn.execute("PRAGMA table_info(deployed_tokens)")
                                    columns = [row[1] for row in cursor.fetchall()]
                                    
                                    if 'token_id' not in columns:
                                        conn.execute("ALTER TABLE deployed_tokens ADD COLUMN token_id INTEGER")
                                    
                                    conn.execute(
                                        "UPDATE deployed_tokens SET token_id = ? WHERE token_address = ?",
                                        (token_id, token_address)
                                    )
                                    conn.commit()
                                    conn.close()
                                except Exception as db_error:
                                    logger.warning(f"Could not update database: {db_error}")
                                
                                return token_id
                else:
                    logger.warning(f"Failed to get logs for block range {from_block}-{to_block}: {response.status_code}")
                    
                # Small delay to avoid rate limits
                await asyncio.sleep(0.1)
            
            return None
            
        except Exception as e:
            logger.error(f"Error finding token from events: {e}")
            return None

    async def get_token_id_from_database(self, token_address: str) -> Optional[int]:
        """Check if we have the tokenId cached in our database"""
        try:
            import sqlite3
            conn = sqlite3.connect('deployments.db')
            
            # First check deployed_tokens table
            cursor = conn.execute(
                "SELECT token_id FROM deployed_tokens WHERE token_address = ? AND token_id IS NOT NULL",
                (token_address,)
            )
            result = cursor.fetchone()
            
            if result:
                conn.close()
                return result[0]
            
            # Check deployments table for recent deployments
            cursor = conn.execute('''
                SELECT d.token_address, d.tx_hash 
                FROM deployments d 
                WHERE d.token_address = ? 
                AND d.status = 'success'
                ORDER BY d.requested_at DESC 
                LIMIT 1
            ''', (token_address,))
            
            deployment = cursor.fetchone()
            conn.close()
            
            if deployment and deployment[1]:
                # We have a deployment tx, analyze it to find the pool creation
                logger.info(f"Found deployment tx {deployment[1]} for {token_address}")
                # Could analyze this tx to find the pool creation event
                
            return None
            
        except Exception as e:
            logger.warning(f"Database lookup failed: {e}")
            return None

    async def get_token_id_for_token(self, token_address: str) -> Optional[int]:
        """Get tokenId for a token by finding its pool in the allPairs array"""
        try:
            # Normalize address
            token_address = Web3.to_checksum_address(token_address)
            
            # 1. Check if we have a known mapping
            if token_address in KNOWN_TOKEN_IDS:
                token_id = KNOWN_TOKEN_IDS[token_address]
                logger.info(f"Using known tokenId {token_id} for {token_address}")
                return token_id
            
            # 2. Check database cache
            token_id = await self.get_token_id_from_database(token_address)
            if token_id is not None:
                logger.info(f"Found tokenId {token_id} in database for {token_address}")
                KNOWN_TOKEN_IDS[token_address] = token_id
                return token_id
            
            # 3. Try to find from pool creation events (most efficient)
            token_id = await self.get_token_id_from_deployment_event(token_address)
            if token_id is not None:
                return token_id
            
            # 4. If still not found, check if this is a recent deployment we know about
            logger.warning(f"Could not find tokenId for {token_address} using efficient methods")
            
            # 5. Last resort - binary search through recent pairs (limited range)
            pairs_length = self.factory.functions.allPairsLength().call()
            logger.info(f"Total pairs: {pairs_length}. Checking last 10,000 pairs only...")
            
            # Only check recent pairs (last 10k)
            start_index = max(0, pairs_length - 10000)
            
            for i in range(pairs_length - 1, start_index, -1):
                if i % 100 == 0:
                    logger.info(f"Checking pair {i}...")
                
                try:
                    pair_address = self.factory.functions.allPairs(i).call()
                    
                    # Check if this pair contains our token
                    pair_contract = self.w3.eth.contract(address=pair_address, abi=PAIR_ABI)
                    token0 = pair_contract.functions.token0().call()
                    token1 = pair_contract.functions.token1().call()
                    
                    if token_address.lower() == token0.lower() or token_address.lower() == token1.lower():
                        logger.info(f"Found token {token_address} in pair {pair_address} at index {i}")
                        
                        # Cache this discovery
                        KNOWN_TOKEN_IDS[token_address] = i
                        
                        # Update database
                        try:
                            import sqlite3
                            conn = sqlite3.connect('deployments.db')
                            
                            # Ensure column exists
                            cursor = conn.execute("PRAGMA table_info(deployed_tokens)")
                            columns = [row[1] for row in cursor.fetchall()]
                            
                            if 'token_id' not in columns:
                                conn.execute("ALTER TABLE deployed_tokens ADD COLUMN token_id INTEGER")
                            
                            # Insert or update
                            conn.execute('''
                                INSERT OR REPLACE INTO deployed_tokens 
                                (token_address, token_id, pool_address)
                                VALUES (?, ?, ?)
                            ''', (token_address, i, pair_address))
                            conn.commit()
                            conn.close()
                        except Exception as db_error:
                            logger.warning(f"Could not update database: {db_error}")
                        
                        return i
                        
                except Exception as e:
                    # Some pairs might not be standard, skip them
                    continue
            
            logger.error(f"Token {token_address} not found in recent pairs. It might be older than 10k pairs ago.")
            return None
            
        except Exception as e:
            logger.error(f"Error finding tokenId: {e}")
            return None
    
    async def get_dok_price_v3(self) -> float:
        """Get current DOK price in ETH from Uniswap V3 pool"""
        # First, try to find the pool if we don't have it
        pool_address = DOK_WETH_V3_POOL
        
        # Check if the hardcoded pool is valid
        test_response = requests.post(self.rpc_url, json={
            "jsonrpc": "2.0",
            "method": "eth_call",
            "params": [{
                "to": pool_address,
                "data": "0x3850c7bd"  # slot0()
            }, "latest"],
            "id": 1
        })
        
        if test_response.status_code != 200 or not test_response.json().get('result') or len(test_response.json().get('result', '')) < 66:
            found_pool = await self.find_dok_weth_v3_pool()
            if not found_pool:
                raise Exception("No DOK/WETH Uniswap V3 pool found")
            pool_address = found_pool
        
        # Call slot0() on the V3 pool
        response = requests.post(self.rpc_url, json={
            "jsonrpc": "2.0",
            "method": "eth_call",
            "params": [{
                "to": pool_address,
                "data": "0x3850c7bd"  # slot0() function selector
            }, "latest"],
            "id": 1
        })
        
        if response.status_code != 200:
            raise Exception(f"Failed to get slot0 data: HTTP {response.status_code}")
        
        response_data = response.json()
        if 'error' in response_data:
            raise Exception(f"RPC error: {response_data['error']}")
            
        result = response_data.get('result')
        
        if not result or len(result) < 66:  # 0x + 64 hex chars for first 32 bytes
            raise Exception(f"Invalid slot0 result: {result}")
        
        # Extract sqrtPriceX96 (first 32 bytes after 0x)
        sqrtPriceX96_hex = result[2:66]  # Skip 0x and take first 32 bytes
        sqrtPriceX96 = int(sqrtPriceX96_hex, 16)
        
        if sqrtPriceX96 == 0:
            raise Exception("sqrtPriceX96 is zero - pool might not be initialized")
        
        # Get token0 and token1 addresses to determine price direction
        # token0() function selector: 0x0dfe1681
        token0_response = requests.post(self.rpc_url, json={
            "jsonrpc": "2.0",
            "method": "eth_call",
            "params": [{
                "to": pool_address,
                "data": "0x0dfe1681"
            }, "latest"],
            "id": 1
        })
        
        if token0_response.status_code != 200:
            raise Exception(f"Failed to get token0: HTTP {token0_response.status_code}")
            
        token0_data = token0_response.json()
        token0_result = token0_data.get('result')
        if not token0_result:
            raise Exception("No token0 result")
            
        # Extract address from the result (last 20 bytes of 32 byte result)
        token0_address = '0x' + token0_result[-40:]
        
        # token1() function selector: 0xd21220a7
        token1_response = requests.post(self.rpc_url, json={
            "jsonrpc": "2.0",
            "method": "eth_call",
            "params": [{
                "to": pool_address,
                "data": "0xd21220a7"
            }, "latest"],
            "id": 1
        })
        
        if token1_response.status_code != 200:
            raise Exception(f"Failed to get token1: HTTP {token1_response.status_code}")
            
        token1_data = token1_response.json()
        token1_result = token1_data.get('result')
        if not token1_result:
            raise Exception("No token1 result")
            
        token1_address = '0x' + token1_result[-40:]
        
        # Calculate the actual price from sqrtPriceX96
        # sqrtPriceX96 = sqrt(price) * 2^96
        # price = (sqrtPriceX96 / 2^96)^2
        
        # First convert to sqrtPrice
        sqrtPrice = sqrtPriceX96 / (2 ** 96)
        
        # Then square to get price
        price = sqrtPrice ** 2
        
        # Check token ordering
        if token0_address.lower() == DOK_ADDRESS.lower():
            # DOK is token0, WETH is token1
            # price is WETH/DOK (amount of WETH per DOK)
            price_in_eth = price
        elif token1_address.lower() == DOK_ADDRESS.lower():
            # DOK is token1, WETH is token0
            # price is DOK/WETH (amount of DOK per WETH)
            # We want WETH/DOK, so invert
            if price == 0:
                raise Exception("Price is zero - cannot calculate")
            price_in_eth = 1 / price
        else:
            raise Exception(f"DOK not found in pool. Token0: {token0_address}, Token1: {token1_address}")
        
        # Apply decimal adjustments if needed
        # Both DOK and WETH have 18 decimals, so no adjustment needed
        
        logger.info(f"DOK price from V3 pool: {price_in_eth:.8f} ETH")
        
        return price_in_eth
    
    async def execute_dok_buyback_v3(self, amount_eth: float, reference_tx: str, silent: bool = False) -> Dict:
        """Execute DOK buyback and hold in our wallet"""
        try:
            # Simply use the general buyback method which now supports V3
            result = await self.execute_token_buyback(DOK_ADDRESS, amount_eth, silent=silent)
            
            if result['success']:
                # Try to get actual DOK amount and price
                try:
                    dok_price = await self.get_dok_price_v3()
                    expected_dok = amount_eth / dok_price
                    result['dok_amount'] = expected_dok
                    if not silent:
                        print(f"   DOK price: {dok_price:.8f} ETH (${dok_price * 2500:.2f} at $2500/ETH)")
                        print(f"   Expected DOK amount: {expected_dok:,.2f}")
                except Exception as e:
                    logger.warning(f"Could not get DOK price: {e}")
                    # Don't set dok_amount if we can't get the real price
                    if not silent:
                        print(f"   Note: Could not fetch current DOK price from V3 pool")
                    
            return result
                
        except Exception as e:
            logger.error(f"DOK buyback failed: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    async def simulate_fee_claim(self, token_address: str) -> Dict:
        """DEPRECATED - DO NOT USE - Active claiming disabled"""
        logger.error("Fee simulation is disabled. Fees are now claimed automatically by the platform.")
        return {
            'success': False,
            'error': 'Active fee claiming is disabled. Use detect_incoming_fee_claims instead.'
        }
    
    async def check_claimable_fees_with_fork(self, token_address: str) -> Dict:
        """Use Alchemy's fork feature to simulate the exact fee amount"""
        try:
            # Get tokenId
            token_id = await self.get_token_id_for_token(token_address)
            if token_id is None:
                return {'success': False, 'error': 'Token not found'}
            
            # Create a fork and simulate the transaction
            # This uses Alchemy's anvil_* methods if available
            fork_response = requests.post(self.rpc_url, json={
                "jsonrpc": "2.0",
                "method": "anvil_createFork",
                "params": ["latest"],
                "id": 1
            })
            
            if fork_response.status_code == 200 and 'result' in fork_response.json():
                fork_id = fork_response.json()['result']
                
                # Now simulate on the fork
                # ... implementation continues
                
                # Clean up fork
                requests.post(self.rpc_url, json={
                "jsonrpc": "2.0",
                    "method": "anvil_removeFork",
                    "params": [fork_id],
                    "id": 1
                })
            
            # If fork not available, fall back to regular simulation
            return await self.simulate_fee_claim(token_address)
            
        except Exception as e:
            logger.error(f"Fork simulation failed: {e}")
            return await self.simulate_fee_claim(token_address)

    async def decode_collect_fee_transaction(self, tx_hash: str) -> Optional[Dict]:
        """Decode a collectFee transaction to get the tokenId and related info"""
        try:
            # Get transaction details
            tx = self.w3.eth.get_transaction(tx_hash)
            receipt = self.w3.eth.get_transaction_receipt(tx_hash)
            
            if not tx:
                logger.error(f"Transaction {tx_hash} not found")
                return None
            
            # Check if it's to the factory contract
            if tx['to'].lower() != KLIK_FACTORY.lower():
                logger.error(f"Transaction is not to Klik Factory")
                return None
            
            # Decode the input data
            try:
                decoded_input = self.factory.decode_function_input(tx['input'])
                function_name = decoded_input[0].fn_name
                params = decoded_input[1]
                
                if function_name == 'collectFees' and 'tokenId' in params:
                    token_id = params['tokenId']
                    
                    # Parse logs to find the pool and token
                    pool_address = None
                    token_addresses = []
                    
                    # Look for Collect event from the pool (has 4 topics)
                    for log in receipt['logs']:
                        # Collect event has signature: 0x70935338e69775456a85ddef226c395fb668b63fa0115f5f20610b388e6ca9c0
                        if (len(log['topics']) == 4 and 
                            log['topics'][0].hex() == '0x70935338e69775456a85ddef226c395fb668b63fa0115f5f20610b388e6ca9c0'):
                            pool_address = log['address']
                            logger.info(f"Found pool address from Collect event: {pool_address}")
                        
                        # ERC20 Transfer events (3 topics)
                        elif (len(log['topics']) == 3 and 
                              log['topics'][0].hex() == '0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef'):
                            token_address = log['address']
                            if token_address.lower() not in [pool_address.lower() if pool_address else '', KLIK_FACTORY.lower()]:
                                token_addresses.append(token_address)
                    
                    # Identify which is the deployed token (not WETH)
                    deployed_token = None
                    for token in token_addresses:
                        if token.lower() != WETH_ADDRESS.lower():
                            deployed_token = token
                            break
                    
                    if not deployed_token and token_addresses:
                        deployed_token = token_addresses[0]  # Fallback to first token
                    
                    # Try to get token info from our database
                    token_info = None
                    if deployed_token:
                        try:
                            import sqlite3
                            conn = sqlite3.connect('deployments.db')
                            cursor = conn.execute(
                                "SELECT token_symbol, token_name FROM deployments WHERE token_address = ?",
                                (deployed_token,)
                            )
                            result = cursor.fetchone()
                            if result:
                                token_info = {'symbol': result[0], 'name': result[1]}
                            conn.close()
                        except Exception as db_error:
                            logger.warning(f"Could not get token info from database: {db_error}")
                    
                    logger.info(f"Decoded fee claim - Token: {deployed_token}, Pool: {pool_address}, TokenId: {token_id}")
                    
                    return {
                        'token_id': token_id,
                        'pool_address': pool_address,
                        'deployed_token': deployed_token,
                        'token_addresses': token_addresses,
                        'token_info': token_info,
                        'tx_hash': tx_hash
                    }
                else:
                    logger.error(f"Not a collectFees transaction or missing tokenId")
                    return None
                    
            except Exception as e:
                logger.error(f"Error decoding transaction input: {e}")
                return None
                
        except Exception as e:
            logger.error(f"Error decoding collect fee transaction: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return None
    
    async def execute_token_buyback(self, token_address: str, amount_eth: float, destination_address: str = None, silent: bool = False) -> Dict:
        """Execute buyback for any token and hold in our wallet"""
        try:
            amount_wei = self.w3.to_wei(amount_eth, 'ether')
            
            # Use our wallet as destination if not specified
            if destination_address is None:
                destination_address = self.account.address
            
            deadline = int(self.w3.eth.get_block('latest')['timestamp']) + 300
            
            if not silent:
                print(f"   Executing buyback: {amount_eth} ETH for {token_address}")
                print(f"   Destination: {destination_address}")
            logger.info(f"Executing buyback: {amount_eth} ETH for {token_address}")
            logger.info(f"Destination: {destination_address}")
            
            # Use only 1% fee tier since that's what worked in testing
            fee = 10000  # 1% fee tier
            
            if not silent:
                print("   Attempting V3 swap with 1% fee tier...")
            logger.info("Attempting V3 swap with 1% fee tier...")
            
            # Build V3 swap params
            swap_params = {
                'tokenIn': WETH_ADDRESS,
                'tokenOut': token_address,
                'fee': fee,
                'recipient': destination_address,
                'deadline': deadline,
                'amountIn': amount_wei,
                'amountOutMinimum': 0,  # Accept any amount
                'sqrtPriceLimitX96': 0  # No price limit
            }
            
            if not silent:
                print("   Building transaction...")
            logger.info("Building transaction...")
            function_call = self.router_v3.functions.exactInputSingle(swap_params)
            
            # Get current gas price first
            gas_price = self.w3.eth.gas_price
            # Increase gas price by 50% for instant execution
            instant_gas_price = int(gas_price * 1.5)
            # Ensure minimum 0.5 gwei for instant execution
            min_gas_price = self.w3.to_wei(0.5, 'gwei')
            instant_gas_price = max(instant_gas_price, min_gas_price)
            
            if not silent:
                print(f"   Base gas price: {self.w3.from_wei(gas_price, 'gwei'):.2f} gwei")
                print(f"   Using instant gas: {self.w3.from_wei(instant_gas_price, 'gwei'):.2f} gwei (min 0.5)")
            logger.info(f"Current gas price: {self.w3.from_wei(gas_price, 'gwei'):.2f} gwei")
            logger.info(f"Using instant gas price: {self.w3.from_wei(instant_gas_price, 'gwei'):.2f} gwei")
            
            # Try to estimate gas with timeout
            if not silent:
                print("   Estimating gas...")
            logger.info("Estimating gas...")
            try:
                # Add timeout for gas estimation
                gas_estimate = await asyncio.wait_for(
                    to_thread(
                        function_call.estimate_gas,
                        {'from': self.account.address, 'value': amount_wei}
                    ),
                    timeout=30.0  # 30 second timeout
                )
                if not silent:
                    print(f"   Gas estimate: {gas_estimate:,}")
                logger.info(f"Gas estimate: {gas_estimate:,}")
            except asyncio.TimeoutError:
                if not silent:
                    print("   ❌ Gas estimation timed out after 30 seconds")
                logger.error("Gas estimation timed out after 30 seconds")
                return {
                    'success': False,
                    'error': 'Gas estimation timeout - pool might not exist or have liquidity'
                }
            except Exception as e:
                if not silent:
                    print(f"   ❌ Gas estimation failed: {str(e)}")
                logger.error(f"Gas estimation failed: {str(e)}")
                # If it's a revert error, the pool likely doesn't exist
                if "execution reverted" in str(e).lower():
                    return {
                        'success': False,
                        'error': 'No liquidity pool found for this token on Uniswap V3 with 1% fee'
                    }
                return {
                    'success': False,
                    'error': f'Gas estimation failed: {str(e)}'
                }
            
            if not silent:
                print("   ✅ V3 pool found with 1% fee tier")
            logger.info("V3 pool found with 1% fee tier")
            
            nonce = self.w3.eth.get_transaction_count(self.account.address)
            if not silent:
                print(f"   Account nonce: {nonce}")
            logger.info(f"Account nonce: {nonce}")
            
            # Build transaction with higher gas
            final_gas_limit = int(gas_estimate * 2.0)  # 100% buffer (doubled from estimate)
            if not silent:
                print(f"   Using gas limit: {final_gas_limit:,} (2x estimate)")
            
            tx = function_call.build_transaction({
                'from': self.account.address,
                'value': amount_wei,
                'gas': final_gas_limit,
                'gasPrice': instant_gas_price,  # Use higher gas price
                'nonce': nonce,
                'chainId': self.w3.eth.chain_id
            })
            
            if not silent:
                print("   Signing transaction...")
            logger.info("Signing transaction...")
            # Sign and send
            signed_tx = self.account.sign_transaction(tx)
            
            total_gas_cost = self.w3.from_wei(final_gas_limit * instant_gas_price, 'ether')
            if not silent:
                print(f"   Max gas cost: {total_gas_cost:.6f} ETH")
                print(f"   Sending transaction...")
            logger.info(f"Sending transaction with gas: {int(final_gas_limit):,}")
            logger.info("Sending transaction...")
            tx_hash = self.w3.eth.send_raw_transaction(signed_tx.rawTransaction)
            if not silent:
                print(f"   Transaction sent: {tx_hash.hex()}")
            logger.info(f"Transaction sent: {tx_hash.hex()}")
            
            # Wait for confirmation with timeout
            if not silent:
                print("   Waiting for confirmation (max 5 minutes)...")
            logger.info("Waiting for confirmation (max 5 minutes)...")
            try:
                receipt = await asyncio.wait_for(
                    to_thread(
                        self.w3.eth.wait_for_transaction_receipt,
                        tx_hash,
                        timeout=300
                    ),
                    timeout=310.0  # Slightly longer than web3's timeout
                )
            except asyncio.TimeoutError:
                if not silent:
                    print("   ❌ Transaction confirmation timed out after 5 minutes")
                logger.error("Transaction confirmation timed out after 5 minutes")
                return {
                    'success': False,
                    'error': 'Transaction timeout - check etherscan',
                    'tx_hash': tx_hash.hex()
                }
            
            if receipt['status'] == 1:
                if not silent:
                    print(f"   ✅ Successfully bought token via V3")
                logger.info(f"Successfully bought token {token_address} via V3 (now holding): {tx_hash.hex()}")
                
                return {
                    'success': True,
                    'tx_hash': tx_hash.hex(),
                    'token_address': token_address,
                    'amount_eth': amount_eth,
                    'destination': destination_address,
                    'router': 'V3',
                    'fee_tier': fee
                }
            else:
                if not silent:
                    print(f"   ❌ Transaction failed: {tx_hash.hex()}")
                logger.error(f"Transaction failed: {tx_hash.hex()}")
                return {
                    'success': False,
                    'error': 'Transaction reverted',
                    'tx_hash': tx_hash.hex()
                }
                
        except Exception as e:
            if not silent:
                print(f"   ❌ Buyback failed: {e}")
            logger.error(f"Buyback failed: {e}")
            import traceback
            traceback.print_exc()
            return {
                'success': False,
                'error': str(e)
            }
    
    async def find_dok_weth_v3_pool(self) -> Optional[str]:
        """Find the DOK/WETH Uniswap V3 pool address"""
        try:
            # Uniswap V3 Factory address
            v3_factory = "0x1F98431c8aD98523631AE4a59f267346ea31F984"
            
            # Common fee tiers for V3: 500 (0.05%), 3000 (0.3%), 10000 (1%)
            fee_tiers = [500, 3000, 10000]
            
            print(f"[DEBUG] Looking for DOK/WETH pool on Uniswap V3...")
            print(f"[DEBUG] DOK: {DOK_ADDRESS}")
            print(f"[DEBUG] WETH: {WETH_ADDRESS}")
            
            # getPool(address,address,uint24) function selector: 0x1698ee82
            for fee in fee_tiers:
                # Encode the function call
                # Function selector (4 bytes) + token0 (32 bytes) + token1 (32 bytes) + fee (32 bytes)
                token0 = DOK_ADDRESS if DOK_ADDRESS.lower() < WETH_ADDRESS.lower() else WETH_ADDRESS
                token1 = WETH_ADDRESS if DOK_ADDRESS.lower() < WETH_ADDRESS.lower() else DOK_ADDRESS
                
                # Pad addresses to 32 bytes
                token0_padded = token0[2:].lower().zfill(64)
                token1_padded = token1[2:].lower().zfill(64)
                fee_padded = hex(fee)[2:].zfill(64)
                
                data = f"0x1698ee82{token0_padded}{token1_padded}{fee_padded}"
                
                print(f"[DEBUG] Checking fee tier {fee} ({fee/10000}%)...")
                
                response = requests.post(self.rpc_url, json={
                "jsonrpc": "2.0",
                    "method": "eth_call",
                    "params": [{
                        "to": v3_factory,
                        "data": data
                    }, "latest"],
                "id": 1
            })
            
                if response.status_code == 200:
                    result = response.json().get('result')
                    if result and result != '0x0000000000000000000000000000000000000000000000000000000000000000':
                        # Extract address from result (last 20 bytes)
                        pool_address = '0x' + result[-40:]
                        print(f"[DEBUG] Found pool at {pool_address} with fee {fee}")
                        
                        # Verify it's a valid pool by calling slot0
                        verify_response = requests.post(self.rpc_url, json={
                    "jsonrpc": "2.0",
                            "method": "eth_call",
                            "params": [{
                                "to": pool_address,
                                "data": "0x3850c7bd"  # slot0()
                            }, "latest"],
                    "id": 1
                })
            
                        if verify_response.status_code == 200:
                            verify_result = verify_response.json().get('result')
                            if verify_result and len(verify_result) > 66:
                                print(f"[DEBUG] Verified pool is active")
                                return pool_address
                        
            print(f"[DEBUG] No DOK/WETH V3 pool found")
            return None
            
        except Exception as e:
            logger.error(f"Error finding DOK/WETH pool: {e}")
            return None

# Singleton instance
factory_interface = KlikFactoryInterface()

# Export the functions for use in telegram bot
async def execute_dok_buyback(amount: float, reference_tx: str, silent: bool = False) -> Dict:
    """Execute DOK buyback and hold in wallet"""
    return await factory_interface.execute_dok_buyback_v3(amount, reference_tx, silent)

# New functions for passive fee processing
async def decode_collect_fee_transaction(tx_hash: str) -> Optional[Dict]:
    """Decode a collectFee transaction to get token details"""
    return await factory_interface.decode_collect_fee_transaction(tx_hash)

async def execute_token_buyback(token_address: str, amount_eth: float, destination_address: str = None, silent: bool = False) -> Dict:
    """Execute buyback for any token and hold in our wallet"""
    return await factory_interface.execute_token_buyback(token_address, amount_eth, destination_address, silent) 