#!/usr/bin/env python3
"""
Klik Finance - Standalone Token Deployer
This script contains the core logic for deploying a token using the Klik Finance factory.
It's designed to be used as a library or a standalone script for deployment.

Usage (as a script):
- Set up your .env file with PRIVATE_KEY, ALCHEMY_RPC_URL, etc.
- Run: python contract_deployer.py
"""

import asyncio
import os
import json
import time
from datetime import datetime
from typing import Dict, Optional, Tuple
import logging
from asyncio import Lock

# Web3 and blockchain
from web3 import Web3
from eth_account import Account

# Environment and HTTP
from dotenv import load_dotenv
import aiohttp
import requests

# For image handling
from io import BytesIO
from dataclasses import dataclass

# For address calculation
from eth_hash.auto import keccak
from eth_utils import to_checksum_address

@dataclass
class DeploymentRequest:
    """Represents a token deployment request"""
    tweet_id: str  # Can be a unique identifier
    username: str
    token_name: str
    token_symbol: str
    tweet_url: str # A URL for social link, e.g., twitter post
    image_url: Optional[str] = None # Image for the token
    # These will be populated upon deployment
    tx_hash: Optional[str] = None
    token_address: Optional[str] = None
    status: str = "pending"

@dataclass
class PreparedDeployment:
    """Contains all prepared data for deployment"""
    request: DeploymentRequest
    salt: str
    predicted_address: str
    metadata_ipfs: Optional[str]
    metadata_json: str
    image_ipfs: Optional[str] = None

class ContractDeployer:
    """A standalone deployer for Klik Finance tokens."""
    
    def __init__(self):
        """Initialize the deployer"""
        load_dotenv()
        self._setup_logging()
        self._load_config()
        self._setup_web3()
        
        # For managing nonce in concurrent deployments
        self.nonce_lock = Lock()
        self.last_nonce = None
        self.last_nonce_time = 0
        
        print("🚀 KLIK FINANCE STANDALONE DEPLOYER")
        print("=" * 50)
        print(f"💰 Balance: {self.get_eth_balance():.4f} ETH")
        print(f"✅ Connected to Ethereum (Chain ID: {self.w3.eth.chain_id})")
        print(f"🏭 Using Klik Factory: {self.factory_address}")
        print("=" * 50)

    def _setup_logging(self):
        """Setup logging"""
        os.makedirs('logs', exist_ok=True)
        self.logger = logging.getLogger('contract_deployer')
        self.logger.setLevel(logging.DEBUG)
        
        handler = logging.StreamHandler()
        handler.setLevel(logging.INFO)
        formatter = logging.Formatter('%(asctime)s | %(levelname)s | %(message)s')
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)

    def _load_config(self):
        """Load configuration from environment"""
        required_vars = ['PRIVATE_KEY', 'ALCHEMY_RPC_URL', 'KLIK_FACTORY_ADDRESS']
        missing = [var for var in required_vars if not os.getenv(var)]
        if missing:
            raise ValueError(f"Missing required environment variables: {missing}")
        
        self.private_key = os.getenv('PRIVATE_KEY')
        self.rpc_url = os.getenv('ALCHEMY_RPC_URL')
        self.factory_address = os.getenv('KLIK_FACTORY_ADDRESS')
        
        # Optional configs
        self.gas_limit = int(os.getenv('GAS_LIMIT', '6500000'))
        
        # IPFS service config
        self.pinata_api_key = os.getenv('PINATA_API_KEY')
        self.pinata_secret_key = os.getenv('PINATA_SECRET_KEY')
        self.web3_storage_token = os.getenv('WEB3_STORAGE_TOKEN')

    def _setup_web3(self):
        """Setup Web3 connection"""
        self.w3 = Web3(Web3.HTTPProvider(self.rpc_url))
        if not self.w3.is_connected():
            raise ConnectionError("Failed to connect to Ethereum network")
        
        self.account = Account.from_key(self.private_key)
        self.deployer_address = self.account.address
        
        # Factory contract ABI for deployCoin with salt
        factory_abi = [
            {
                "inputs": [
                    {"name": "_name", "type": "string"},
                    {"name": "_symbol", "type": "string"}, 
                    {"name": "_metadata", "type": "string"},
                    {"name": "salt", "type": "bytes32"}
                ],
                "name": "deployCoin",
                "outputs": [],
                "stateMutability": "payable",
                "type": "function"
            }
        ]
        
        self.factory_contract = self.w3.eth.contract(
            address=self.factory_address,
            abi=factory_abi
        )

    def get_eth_balance(self) -> float:
        """Get current ETH balance"""
        balance_wei = self.w3.eth.get_balance(self.deployer_address)
        return float(self.w3.from_wei(balance_wei, 'ether'))

    async def generate_salt_and_address(self, token_name: str, token_symbol: str) -> Tuple[str, str]:
        """Generate salt using Klik Finance API and calculate predicted address"""
        try:
            print(f"🎲 Generating vanity salt for {token_name} ({token_symbol})...")
            
            # Call Klik Finance API to generate salt
            url = f"https://klik.finance/api/generate-salt"
            params = {
                'name': token_name,
                'symbol': token_symbol,
                'creator': self.deployer_address
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params) as response:
                    if response.status != 200:
                        raise Exception(f"Failed to generate salt: HTTP {response.status}")
                    
                    data = await response.json()
            
            # Validate response
            if not data.get('has_target_prefix') or not data.get('results'):
                raise Exception("No valid salt generated by API")
            
            salt = data['results'][0]['salt']
            bytecode_hash = data['bytecode_hash']
            
            print(f"✅ Salt generated successfully!")
            print(f"   🎯 Target prefix: 0x{data['target_prefix']}")
            print(f"   🔍 Total attempts: {data['total_attempts']}")
            print(f"   ⏱️  Generation time: {data['timeMs']}ms")
            
            # Calculate predicted address using CREATE2
            predicted_address = self._calculate_create2_address(salt, bytecode_hash)
            
            print(f"🎯 Predicted token address: {predicted_address}")
            
            return salt, predicted_address
            
        except Exception as e:
            self.logger.error(f"Error generating salt: {e}")
            raise Exception(f"Failed to generate vanity salt: {e}")

    def _calculate_create2_address(self, salt: str, bytecode_hash: str) -> str:
        """Calculate CREATE2 address"""
        try:
            # Remove 0x prefix for calculation
            factory = self.factory_address[2:] if self.factory_address.startswith('0x') else self.factory_address
            salt_clean = salt[2:] if salt.startswith('0x') else salt
            bytecode_clean = bytecode_hash[2:] if bytecode_hash.startswith('0x') else bytecode_hash
            
            # CREATE2 formula: keccak256(0xff + factory + salt + bytecode_hash)
            data = bytes.fromhex("ff" + factory + salt_clean + bytecode_clean)
            hash_result = keccak(data)
            
            # Address = last 20 bytes
            address = "0x" + hash_result[-20:].hex()
            
            # Return checksum address
            return to_checksum_address(address)
            
        except Exception as e:
            self.logger.error(f"Error calculating CREATE2 address: {e}")
            raise

    async def upload_image_to_ipfs(self, image_url: str) -> Optional[str]:
        """Download image from URL and upload to IPFS"""
        try:
            print(f"🖼️ Uploading image to IPFS...")
            
            # Download the image
            async with aiohttp.ClientSession() as session:
                async with session.get(image_url) as response:
                    if response.status != 200:
                        self.logger.error(f"Failed to download image: {response.status}")
                        return None
                    
                    image_data = await response.read()
                    content_type = response.headers.get('Content-Type', 'image/jpeg')
            
            # Upload to IPFS
            if self.pinata_api_key and self.pinata_secret_key:
                # Use Pinata
                url = "https://api.pinata.cloud/pinning/pinFileToIPFS"
                headers = {
                    "pinata_api_key": self.pinata_api_key,
                    "pinata_secret_api_key": self.pinata_secret_key
                }
                
                # Prepare multipart form data
                files = {
                    'file': ('image', BytesIO(image_data), content_type)
                }
                
                response = requests.post(url, files=files, headers=headers)
                if response.status_code == 200:
                    ipfs_hash = response.json()['IpfsHash']
                    print(f"✅ Image uploaded to IPFS: {ipfs_hash}")
                    return ipfs_hash
                else:
                    self.logger.error(f"Pinata upload failed: {response.text}")
            
            elif self.web3_storage_token:
                # Use web3.storage
                url = "https://api.web3.storage/upload"
                headers = {
                    "Authorization": f"Bearer {self.web3_storage_token}",
                    "X-NAME": "token-image"
                }
                
                response = requests.post(url, data=image_data, headers=headers)
                if response.status_code == 200:
                    cid = response.json()['cid']
                    print(f"✅ Image uploaded to IPFS: {cid}")
                    return cid
                else:
                    self.logger.error(f"Web3.storage upload failed: {response.text}")
            
            self.logger.warning("No IPFS service configured for image upload")
            return None
            
        except Exception as e:
            self.logger.error(f"Error uploading image to IPFS: {e}")
            return None
    
    def upload_metadata_to_ipfs(self, metadata: Dict) -> Optional[str]:
        """Upload metadata JSON to IPFS"""
        try:
            print(f"📄 Uploading metadata to IPFS...")
            
            if self.pinata_api_key and self.pinata_secret_key:
                url = "https://api.pinata.cloud/pinning/pinJSONToIPFS"
                headers = {
                    "pinata_api_key": self.pinata_api_key,
                    "pinata_secret_api_key": self.pinata_secret_key
                }
                
                response = requests.post(url, json=metadata, headers=headers)
                if response.status_code == 200:
                    ipfs_hash = response.json()['IpfsHash']
                    print(f"✅ Metadata uploaded to IPFS: {ipfs_hash}")
                    return ipfs_hash
            
            elif self.web3_storage_token:
                url = "https://api.web3.storage/upload"
                headers = {
                    "Authorization": f"Bearer {self.web3_storage_token}",
                    "Content-Type": "application/json"
                }
                
                response = requests.post(url, json=metadata, headers=headers)
                if response.status_code == 200:
                    cid = response.json()['cid']
                    print(f"✅ Metadata uploaded to IPFS: {cid}")
                    return cid
            
            self.logger.warning("No IPFS service configured for metadata upload")
            return None
            
        except Exception as e:
            self.logger.error(f"Error uploading metadata to IPFS: {e}")
            return None

    async def prepare_deploy(self, request: DeploymentRequest) -> PreparedDeployment:
        """Prepare all deployment data including salt generation, image and metadata upload"""
        try:
            print(f"\n🔧 Preparing deployment for {request.token_name} ({request.token_symbol})")
            
            # Step 1: Generate vanity salt and predict address
            salt, predicted_address = await self.generate_salt_and_address(
                request.token_name, 
                request.token_symbol
            )
            
            # Step 2: Prepare base metadata
            metadata_obj = {
                "uniqueId": f"{self.deployer_address}-{request.token_name}-{request.token_symbol}-{int(time.time() * 1000)}",
                "name": request.token_name,
                "symbol": request.token_symbol,
                "telegram": "",
                "x": request.tweet_url,
                "website": "",
                "image": ""
            }
            
            # Step 3: Handle image upload if present
            image_ipfs = None
            if request.image_url:
                image_ipfs = await self.upload_image_to_ipfs(request.image_url)
                if image_ipfs:
                    metadata_obj["image"] = image_ipfs
            
            # Step 4: Upload metadata to IPFS
            metadata_ipfs = None
            if self.pinata_api_key or self.web3_storage_token:
                metadata_ipfs = self.upload_metadata_to_ipfs(metadata_obj)
            
            # Fallback to JSON string
            metadata_json = json.dumps(metadata_obj)
            
            print(f"✅ Deployment preparation complete!")
            print(f"   🎯 Predicted address: {predicted_address}")
            if image_ipfs:
                print(f"   🖼️ Image IPFS: {image_ipfs}")
            if metadata_ipfs:
                print(f"   📄 Metadata IPFS: {metadata_ipfs}")
            
            return PreparedDeployment(
                request=request,
                salt=salt,
                predicted_address=predicted_address,
                metadata_ipfs=metadata_ipfs,
                metadata_json=metadata_json,
                image_ipfs=image_ipfs
            )
            
        except Exception as e:
            self.logger.error(f"Error preparing deployment: {e}")
            raise Exception(f"Failed to prepare deployment: {e}")

    def _extract_token_address_from_receipt(self, receipt) -> Optional[str]:
        """Extract token address from transaction receipt"""
        try:
            # Look for Transfer events from null address (minting)
            for log in receipt['logs']:
                if len(log['topics']) >= 2:
                    # Transfer event signature
                    if log['topics'][0].hex() == '0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef':
                        # Check if from address is null (minting)
                        if log['topics'][1].hex() == '0x' + '0' * 64:
                            return log['address']
            return None
        except Exception as e:
            self.logger.error(f"Error extracting token address: {e}")
            return None

    async def deploy_token(self, prepared: PreparedDeployment) -> Tuple[bool, Optional[str], Optional[str]]:
        """Deploy a prepared token to Klik Finance"""
        try:
            request = prepared.request
            print(f"\n🚀 Deploying {request.token_name} ({request.token_symbol}) for @{request.username}")
            
            # Check balance
            eth_balance = self.get_eth_balance()
            current_gas_price = self.w3.eth.gas_price
            realistic_gas_units = self.gas_limit
            
            # Calculate expected cost
            expected_gas_cost = float(self.w3.from_wei(current_gas_price * realistic_gas_units, 'ether'))
            
            # Only require 5% buffer over expected cost
            if eth_balance < expected_gas_cost * 1.05:
                raise Exception(f"Insufficient balance: {eth_balance:.4f} ETH (need ~{expected_gas_cost * 1.05:.4f} ETH)")
            
            # Use prepared metadata
            metadata = prepared.metadata_ipfs if prepared.metadata_ipfs else prepared.metadata_json
            
            # Get base fee and calculate EIP-1559 gas parameters
            latest_block = self.w3.eth.get_block('latest')
            base_fee = latest_block['baseFeePerGas']
            max_priority_fee = self.w3.to_wei(1, 'gwei')
            max_fee_per_gas = int(base_fee * 1.2) + max_priority_fee
            
            # Convert salt to bytes32 format
            salt_bytes = bytes.fromhex(prepared.salt[2:]) if prepared.salt.startswith('0x') else bytes.fromhex(prepared.salt)
            
            # Build transaction
            function_call = self.factory_contract.functions.deployCoin(
                request.token_name, 
                request.token_symbol, 
                metadata, 
                salt_bytes
            )
            
            gas_limit = self.gas_limit
            
            # Get nonce with proper locking
            async with self.nonce_lock:
                current_time = time.time()
                if self.last_nonce is not None and (current_time - self.last_nonce_time) < 5:
                    nonce = self.last_nonce + 1
                else:
                    nonce = self.w3.eth.get_transaction_count(self.deployer_address, 'pending')
                self.last_nonce = nonce
                self.last_nonce_time = current_time
            
            print(f"⛽ EIP-1559 Gas: Base fee: {base_fee / 1e9:.2f} gwei, Priority: {max_priority_fee / 1e9:.2f} gwei")
            print(f"🔢 Nonce: {nonce}")
            print(f"🧂 Using salt: {prepared.salt}")
            
            # Build transaction with EIP-1559 parameters
            tx = function_call.build_transaction({
                'from': self.deployer_address, 'value': 0, 'gas': gas_limit,
                'maxFeePerGas': max_fee_per_gas, 'maxPriorityFeePerGas': max_priority_fee,
                'nonce': nonce, 'chainId': self.w3.eth.chain_id, 'type': 2
            })
            
            signed_tx = self.account.sign_transaction(tx)
            tx_hash = self.w3.eth.send_raw_transaction(signed_tx.rawTransaction)
            tx_hash_hex = tx_hash.hex()
            
            print(f"📝 Transaction sent: {tx_hash_hex}")
            print("⏳ Waiting for confirmation...")
            receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=300)
            
            if receipt['status'] == 1:
                token_address = self._extract_token_address_from_receipt(receipt)
                
                # Verify predicted address matches actual address
                if token_address and token_address.lower() == prepared.predicted_address.lower():
                    print(f"✅ SUCCESS! Token deployed at predicted address: {token_address}")
                    print(f"🎯 Address prediction was correct!")
                else:
                    print(f"⚠️  Token deployed but address mismatch:")
                    print(f"   Predicted: {prepared.predicted_address}")
                    print(f"   Actual: {token_address}")
                
                return True, tx_hash_hex, token_address
            else:
                print("❌ Transaction failed!")
                return False, tx_hash_hex, None
                
        except Exception as e:
            print(f"❌ Deployment failed: {e}")
            self.logger.error(f"Deployment failed for {request.username}: {e}")
            return False, None, None

async def main():
    """Example usage of the ContractDeployer"""
    try:
        deployer = ContractDeployer()
        
        # Example deployment request
        test_request = DeploymentRequest(
            tweet_id='test_deploy_001',
            username='my_test_user',
            token_name='My Test Token',
            token_symbol='MTT',
            tweet_url='https://example.com',
            image_url=None  # Optional: 'https://path/to/image.png'
        )
        
        print(f"\n🔧 Preparing deployment: {test_request.token_name} ({test_request.token_symbol})")
        
        # Prepare deployment (generate salt, upload metadata, etc.)
        prepared = await deployer.prepare_deploy(test_request)
        
        print(f"\n🎯 DEPLOYMENT READY!")
        print(f"   Token Name: {test_request.token_name}")
        print(f"   Token Symbol: {test_request.token_symbol}")
        print(f"   Predicted Address: {prepared.predicted_address}")
        print(f"   Creator: @{test_request.username}")
        print(f"   Social Link: {test_request.tweet_url}")
        if prepared.image_ipfs:
            print(f"   Image IPFS: {prepared.image_ipfs}")
        
        # Confirmation prompt
        confirm = input("\n⚠️  This will deploy a real token to the network! Continue? (y/N): ")
        if confirm.lower() != 'y':
            print("❌ Deployment cancelled")
            return
            
        # Deploy the prepared token
        success, tx_hash, token_address = await deployer.deploy_token(prepared)
        
        if success:
            print("\n🎉 DEPLOYMENT SUCCESSFUL!")
            print(f"   Token Address: {token_address}")
            print(f"   Transaction Hash: {tx_hash}")
            print(f"   Etherscan: https://etherscan.io/tx/{tx_hash}")
            print(f"   DexScreener: https://dexscreener.com/ethereum/{token_address}")
        else:
            print("\n❌ DEPLOYMENT FAILED.")
    
    except ValueError as e:
        print(f"\n❌ CONFIGURATION ERROR: {e}")
        print("   Please ensure you have a .env file with all required variables.")

if __name__ == "__main__":
    asyncio.run(main())
