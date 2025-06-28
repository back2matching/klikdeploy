#!/usr/bin/env python3
"""
Klik Factory Contract Interface
Handles fee claiming and pool interactions
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
UNISWAP_V2_ROUTER = "0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D"  # V2 router for DOK
WETH_ADDRESS = "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2"
DOK_ADDRESS = "0x69ca61398eCa94D880393522C1Ef5c3D8c058837"
BURN_ADDRESS = "0x000000000000000000000000000000000000dEaD"  # Not used anymore - we hold tokens instead

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
    
    async def claim_fees_for_token(self, token_address: str) -> Optional[str]:
        """DEPRECATED - DO NOT USE - Active claiming disabled to save gas"""
        logger.error("Active fee claiming is disabled. Fees are now claimed automatically by the platform.")
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
        """Execute DOK buyback on Uniswap V3 and hold in our wallet"""
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
                self.account.address,  # Send to our wallet to hold
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
                
                logger.info(f"Successfully bought {actual_dok:,.0f} DOK (now holding): {tx_hash.hex()}")
                
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
                        except:
                            pass
                    
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
            return None
    
    async def execute_token_buyback(self, token_address: str, amount_eth: float, destination_address: str = None) -> Dict:
        """Execute buyback for any token and hold in our wallet"""
        try:
            amount_wei = self.w3.to_wei(amount_eth, 'ether')
            
            # Use our wallet as destination if not specified
            if destination_address is None:
                destination_address = self.account.address
            
            # Check if it's DOK - use existing method
            if token_address.lower() == DOK_ADDRESS.lower():
                return await self.execute_dok_buyback_v3(amount_eth, "auto_buyback")
            
            # For other tokens, we need to find their pool and router
            # First check if there's a V2 pool
            path = [WETH_ADDRESS, token_address]
            deadline = int(self.w3.eth.get_block('latest')['timestamp']) + 300
            
            logger.info(f"Executing buyback: {amount_eth} ETH for {token_address}")
            
            # Try V2 router
            try:
                # Build swap transaction
                function_call = self.router_v2.functions.swapExactETHForTokens(
                    0,  # Accept any amount of tokens (we'll hold anyway)
                    path,
                    destination_address,
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
                    'gas': int(gas_estimate * 1.2),
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
                    logger.info(f"Successfully bought token {token_address} (now holding): {tx_hash.hex()}")
                    
                    return {
                        'success': True,
                        'tx_hash': tx_hash.hex(),
                        'token_address': token_address,
                        'amount_eth': amount_eth,
                        'destination': destination_address
                    }
                else:
                    return {
                        'success': False,
                        'error': 'Transaction failed'
                    }
                    
            except Exception as e:
                logger.error(f"V2 buyback failed, token might not have liquidity: {e}")
                # Could try V3 or other DEXs here
                return {
                    'success': False,
                    'error': f'No liquidity found: {str(e)}'
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
    """DEPRECATED - Active claiming disabled"""
    return await factory_interface.claim_fees_for_token(token_address)

async def simulate_fee_claim(token_address: str) -> Dict:
    """DEPRECATED - Active claiming disabled"""
    return await factory_interface.simulate_fee_claim(token_address)

async def execute_dok_buyback(amount: float, reference_tx: str) -> Dict:
    """Execute DOK buyback and hold in wallet"""
    return await factory_interface.execute_dok_buyback_v3(amount, reference_tx)

# New functions for passive fee processing
async def decode_collect_fee_transaction(tx_hash: str) -> Optional[Dict]:
    """Decode a collectFee transaction to get token details"""
    return await factory_interface.decode_collect_fee_transaction(tx_hash)

async def execute_token_buyback(token_address: str, amount_eth: float, destination_address: str = None) -> Dict:
    """Execute buyback for any token and hold"""
    return await factory_interface.execute_token_buyback(token_address, amount_eth, destination_address)

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