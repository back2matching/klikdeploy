#!/usr/bin/env python3
"""
Klik Finance Twitter Token Deployer
Deploy tokens when users tag the bot on Twitter - like @launchcoin on Solana!

Usage ($ SYMBOL REQUIRED):
  Tweet: "@DeployOnKlik $MEME" 
  Reply with image: "@DeployOnKlik $MEME - MemeCoin" (uses parent tweet's image)
  Invalid: "@DeployOnKlik MEME" (missing $ - will be ignored)
  Result: Creates token on Klik Finance with social links and images
"""

import asyncio
import os
import json
import time
import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import logging
from asyncio import Queue, Lock

# Web3 and blockchain
from web3 import Web3
from eth_account import Account

# Environment and HTTP
from dotenv import load_dotenv
import aiohttp
import requests

# Database for tracking
import sqlite3
from dataclasses import dataclass

# For address calculation
from eth_hash.auto import keccak
from eth_utils import to_checksum_address

# Twitter monitoring
from twitter_monitor import TwitterMonitor

# Configure SQLite to handle datetime properly for Python 3.12+
sqlite3.register_adapter(datetime, lambda dt: dt.isoformat())
sqlite3.register_converter("timestamp", lambda b: datetime.fromisoformat(b.decode()))

# For image handling
from io import BytesIO
import base64

@dataclass
class DeploymentRequest:
    """Represents a token deployment request"""
    tweet_id: str
    username: str
    token_name: str
    token_symbol: str
    requested_at: datetime
    tweet_url: str  # URL of the tweet that triggered deployment
    parent_tweet_id: Optional[str] = None  # If this is a reply
    image_url: Optional[str] = None  # Image from parent tweet
    deployed_at: Optional[datetime] = None
    tx_hash: Optional[str] = None
    token_address: Optional[str] = None
    status: str = "pending"  # pending, deploying, success, failed
    follower_count: int = 0  # Track follower count for rate limits
    salt: Optional[str] = None  # Pre-generated salt for CREATE2
    predicted_address: Optional[str] = None  # Predicted contract address

class KlikTokenDeployer:
    """Twitter-triggered token deployer for Klik Finance"""
    
    def __init__(self):
        """Initialize the deployer"""
        load_dotenv()
        self._setup_logging()
        self._load_config()
        self._setup_web3()
        self._setup_database()
        
        # Rate limiting
        self.deployment_history = []
        self.user_deployments = {}
        
        # Queue system for deployments
        self.deployment_queue = Queue(maxsize=10)  # Max 10 pending deployments
        self.deployment_lock = Lock()  # For critical sections
        self.active_deployments = {}  # Track active deployments by user
        self.nonce_lock = Lock()  # Separate lock for nonce management
        self.last_nonce = None
        self.last_nonce_time = 0
        
        print("🚀 KLIK FINANCE TWITTER DEPLOYER v2.0")
        print("=" * 50)
        print("💰 Deploy tokens for FREE via Twitter mentions")
        print("🖼️  Auto-attach images from parent tweets")
        print("🔗 Auto-link to deployment tweet")
        print("📦 Queue System: ENABLED (max 10 pending)")
        
        # Show balance breakdown
        total_balance = self.get_eth_balance()
        user_deposits = self.get_total_user_deposits()
        available_balance = self.get_available_balance()
        
        print(f"💰 Total Balance: {total_balance:.4f} ETH")
        print(f"   • User deposits: {user_deposits:.4f} ETH (protected)")
        print(f"   • Available for bot: {available_balance:.4f} ETH")
        
        # CRITICAL: Verify bot username is set correctly
        print(f"🏷️  Bot username: @{self.bot_username}")
        if self.bot_username.lower() == 'deployonklik':
            print("⚠️  WARNING: Using production username 'DeployOnKlik'")
        else:
            print(f"🧪 TEST MODE: Using test username '@{self.bot_username}'")
            print("   Remember to change BOT_USERNAME to 'DeployOnKlik' for production!")
        
        # Check Twitter reply capability
        twitter_keys = [
            os.getenv('TWITTER_API_KEY'),
            os.getenv('TWITTER_API_SECRET'),
            os.getenv('TWITTER_ACCESS_TOKEN'),
            os.getenv('TWITTER_ACCESS_TOKEN_SECRET')
        ]
        if all(twitter_keys):
            print("✅ Twitter replies: ENABLED")
        else:
            print("⚠️  Twitter replies: DISABLED")
        
        # Check Telegram notification capability
        telegram_enabled = os.getenv('TELEGRAM_NOTIFICATIONS_ENABLED', 'false').lower() == 'true'
        if telegram_enabled:
            print("✅ Telegram notifications: ENABLED")
            if self.telegram_channel_id:
                print(f"   → Posting to: {self.telegram_channel_id}")
        else:
            print("📴 Telegram notifications: DISABLED (Twitter only)")
            
        print("=" * 50)
    
    def _setup_logging(self):
        """Setup logging"""
        os.makedirs('logs', exist_ok=True)
        
        self.logger = logging.getLogger('klik_deployer')
        self.logger.setLevel(logging.DEBUG)
        
        file_handler = logging.FileHandler('logs/deployer.log', encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)
        
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        
        # Add debug handler for media extraction
        if os.getenv('DEBUG_MEDIA', 'false').lower() == 'true':
            console_handler.setLevel(logging.DEBUG)
        
        formatter = logging.Formatter(
            '%(asctime)s | %(levelname)s | %(message)s'
        )
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)
        
        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)
    
    def _load_config(self):
        """Load configuration from environment"""
        required_vars = [
            'PRIVATE_KEY', 'ALCHEMY_RPC_URL', 'KLIK_FACTORY_ADDRESS',
            'TELEGRAM_BOT_TOKEN', 'TELEGRAM_CHANNEL_ID'
        ]
        
        missing = [var for var in required_vars if not os.getenv(var)]
        if missing:
            raise ValueError(f"Missing required environment variables: {missing}")
        
        self.private_key = os.getenv('PRIVATE_KEY')
        self.rpc_url = os.getenv('ALCHEMY_RPC_URL')
        self.factory_address = os.getenv('KLIK_FACTORY_ADDRESS')
        self.telegram_bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
        self.telegram_channel_id = os.getenv('TELEGRAM_CHANNEL_ID')
        
        # Optional configs
        self.bot_username = os.getenv('BOT_USERNAME', 'DeployOnKlik')
        self.max_gas_price_gwei = int(os.getenv('MAX_GAS_PRICE_GWEI', '50'))
        self.gas_limit = int(os.getenv('GAS_LIMIT', '6000000'))
        self.max_deploys_per_hour = int(os.getenv('MAX_DEPLOYS_PER_HOUR', '10'))
        self.max_deploys_per_user_per_day = int(os.getenv('MAX_DEPLOYS_PER_USER_PER_DAY', '3'))
        self.cooldown_minutes = int(os.getenv('COOLDOWN_MINUTES', '5'))
        self.min_follower_count = int(os.getenv('MIN_FOLLOWER_COUNT', '100'))
        
        # IPFS service config
        self.pinata_api_key = os.getenv('PINATA_API_KEY')
        self.pinata_secret_key = os.getenv('PINATA_SECRET_KEY')
        self.web3_storage_token = os.getenv('WEB3_STORAGE_TOKEN')
    
    def _setup_web3(self):
        """Setup Web3 connection"""
        self.w3 = Web3(Web3.HTTPProvider(self.rpc_url))
        
        if not self.w3.is_connected():
            raise ConnectionError("Failed to connect to Ethereum network")
        
        # Setup account
        self.account = Account.from_key(self.private_key)
        self.deployer_address = self.account.address
        
        # Factory contract ABI (updated for new deployCoin with salt)
        factory_abi = [
            {
                # Old 3-parameter version (kept for backwards compatibility)
            "inputs": [
                {"name": "_name", "type": "string"},
                {"name": "_symbol", "type": "string"}, 
                {"name": "_metadata", "type": "string"}
            ],
            "name": "deployCoin",
            "outputs": [],
            "stateMutability": "payable",
            "type": "function"
            },
            {
                # New 4-parameter version with salt (for 0x69 addresses)
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
        
        print(f"✅ Connected to Ethereum (Chain ID: {self.w3.eth.chain_id})")
        print(f"🏭 Using Klik Factory: {self.factory_address}")
    
    def _setup_database(self):
        """Setup SQLite database for tracking deployments"""
        self.db_path = 'deployments.db'
        
        with sqlite3.connect(self.db_path, detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES) as conn:
            # Original deployments table
            conn.execute('''
                CREATE TABLE IF NOT EXISTS deployments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tweet_id TEXT UNIQUE,
                    username TEXT,
                    token_name TEXT,
                    token_symbol TEXT,
                    requested_at TIMESTAMP,
                    deployed_at TIMESTAMP,
                    tx_hash TEXT,
                    token_address TEXT,
                    status TEXT DEFAULT 'pending',
                    tweet_url TEXT,
                    parent_tweet_id TEXT,
                    image_url TEXT,
                    image_ipfs TEXT,
                    salt TEXT,
                    predicted_address TEXT
                )
            ''')
            
            # New user accounts table
            conn.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    twitter_username TEXT UNIQUE,
                    eth_address TEXT,
                    balance REAL DEFAULT 0,
                    is_holder BOOLEAN DEFAULT FALSE,
                    holder_balance REAL DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Deposits tracking
            conn.execute('''
                CREATE TABLE IF NOT EXISTS deposits (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    twitter_username TEXT,
                    amount REAL,
                    tx_hash TEXT UNIQUE,
                    from_address TEXT,
                    confirmed BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Daily limits tracking
            conn.execute('''
                CREATE TABLE IF NOT EXISTS daily_limits (
                    username TEXT,
                    date DATE,
                    free_deploys INTEGER DEFAULT 0,
                    holder_deploys INTEGER DEFAULT 0,
                    PRIMARY KEY (username, date)
                )
            ''')
            
            conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_username_date 
                ON deployments(username, requested_at)
            ''')
            
            # Add new columns if they don't exist (for existing databases)
            try:
                conn.execute('ALTER TABLE deployments ADD COLUMN salt TEXT')
            except sqlite3.OperationalError:
                pass  # Column already exists
            
            try:
                conn.execute('ALTER TABLE deployments ADD COLUMN predicted_address TEXT')
            except sqlite3.OperationalError:
                pass  # Column already exists
        
        print("✅ Database initialized with user accounts")
    
    def get_eth_balance(self) -> float:
        """Get current ETH balance"""
        balance_wei = self.w3.eth.get_balance(self.deployer_address)
        return float(self.w3.from_wei(balance_wei, 'ether'))
    
    def get_total_user_deposits(self) -> float:
        """Get total balance of all user deposits"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT COALESCE(SUM(balance), 0) FROM users WHERE balance > 0"
            )
            total = cursor.fetchone()[0]
            return float(total)
    
    def get_available_balance(self) -> float:
        """Get balance available for bot operations (excludes user deposits)"""
        total_balance = self.get_eth_balance()
        user_deposits = self.get_total_user_deposits()
        
        # Available = total - user deposits (with safety buffer)
        available = total_balance - (user_deposits * 1.05)  # 5% buffer for gas fluctuations
        
        return max(0, available)  # Never negative
    
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
            print(f"   🔍 Total attempts: {data['total_attempts']:,}")
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
    
    def parse_tweet_for_token(self, tweet_text: str) -> Optional[Dict[str, str]]:
        """Parse tweet text to extract token name/symbol
        
        REQUIRES $ symbol to reduce spam/clutter
        
        Examples:
        "@DeployOnKlik $MEME" -> {symbol: "MEME", name: "MEME"}
        "@DeployOnKlik $DOG - DogeCoin" -> {symbol: "DOG", name: "DogeCoin"}
        "@DeployOnKlik PEPE" -> None (no $ symbol - rejected)
        """
        # Remove mentions and clean up
        text = tweet_text.strip()
        text = re.sub(r'@\w+', '', text).strip()
        
        # REQUIRE $SYMBOL pattern - no $ means no deployment
        symbol_match = re.search(r'\$([a-zA-Z0-9]+)', text)
        
        if not symbol_match:
            # No $ symbol found - reject to reduce clutter
            return None
            
        symbol = symbol_match.group(1).upper()
        
        # Look for name after a dash, but stop at URLs or mentions
        name_match = re.search(r'\$[a-zA-Z0-9]+\s*[-–]\s*([^@\s]+(?:\s+[^@\s]+)*?)(?:\s+https?://|\s+@|\s*$)', text)
        if not name_match:
            # Try simpler pattern without URL/mention check
            name_match = re.search(r'\$[a-zA-Z0-9]+\s*[-–]\s*([^@\n]+?)(?:\s+https?://|\s*$)', text)
        
        if name_match:
            name = name_match.group(1).strip()
            # Remove any trailing URLs that might have been caught
            name = re.sub(r'\s*https?://\S+\s*$', '', name).strip()
        else:
            name = symbol
        
        # Validation
        if not symbol or len(symbol) > 10 or not symbol.replace('_', '').isalnum():
            return None
        
        if not name or len(name) > 30:
            name = symbol
        
        return {
            'symbol': symbol,
            'name': name.title() if name == symbol else name
        }
    
    def check_rate_limits(self, username: str, follower_count: int = 0) -> tuple[bool, str]:
        """Check if user can deploy (rate limiting + gas tiers)"""
        now = datetime.now()
        today = now.date()
        
        # Get current gas price (use the same as preview for consistency)
        current_gas_price = self.w3.eth.gas_price
        current_gas_gwei = float(self.w3.from_wei(current_gas_price, 'gwei'))
        
        # For EIP-1559, calculate max fee for safety checks
        latest_block = self.w3.eth.get_block('latest')
        base_fee = latest_block['baseFeePerGas']
        max_priority_fee = self.w3.to_wei(2, 'gwei')
        max_fee_per_gas = (base_fee * 2) + max_priority_fee
        
        # Use the actual current gas price for cost calculations (same as preview)
        likely_gas_gwei = current_gas_gwei
        
        # Get gas limits from config - updated for new tiers
        free_gas_limit = float(os.getenv('FREE_DEPLOY_GAS_LIMIT', '3'))
        vip_gas_limit = float(os.getenv('VIP_DEPLOY_GAS_LIMIT', '6'))  # VIP FREE up to 6 gwei
        holder_gas_limit = float(os.getenv('HOLDER_MAX_GAS_LIMIT', '15'))  # Reduced from 50 to 15
        
        # Check overall hourly spam protection
        recent_deploys = [
            d for d in self.deployment_history 
            if d > now - timedelta(hours=1)
        ]
        
        if len(recent_deploys) >= self.max_deploys_per_hour:
            return False, f"⏳ System limit reached ({self.max_deploys_per_hour} deploys/hour). Try again later."
        
        # Estimate deployment cost using realistic gas usage
        # Use 6.5M units as typical for Klik factory deployments
        realistic_gas_units = 6_500_000
        # Use current gas price (same as preview) for consistency
        realistic_gas_cost = float(self.w3.from_wei(current_gas_price * realistic_gas_units, 'ether'))
        
        # Debug: Log the values
        self.logger.debug(f"Rate check gas: current_gas={current_gas_gwei:.2f} gwei")
        self.logger.debug(f"Rate check cost: gas_cost={realistic_gas_cost:.4f} ETH for {realistic_gas_units/1e6:.1f}M units")
        
        # Check if user is a holder
        is_holder = self.check_holder_status(username)
        
        # Check if user qualifies for VIP tier (20k+ followers)
        is_vip = follower_count >= 20000
        self.logger.debug(f"User @{username} has {follower_count:,} followers (VIP: {is_vip})")
        
        # Calculate total cost
        # Bot owner doesn't pay fees on their own deployments!
        is_bot_owner = username.lower() == self.bot_username.lower()
        fee = 0 if (is_holder or is_bot_owner) else 0.01  # Holders and bot owner pay no fee
        total_cost = realistic_gas_cost + fee
        
        # Get user balance
        user_balance = self.get_user_balance(username)
        self.logger.debug(f"User @{username} balance: {user_balance:.4f} ETH")
        
        # CRITICAL: Check bot's available balance for free/holder deployments
        available_bot_balance = self.get_available_balance()
        
        # Get today's deployment counts
        with sqlite3.connect(self.db_path) as conn:
            # Get or create daily limits
            cursor = conn.execute('''
                SELECT free_deploys, holder_deploys 
                FROM daily_limits 
                WHERE username = ? AND date = ?
            ''', (username.lower(), today))
            
            daily_stats = cursor.fetchone()
            if daily_stats:
                free_deploys_today, holder_deploys_today = daily_stats
            else:
                free_deploys_today = holder_deploys_today = 0
                conn.execute('''
                    INSERT INTO daily_limits (username, date, free_deploys, holder_deploys)
                    VALUES (?, ?, 0, 0)
                ''', (username.lower(), today))
        
        # Tier 1: Free deployment 
        # Standard users: gas <= 3 gwei AND 1500+ followers
        # VIP users (20k+ followers): gas <= 6 gwei
        gas_limit_for_user = vip_gas_limit if is_vip else free_gas_limit
        
        # Minimum follower count for FREE deployments
        min_followers_for_free = int(os.getenv('MIN_FOLLOWER_COUNT', '1500'))
        
        if likely_gas_gwei <= gas_limit_for_user:
            # Check follower count for free deployments
            if follower_count < min_followers_for_free and not is_holder:
                # Not enough followers for free deployment, check if they can pay
                if user_balance >= total_cost:
                    return True, f"💰 Pay-per-deploy (cost: {total_cost:.4f} ETH, balance: {user_balance:.4f} ETH)"
                else:
                    return False, f"""❌ Not enough followers for free deployment!

You have: {follower_count:,} followers
Need: {min_followers_for_free:,} followers for free deploys

💰 Or deposit {total_cost:.4f} ETH to deploy now:
t.me/DeployOnKlik"""
            
            # SAFETY: Check if bot has enough balance for free deployments
            if available_bot_balance < realistic_gas_cost * 1.1:
                # Bot doesn't have enough balance for free deployment
                if user_balance >= total_cost:
                    return True, f"💰 Pay-per-deploy (bot low on funds - cost: {total_cost:.4f} ETH, your balance: {user_balance:.4f} ETH)"
                else:
                    return False, f"""❌ Bot balance too low for free deployment!

Bot needs more ETH for free deploys.
Deposit to deploy now: t.me/DeployOnKlik"""
            
            if is_holder and holder_deploys_today < 2:  # Changed from 5 to 2
                return True, f"✅ Holder deployment allowed (gas: {likely_gas_gwei:.1f} gwei, {holder_deploys_today}/2 used today)"
            elif free_deploys_today < 1:
                if is_vip and likely_gas_gwei > free_gas_limit:
                    return True, f"✅ Free deployment allowed (gas: {likely_gas_gwei:.1f} gwei, 20k+ followers benefit)"
                else:
                    return True, f"✅ Free deployment allowed (gas: {likely_gas_gwei:.1f} gwei)"
            else:
                return False, f"🚫 Daily free limit reached. Visit t.me/DeployOnKlik for more info!"
        
        # Tier 2: Holder deployment (gas <= 15 gwei)
        if is_holder:
            if likely_gas_gwei > holder_gas_limit:
                return False, f"""❌ Gas too high for holders!

Gas: {likely_gas_gwei:.1f} gwei (limit: {holder_gas_limit:.0f})

Please wait for gas to drop or visit t.me/DeployOnKlik"""
            
            # SAFETY: Check if bot has enough balance for holder deployments
            if available_bot_balance < realistic_gas_cost * 1.1:
                # Bot doesn't have enough balance for holder deployment
                if user_balance >= total_cost:
                    return True, f"💰 Pay-per-deploy (bot low on funds - cost: {total_cost:.4f} ETH, your balance: {user_balance:.4f} ETH)"
                else:
                    return False, f"""❌ Bot balance too low for holder deployment!

Bot needs more ETH for free deploys.
Your balance: {user_balance:.4f} ETH
Deposit more: t.me/DeployOnKlik"""
            
            if holder_deploys_today < 2:  # Changed from 5 to 2
                return True, f"🎯 Holder deployment allowed ({holder_deploys_today}/2 used today, gas: {likely_gas_gwei:.1f} gwei)"
            else:
                return False, f"🎯 Holder daily limit reached (2/2 used). Thank you for supporting $KLIK!"
        
        # Tier 3: Pay per deploy (check balance)
        if user_balance >= total_cost:
            return True, f"💰 Pay-per-deploy (cost: {total_cost:.4f} ETH, balance: {user_balance:.4f} ETH)"
        
        # Cannot deploy - insufficient balance
        return False, f"""❌ Gas too high! ({likely_gas_gwei:.1f} gwei)

Cost: {total_cost:.4f} ETH
Your balance: {user_balance:.4f} ETH

To deploy when gas > 3 gwei:
Visit t.me/DeployOnKlik 💬

Quick & easy deposits!"""
    
    async def upload_image_to_ipfs(self, image_url: str) -> Optional[str]:
        """Download image from URL and upload to IPFS"""
        try:
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
                    self.logger.info(f"Image uploaded to IPFS: {ipfs_hash}")
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
                    self.logger.info(f"Image uploaded to IPFS: {cid}")
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
            if self.pinata_api_key and self.pinata_secret_key:
                url = "https://api.pinata.cloud/pinning/pinJSONToIPFS"
                headers = {
                    "pinata_api_key": self.pinata_api_key,
                    "pinata_secret_api_key": self.pinata_secret_key
                }
                
                response = requests.post(url, json=metadata, headers=headers)
                if response.status_code == 200:
                    return response.json()['IpfsHash']
            
            elif self.web3_storage_token:
                url = "https://api.web3.storage/upload"
                headers = {
                    "Authorization": f"Bearer {self.web3_storage_token}",
                    "Content-Type": "application/json"
                }
                
                response = requests.post(url, json=metadata, headers=headers)
                if response.status_code == 200:
                    return response.json()['cid']
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error uploading metadata to IPFS: {e}")
            return None
    
    async def fetch_parent_tweet_image(self, parent_tweet_id: str) -> Optional[str]:
        """Fetch image from parent tweet (requires Twitter API)
        
        Note: This is a placeholder - you'll need Twitter API v2 access
        """
        # This would require Twitter API integration
        # For now, return None or implement with your Twitter API keys
        self.logger.warning("Twitter API integration needed to fetch parent tweet images")
        return None
    
    async def deploy_token(self, request: DeploymentRequest) -> bool:
        """Deploy a token to Klik Finance"""
        try:
            print(f"\n🚀 Deploying {request.token_name} ({request.token_symbol}) for @{request.username}")
            
            # Get deployment type for tracking
            latest_block = self.w3.eth.get_block('latest')
            base_fee = latest_block['baseFeePerGas']
            priority_fee = self.w3.to_wei(1, 'gwei')
            likely_gas_gwei = float(self.w3.from_wei(base_fee + priority_fee, 'gwei'))
            is_holder = self.check_holder_status(request.username)
            user_balance = self.get_user_balance(request.username)
            
            # Determine deployment type - MUST match rate limit logic!
            gas_limit_for_user = 6 if request.follower_count >= 20000 else 3  # 20k+ followers get 6 gwei limit
            min_followers_for_free = int(os.getenv('MIN_FOLLOWER_COUNT', '1500'))
            
            # Check if qualifies for free deployment
            if likely_gas_gwei <= gas_limit_for_user and request.follower_count >= min_followers_for_free and not is_holder:
                deployment_type = 'free'
            elif is_holder and likely_gas_gwei <= 15:  # Holder gas limit
                deployment_type = 'holder'
            else:
                deployment_type = 'pay-per-deploy'
            

            
            # Check gas price for free tier limit
            if likely_gas_gwei > self.max_gas_price_gwei and deployment_type == 'free':
                raise Exception(f"Gas price too high: {likely_gas_gwei:.1f} gwei (max: {self.max_gas_price_gwei})")
            
            # Check balance - CRITICAL: Use different logic for free vs paid deployments
            total_balance = self.get_eth_balance()
            user_deposits = self.get_total_user_deposits()
            available_balance = self.get_available_balance()
            
            # Use current gas price for balance check (same as preview)
            current_gas_price = self.w3.eth.gas_price
            realistic_gas_units = 6_500_000
            
            # Calculate expected cost (same as preview)
            expected_gas_cost = float(self.w3.from_wei(current_gas_price * realistic_gas_units, 'ether'))
            total_expected = expected_gas_cost
            
            # For EIP-1559, also calculate max possible (for safety)
            latest_block = self.w3.eth.get_block('latest')
            base_fee = latest_block['baseFeePerGas']
            max_priority_fee = self.w3.to_wei(1, 'gwei')
            max_fee_per_gas = int(base_fee * 1.2) + max_priority_fee
            
            # Calculate worst case for logging
            worst_case_fee = float(self.w3.from_wei(max_fee_per_gas * realistic_gas_units, 'ether'))
            total_worst_case = worst_case_fee
            
            # CRITICAL SAFETY CHECK: Different balance requirements based on deployment type
            if deployment_type in ['free', 'holder']:
                # Free/holder deployments MUST NOT touch user deposits
                if available_balance < total_expected * 1.05:
                    self.logger.error(f"SAFETY: Cannot use user deposits for {deployment_type} deployment!")
                    self.logger.error(f"Total balance: {total_balance:.4f}, User deposits: {user_deposits:.4f}, Available: {available_balance:.4f}")
                    raise Exception(f"Insufficient bot balance for {deployment_type} deployment! Bot has {available_balance:.4f} ETH available (excluding {user_deposits:.4f} ETH in user deposits)")
            else:
                # Pay-per-deploy uses total balance (user is paying from their deposit)
                if total_balance < total_expected * 1.05:
                    raise Exception(f"Insufficient balance: {total_balance:.4f} ETH (need ~{total_expected * 1.05:.4f} ETH with buffer, expected cost ~{total_expected:.4f} ETH)")
            
            print(f"💰 Balance check passed:")
            print(f"   • Total: {total_balance:.4f} ETH")
            print(f"   • User deposits: {user_deposits:.4f} ETH")
            print(f"   • Available for bot: {available_balance:.4f} ETH")
            print(f"   • Deployment type: {deployment_type}")
            
            # Prepare metadata
            metadata_obj = {
                "uniqueId": f"{self.deployer_address}-{request.token_name}-{request.token_symbol}-{int(time.time() * 1000)}",
                "name": request.token_name,
                "symbol": request.token_symbol,
                "telegram": "",
                "x": request.tweet_url,  # Always use the deployment tweet URL
                "website": "",
                "image": ""
            }
            
            # Handle image if present
            image_ipfs = None
            if request.image_url:
                print(f"🖼️  Uploading image from parent tweet...")
                image_ipfs = await self.upload_image_to_ipfs(request.image_url)
                if image_ipfs:
                    metadata_obj["image"] = image_ipfs
                    print(f"✅ Image uploaded: {image_ipfs}")
            
            # Try to upload metadata to IPFS
            metadata = None
            if self.pinata_api_key or self.web3_storage_token:
                metadata_ipfs = self.upload_metadata_to_ipfs(metadata_obj)
                if metadata_ipfs:
                    metadata = metadata_ipfs
                    print(f"📦 Metadata uploaded to IPFS: {metadata_ipfs}")
            
            # Fall back to JSON if IPFS fails
            if not metadata:
                metadata = json.dumps(metadata_obj)
            
            # Get base fee and calculate EIP-1559 gas parameters first
            latest_block = self.w3.eth.get_block('latest')
            base_fee = latest_block['baseFeePerGas']
            
            # Priority fee (tip) - 1 gwei minimal for mainnet
            max_priority_fee = self.w3.to_wei(1, 'gwei')
            
            # Max fee = (1.2 * base fee) + priority fee
            # This allows for base fee to increase by 20% before tx gets stuck
            max_fee_per_gas = int(base_fee * 1.2) + max_priority_fee
            
            # Use pre-generated salt if available (from manual deployment preview)
            if request.salt:
                # Convert hex string to bytes32
                salt = bytes.fromhex(request.salt[2:]) if request.salt.startswith('0x') else bytes.fromhex(request.salt)
                print(f"🧂 Using pre-generated vanity salt: {request.salt}")
                if request.predicted_address:
                    print(f"🎯 Expected address: {request.predicted_address}")
            else:
                # Generate a random salt for CREATE2 (automated deployments)
                salt_input = f"{request.token_name}-{request.token_symbol}-{int(time.time() * 1000)}-{os.urandom(16).hex()}"
                salt = self.w3.keccak(text=salt_input)[:32]  # bytes32
            
            # Build transaction with the new 4-parameter deployCoin function
            function_call = self.factory_contract.functions.deployCoin(
                request.token_name,
                request.token_symbol,
                metadata,
                salt
            )
            
            # Estimate gas
            try:
                gas_estimate = function_call.estimate_gas({
                    'from': self.deployer_address,
                    'value': 0
                })
                
                # Add minimal buffer based on gas estimate size
                if gas_estimate > 4_000_000:
                    # For high gas estimates, use minimal buffer (5%)
                    gas_limit = int(gas_estimate * 1.05)
                    buffer_pct = 5
                else:
                    # For normal estimates, use 10% buffer
                    gas_limit = int(gas_estimate * 1.10)
                    buffer_pct = 10
                
                # Warn if gas usage is very high
                if gas_estimate > 6_000_000:
                    print(f"⚠️  WARNING: High gas requirement detected: {gas_estimate:,} units")
                    print(f"   Using {gas_limit:,} units with {buffer_pct}% safety buffer")
                    
                    # Double check our balance can cover this
                    worst_case_cost = float(self.w3.from_wei(max_fee_per_gas * gas_limit, 'ether'))
                    expected_cost = float(self.w3.from_wei(current_gas_price * gas_limit, 'ether'))
                    
                    # Use appropriate balance check based on deployment type
                    if deployment_type in ['free', 'holder']:
                        if available_balance < expected_cost * 1.05:
                            raise Exception(f"Insufficient bot balance for high gas deployment: need {expected_cost * 1.05:.4f} ETH (available: {available_balance:.4f} ETH)")
                    else:
                        if total_balance < expected_cost * 1.05:
                            raise Exception(f"Insufficient balance for high gas deployment: need {expected_cost * 1.05:.4f} ETH with buffer (expected {expected_cost:.4f} ETH)")
                
                # If estimate is way higher than our configured limit, log it
                if gas_estimate > self.gas_limit:
                    self.logger.warning(f"Gas estimate {gas_estimate} exceeds configured limit {self.gas_limit}")
                    
            except Exception as e:
                # If estimation fails, try a higher default
                self.logger.warning(f"Gas estimation failed: {e}")
                print(f"⚠️  Gas estimation failed, using high default of {self.gas_limit:,} units")
                gas_limit = self.gas_limit
                
                # For safety, simulate the transaction first
                try:
                    print("🔍 Simulating transaction...")
                    result = self.w3.eth.call({
                        'from': self.deployer_address,
                        'to': self.factory_address,
                        'value': 0,
                        'data': function_call._encode_transaction_data()
                    })
                    print("✅ Simulation successful")
                except Exception as sim_e:
                    print(f"❌ Simulation failed: {sim_e}")
                    if "out of gas" in str(sim_e).lower():
                        raise Exception(f"Transaction will fail - insufficient gas. Consider increasing GAS_LIMIT in .env")
                    raise sim_e
            
            # Get nonce with proper locking to prevent conflicts
            async with self.nonce_lock:
                current_time = time.time()
                
                # If we have a recent nonce (within 5 seconds), increment it
                if self.last_nonce is not None and (current_time - self.last_nonce_time) < 5:
                    nonce = self.last_nonce + 1
                    self.logger.info(f"Using incremented nonce: {nonce}")
                else:
                    # Get fresh nonce from network
                    nonce = self.w3.eth.get_transaction_count(self.deployer_address, 'pending')
                    self.logger.info(f"Got fresh nonce from network: {nonce}")
                
                # Store for next deployment
                self.last_nonce = nonce
                self.last_nonce_time = current_time
            
            print(f"⛽ EIP-1559 Gas: Base fee: {base_fee / 1e9:.2f} gwei, Priority: {max_priority_fee / 1e9:.2f} gwei")
            print(f"   Max fee: {max_fee_per_gas / 1e9:.2f} gwei (allows for 1.2x base fee increase)")
            print(f"🔢 Nonce: {nonce}")
            
            # Build transaction with EIP-1559 parameters
            tx = function_call.build_transaction({
                'from': self.deployer_address,
                'value': 0,  # No initial purchase
                'gas': gas_limit,
                'maxFeePerGas': max_fee_per_gas,
                'maxPriorityFeePerGas': max_priority_fee,
                'nonce': nonce,
                'chainId': self.w3.eth.chain_id,
                'type': 2  # EIP-1559 transaction
            })
            
            # Update cost display to use max fee
            max_cost = float(self.w3.from_wei(max_fee_per_gas * gas_limit, 'ether'))
            likely_cost = float(self.w3.from_wei((base_fee + max_priority_fee) * gas_limit, 'ether'))
            
            print(f"💸 Gas: {gas_limit:,} units @ ~{(base_fee + max_priority_fee) / 1e9:.1f} gwei")
            print(f"   Likely cost: ~{likely_cost:.4f} ETH")
            print(f"   Max cost: {max_cost:.4f} ETH (if gas spikes)")
            
            # Sign and send with retry logic
            max_retries = 3
            retry_count = 0
            
            while retry_count < max_retries:
                try:
                    signed_tx = self.account.sign_transaction(tx)
                    tx_hash = self.w3.eth.send_raw_transaction(signed_tx.rawTransaction)
                    tx_hash_hex = tx_hash.hex()
                    
                    print(f"📤 Transaction sent: {tx_hash_hex}")
                    print(f"🔗 Etherscan: https://etherscan.io/tx/{tx_hash_hex}")
                    
                    # Update request
                    request.tx_hash = tx_hash_hex
                    request.status = "deploying"
                    self._update_deployment_in_db(request)
                    
                    # Wait for confirmation
                    print("⏳ Waiting for confirmation...")
                    receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=300)  # Increased to 5 minutes
                    break  # Success, exit retry loop
                    
                except Exception as e:
                    error_msg = str(e).lower()
                    
                    # Check if it's a nonce error
                    if 'nonce too low' in error_msg or 'already known' in error_msg:
                        retry_count += 1
                        if retry_count < max_retries:
                            print(f"⚠️  Nonce conflict detected, retrying ({retry_count}/{max_retries})...")
                            
                            # Force refresh nonce
                            async with self.nonce_lock:
                                nonce = self.w3.eth.get_transaction_count(self.deployer_address, 'pending')
                                self.last_nonce = nonce
                                self.last_nonce_time = time.time()
                            
                            # Rebuild transaction with new nonce
                            tx['nonce'] = nonce
                            await asyncio.sleep(1)  # Brief delay before retry
                            continue
                    
                    # For other errors, don't retry
                    raise e
            
            if receipt['status'] == 1:
                # Extract token address from logs
                token_address = self._extract_token_address_from_receipt(receipt)
                
                request.deployed_at = datetime.now()
                request.token_address = token_address
                request.status = "success"
                
                print(f"✅ SUCCESS! Token deployed: {token_address}")
                
                # Verify predicted address if we pre-generated it
                if request.predicted_address:
                    if token_address and token_address.lower() == request.predicted_address.lower():
                        print(f"🎯 ADDRESS PREDICTION VERIFIED! Token deployed at expected address")
                    else:
                        print(f"⚠️  WARNING: Address mismatch!")
                        print(f"   Expected: {request.predicted_address}")
                        print(f"   Actual: {token_address}")
                
                print(f"📈 DexScreener: https://dexscreener.com/ethereum/{token_address}")
                print(f"🌐 Klik Finance: https://klik.finance/")
                
                # Update tracking
                self.deployment_history.append(datetime.now())
                self.user_deployments[request.username.lower()] = datetime.now()
                
                # Update daily limits and balance
                actual_gas_used = receipt['gasUsed'] * receipt['effectiveGasPrice']
                actual_gas_cost = float(self.w3.from_wei(actual_gas_used, 'ether'))
                
                with sqlite3.connect(self.db_path) as conn:
                    today = datetime.now().date()
                    
                    # Ensure daily_limits row exists before updating
                    conn.execute('''
                        INSERT OR IGNORE INTO daily_limits (username, date, free_deploys, holder_deploys)
                        VALUES (?, ?, 0, 0)
                    ''', (request.username.lower(), today))
                    
                    if deployment_type == 'free':
                        conn.execute('''
                            UPDATE daily_limits 
                            SET free_deploys = free_deploys + 1
                            WHERE username = ? AND date = ?
                        ''', (request.username.lower(), today))
                    elif deployment_type == 'holder':
                        conn.execute('''
                            UPDATE daily_limits 
                            SET holder_deploys = holder_deploys + 1
                            WHERE username = ? AND date = ?
                        ''', (request.username.lower(), today))
                    elif deployment_type == 'pay-per-deploy':
                        # Deduct from balance with atomic update
                        fee = 0 if is_holder else 0.01  # Holders pay no fee!
                        total_deducted = actual_gas_cost + fee
                        
                        # Use atomic balance update to prevent race conditions
                        cursor = conn.execute('''
                            UPDATE users 
                            SET balance = balance - ?
                            WHERE LOWER(twitter_username) = LOWER(?) AND balance >= ?
                            RETURNING balance
                        ''', (total_deducted, request.username, total_deducted))
                        
                        result = cursor.fetchone()
                        if result is None:
                            # Balance was insufficient (race condition)
                            self.logger.error(f"Race condition: User @{request.username} balance insufficient after deployment")
                        else:
                            new_balance = result[0]
                            if fee > 0:
                                print(f"💰 Deducted {total_deducted:.4f} ETH from balance (gas: {actual_gas_cost:.4f}, fee: {fee:.4f})")
                            else:
                                print(f"🎯 Deducted {actual_gas_cost:.4f} ETH from holder balance (gas only, NO FEES!)")
                            print(f"   New balance: {new_balance:.4f} ETH")
                            
                            # Log balance change for audit trail
                            self.logger.info(f"Balance deduction: @{request.username} -{total_deducted:.4f} ETH (new balance: {new_balance:.4f})")
                
                # Store image IPFS if we have it
                if image_ipfs:
                    with sqlite3.connect(self.db_path, detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES) as conn:
                        conn.execute(
                            "UPDATE deployments SET image_ipfs = ? WHERE tweet_id = ?",
                            (image_ipfs, request.tweet_id)
                        )
                
                return True
            else:
                request.status = "failed"
                print("❌ Transaction failed!")
                return False
                
        except Exception as e:
            request.status = "failed"
            print(f"❌ Deployment failed: {e}")
            self.logger.error(f"Deployment failed for {request.username}: {e}")
            return False
        finally:
            self._update_deployment_in_db(request)
    
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
    
    def _save_deployment_to_db(self, request: DeploymentRequest):
        """Save deployment request to database"""
        with sqlite3.connect(self.db_path, detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES) as conn:
            conn.execute('''
                INSERT OR REPLACE INTO deployments 
                (tweet_id, username, token_name, token_symbol, requested_at, 
                 deployed_at, tx_hash, token_address, status, tweet_url, 
                 parent_tweet_id, image_url, salt, predicted_address)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                request.tweet_id, request.username.lower(), request.token_name, request.token_symbol,
                request.requested_at, request.deployed_at, request.tx_hash, request.token_address, 
                request.status, request.tweet_url, request.parent_tweet_id, request.image_url,
                request.salt, request.predicted_address
            ))
    
    def _update_deployment_in_db(self, request: DeploymentRequest):
        """Update deployment in database"""
        with sqlite3.connect(self.db_path, detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES) as conn:
            conn.execute('''
                UPDATE deployments 
                SET deployed_at=?, tx_hash=?, token_address=?, status=?
                WHERE tweet_id=?
            ''', (request.deployed_at, request.tx_hash, request.token_address, request.status, request.tweet_id))
    
    def send_telegram_notification(self, request: DeploymentRequest, success: bool):
        """Send Telegram notification about deployment"""
        # Check if Telegram notifications are enabled
        if os.getenv('TELEGRAM_NOTIFICATIONS_ENABLED', 'false').lower() != 'true':
            self.logger.info(f"Telegram notifications disabled (skipping for {request.token_symbol})")
            return
            
        try:
            if success:
                message = f"""🎉 <b>TOKEN LAUNCHED VIA TWITTER!</b>

💰 <b>{request.token_name}</b> ({request.token_symbol})
📍 <code>{request.token_address}</code>

📈 <a href="https://dexscreener.com/ethereum/{request.token_address}">DexScreener</a>
🌐 <a href="https://klik.finance/">Klik Finance</a>
🔗 <a href="https://etherscan.io/tx/{request.tx_hash}">Transaction</a>
🐦 <a href="{request.tweet_url}">Tweet</a>

⚡ <b>Deployed in seconds from Twitter!</b>"""
            else:
                message = f"""❌ <b>DEPLOYMENT FAILED</b>

💰 {request.token_name} ({request.token_symbol})
📋 Status: {request.status}
🐦 <a href="{request.tweet_url}">Tweet</a>"""
            
            # Support both @username and numeric channel IDs
            channel_id = self.telegram_channel_id
            if not channel_id:
                print("⚠️  No Telegram channel configured")
                self.logger.warning("TELEGRAM_CHANNEL_ID not configured")
                return
            
            url = f"https://api.telegram.org/bot{self.telegram_bot_token}/sendMessage"
            data = {
                'chat_id': channel_id,  # Works with both @username and numeric IDs
                'text': message,
                'parse_mode': 'HTML',
                'disable_web_page_preview': False
            }
            
            response = requests.post(url, json=data, timeout=10)
            if response.status_code == 200:
                result = response.json()
                if result.get('ok'):
                    print(f"📱 Telegram notification sent successfully to {channel_id}")
                    self.logger.info(f"Telegram notification sent for {request.token_symbol}")
                else:
                    error_msg = result.get('description', 'Unknown error')
                    print(f"⚠️  Telegram API error: {error_msg}")
                    self.logger.error(f"Telegram API error: {error_msg}")
                    
                    # Log specific error types
                    if "bot was blocked" in error_msg.lower():
                        print("   ➡️  Bot was blocked by the channel")
                    elif "chat not found" in error_msg.lower():
                        print("   ➡️  Channel not found or bot not added")
                        print(f"   ➡️  Make sure bot is admin in {channel_id}")
                    elif "bot is not a member" in error_msg.lower():
                        print("   ➡️  Bot is not a member of the channel")
                        print("   ➡️  Add @DeployOnKlikBot as admin to @DeployOnKlik")
                    elif "not enough rights" in error_msg.lower():
                        print("   ➡️  Bot lacks permission to post messages")
                        print("   ➡️  Give bot 'Post Messages' permission in channel settings")
            else:
                print(f"⚠️  Telegram HTTP error: {response.status_code}")
                self.logger.error(f"Telegram HTTP error: {response.status_code} - {response.text}")
                
        except requests.exceptions.Timeout:
            print("⚠️  Telegram notification timeout (10s)")
            self.logger.error("Telegram notification timeout")
        except requests.exceptions.ConnectionError:
            print("⚠️  Failed to connect to Telegram servers")
            self.logger.error("Failed to connect to Telegram API")
        except Exception as e:
            print(f"⚠️  Telegram notification error: {type(e).__name__}: {e}")
            self.logger.error(f"Telegram notification error: {e}", exc_info=True)
    
    async def send_twitter_reply(self, request: DeploymentRequest, success: bool) -> bool:
        """Reply using Twitter's free API with OAuth 1.0a (required for posting)
        
        Twitter requires user context auth to post tweets - Bearer Token is read-only
        """
        try:
            # SAFETY: Check if this is from the bot itself
            if request.username.lower() == self.bot_username.lower():
                # Check if this is the first deployment ever
                with sqlite3.connect(self.db_path) as conn:
                    cursor = conn.execute(
                        "SELECT COUNT(*) FROM deployments WHERE status = 'success'"
                    )
                    successful_deploys = cursor.fetchone()[0]
                
                if successful_deploys > 0:
                    # Skip replying to own tweets after first deployment
                    self.logger.warning(f"Skipping reply to own tweet from @{request.username}")
                    return False
                else:
                    # Allow reply to first deployment
                    self.logger.info("First deployment - allowing reply to bot's own tweet")
            
            # Check if we have all OAuth 1.0a credentials
            api_key = os.getenv('TWITTER_API_KEY')
            api_secret = os.getenv('TWITTER_API_SECRET')
            access_token = os.getenv('TWITTER_ACCESS_TOKEN')
            access_token_secret = os.getenv('TWITTER_ACCESS_TOKEN_SECRET')
            
            if not all([api_key, api_secret, access_token, access_token_secret]):
                self.logger.warning("Twitter OAuth credentials not complete - skipping reply")
                print("ℹ️  Skipping Twitter reply - need all 4 OAuth keys (see .env)")
                return False
            
            # Prepare the reply message
            if success:
                reply_text = f"""@{request.username} Your ${request.token_symbol} is live! 🎉

📈 dexscreener.com/ethereum/{request.token_address}
🌐 klik.finance"""
            elif hasattr(request, 'status') and request.status == 'cancelled':
                # User cancelled deployment - don't say invalid format!
                reply_text = f"""@{request.username} Deployment cancelled.

Ready when you are! 💪"""
            elif hasattr(request, 'status') and request.status == 'failed':
                # Deployment failed - be helpful
                reply_text = f"""@{request.username} Deployment failed!

Check balance or try when gas is lower.
Info: t.me/DeployOnKlik"""
            else:
                # This should only happen if token parsing failed
                reply_text = f"""@{request.username} Invalid format!

Need: @{self.bot_username} $SYMBOL
You sent: Missing $"""
            
            # Use tweepy for OAuth 1.0a authentication
            import tweepy
            
            # Create OAuth handler
            auth = tweepy.OAuth1UserHandler(api_key, api_secret, access_token, access_token_secret)
            api = tweepy.API(auth)
            
            # Post the reply
            try:
                # For API v2 with tweepy v4+
                client = tweepy.Client(
                    consumer_key=api_key,
                    consumer_secret=api_secret,
                    access_token=access_token,
                    access_token_secret=access_token_secret
                )
                
                response = client.create_tweet(
                    text=reply_text,
                    in_reply_to_tweet_id=request.tweet_id
                )
                
                if response.data:
                    self.logger.info(f"✅ Reply sent! Tweet ID: {response.data['id']}")
                    return True
                else:
                    self.logger.error(f"Failed to send reply: No response data")
                    return False
                    
            except tweepy.TooManyRequests:
                self.logger.error("Rate limit reached for Twitter replies")
                return False
            except Exception as e:
                self.logger.error(f"Tweepy error: {e}")
                return False
                
        except Exception as e:
            self.logger.error(f"Error sending Twitter reply: {e}")
            return False
    
    async def _send_reply_with_requests(self, tweet_id: str, reply_text: str) -> bool:
        """Fallback method using requests with OAuth 1.0a signature"""
        try:
            from requests_oauthlib import OAuth1Session
            
            api_key = os.getenv('TWITTER_API_KEY')
            api_secret = os.getenv('TWITTER_API_SECRET')
            access_token = os.getenv('TWITTER_ACCESS_TOKEN')
            access_token_secret = os.getenv('TWITTER_ACCESS_TOKEN_SECRET')
            
            # Create OAuth1 session
            oauth = OAuth1Session(
                api_key,
                client_secret=api_secret,
                resource_owner_key=access_token,
                resource_owner_secret=access_token_secret,
            )
            
            # Make the request
            url = "https://api.twitter.com/2/tweets"
            payload = {
                "text": reply_text,
                "reply": {
                    "in_reply_to_tweet_id": tweet_id
                }
            }
            
            response = oauth.post(url, json=payload)
            
            if response.status_code == 201:
                result = response.json()
                reply_id = result['data']['id']
                self.logger.info(f"✅ Reply sent via requests! Tweet ID: {reply_id}")
                return True
            else:
                self.logger.error(f"Failed to send reply: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            self.logger.error(f"Requests OAuth error: {e}")
            return False
    
    async def process_tweet_mention(self, tweet_data: Dict) -> str:
        """Process a tweet mention and potentially deploy a token
        
        Args:
            tweet_data: Dict containing:
                - id: Tweet ID
                - author_username: Username of tweet author
                - text: Tweet text
                - in_reply_to_status_id: Parent tweet ID if this is a reply
                - media: List of media objects from the deployment tweet
                - parent_media: List of media objects from parent tweet (if reply)
        """
        try:
            tweet_id = tweet_data['id']
            username = tweet_data['author_username']
            tweet_text = tweet_data['text']
            parent_tweet_id = tweet_data.get('in_reply_to_status_id')
            
            # Build tweet URL
            tweet_url = f"https://x.com/{username}/status/{tweet_id}"
            
            # SAFETY: Check if this is from the bot itself
            if username.lower() == self.bot_username.lower():
                # Check if this is the first deployment ever
                with sqlite3.connect(self.db_path) as conn:
                    cursor = conn.execute(
                        "SELECT COUNT(*) FROM deployments WHERE status = 'success'"
                    )
                    successful_deploys = cursor.fetchone()[0]
                
                if successful_deploys > 0:
                    # Skip processing bot's own tweets after first deployment
                    self.logger.warning(f"Skipping bot's own tweet from @{username} (already have {successful_deploys} deployments)")
                    return "❌ Bot should not deploy from its own tweets"
                else:
                    # Allow first deployment from bot's own account
                    print(f"🎯 FIRST DEPLOYMENT - Allowing bot's own tweet from @{username}")
                    self.logger.info("First deployment detected - allowing bot's own tweet")
            
            # Parse the tweet
            token_info = self.parse_tweet_for_token(tweet_text)
            if not token_info:
                return "❌ Invalid format. You MUST include $ before the symbol. Use: @DeployOnKlik $SYMBOL or @DeployOnKlik $SYMBOL - Token Name"
            
            # Get image - prioritize deployment tweet's own image over parent tweet
            image_url = None
            
            # First, check if deployment tweet itself has an image
            if 'media' in tweet_data and tweet_data['media']:
                for media in tweet_data['media']:
                    if media.get('type') == 'photo':
                        image_url = media.get('url')
                        self.logger.info(f"Using image from deployment tweet: {image_url}")
                        break
            
            # If no image in deployment tweet and it's a reply, check parent tweet
            if not image_url and parent_tweet_id:
                if 'parent_media' in tweet_data and tweet_data['parent_media']:
                    for media in tweet_data['parent_media']:
                        if media.get('type') == 'photo':
                            image_url = media.get('url')
                            self.logger.info(f"Using image from parent tweet: {image_url}")
                            break
            
            # Get follower count from tweet data (needed for DeploymentRequest)
            follower_count = tweet_data.get('follower_count', 0)
            
            # Create deployment request
            request = DeploymentRequest(
                tweet_id=tweet_id,
                username=username,
                token_name=token_info['name'],
                token_symbol=token_info['symbol'],
                requested_at=datetime.now(),
                tweet_url=tweet_url,
                parent_tweet_id=parent_tweet_id,
                image_url=image_url,
                follower_count=follower_count
            )
            
            # Show deployment preview and ask for confirmation
            print(f"\n📋 DEPLOYMENT PREVIEW")
            print(f"=" * 50)
            print(f"💰 Token: {request.token_name} ({request.token_symbol})")
            print(f"👤 User: @{request.username}")
            print(f"🔗 Tweet: {request.tweet_url}")
            if request.image_url:
                print(f"🖼️  Image: ✅ Found ({request.image_url[:50]}...)")
            else:
                print(f"🖼️  Image: ❌ Not found")
            
            # Get current gas price for estimate
            current_gas_price = self.w3.eth.gas_price
            current_gas_gwei = float(self.w3.from_wei(current_gas_price, 'gwei'))
            # Use realistic gas estimate for preview
            estimated_gas_units = 6_500_000  # Typical for Klik factory deployments
            estimated_cost = float(self.w3.from_wei(current_gas_price * estimated_gas_units, 'ether'))
            
            print(f"⛽ Gas Price: {current_gas_gwei:.1f} gwei")
            print(f"💸 Est. Gas Cost: {estimated_cost:.4f} ETH (~${estimated_cost * 2420:.2f})")
            
            # Show balance breakdown
            total_balance = self.get_eth_balance()
            user_deposits = self.get_total_user_deposits()
            available_balance = self.get_available_balance()
            
            print(f"💰 Bot Total Balance: {total_balance:.4f} ETH")
            print(f"   • User deposits: {user_deposits:.4f} ETH (protected)")
            print(f"   • Available for bot: {available_balance:.4f} ETH")
            print(f"👤 User Balance: {self.get_user_balance(username):.4f} ETH")
            
            # Check rate limits to show status
            can_deploy, rate_msg = self.check_rate_limits(username, follower_count)
            if not can_deploy:
                print(f"\n⚠️  {rate_msg}")
                # Don't even ask for confirmation if they can't deploy
                print(f"=" * 50)
                print("\n❌ Cannot deploy - sending instructions via Twitter reply...")
                
                # Send instructions immediately
                await self.send_twitter_reply_instructions(tweet_id, username, rate_msg)
                return f"❌ Rate limit failed: {rate_msg}"
            else:
                # Show what type of deployment this will be
                if "Free deployment allowed" in rate_msg:
                    print(f"\n✅ {rate_msg}")
                    print("🎉 Bot will pay the gas!")
                elif "Holder deployment allowed" in rate_msg:
                    print(f"\n🎯 {rate_msg}")
                    print("🎉 Bot will pay the gas (holder benefit)!")
                elif "Pay-per-deploy" in rate_msg:
                    print(f"\n💰 {rate_msg}")
            
            print(f"=" * 50)
            
            # Only ask for confirmation if running in interactive mode AND they can deploy
            if os.getenv('AUTO_DEPLOY', 'false').lower() != 'true':
                # Generate salt and predict address for manual deployments
                print("\n🔮 Generating vanity address...")
                try:
                    salt, predicted_address = await self.generate_salt_and_address(
                        request.token_name, 
                        request.token_symbol
                    )
                    # Store in request for later use
                    request.salt = salt
                    request.predicted_address = predicted_address
                    
                    print(f"\n{'='*60}")
                    print(f"🎯 TOKEN WILL BE DEPLOYED AT:")
                    print(f"   {predicted_address}")
                    print(f"{'='*60}")
                    print(f"📝 Copy this address NOW to set up buy orders!")
                    print(f"📈 DexScreener: https://dexscreener.com/ethereum/{predicted_address}")
                    print(f"⏱️  You have time before confirming deployment")
                    print(f"{'='*60}")
                    
                except Exception as e:
                    print(f"⚠️  Failed to generate vanity address: {e}")
                    print("   Deployment will proceed with random salt if confirmed")
                
                confirm = input("\n⚠️  Deploy this token? (y/N): ")
                if confirm.lower() != 'y':
                    print("❌ Deployment cancelled by user")
                    
                    # For testing: Still try to send Twitter reply as if deployment failed
                    if os.getenv('TEST_TWITTER_REPLIES', 'false').lower() == 'true':
                        print("\n🧪 TEST MODE: Attempting Twitter reply despite cancellation...")
                        request.status = "cancelled"
                        await self.send_twitter_reply(request, success=False)
                    
                    return "❌ Deployment cancelled by user"
            
            # Save to DB
            self._save_deployment_to_db(request)
            
            # Add to deployment queue instead of deploying directly
            try:
                # Check if queue is full
                if self.deployment_queue.full():
                    print(f"⚠️  Queue is full! ({self.deployment_queue.maxsize} deployments pending)")
                    await self.send_twitter_reply_instructions(tweet_id, username, 
                        "⏳ System is busy! Too many deployments in queue. Please try again in a few minutes.")
                    return "❌ Queue is full"
                
                # Check if user already has a pending deployment
                async with self.deployment_lock:
                    if username.lower() in self.active_deployments:
                        print(f"⏳ User @{username} already has active deployment")
                        return "❌ User already has active deployment"
                
                # Add to queue
                await self.deployment_queue.put(request)
                queue_position = self.deployment_queue.qsize()
                
                print(f"📥 Added to queue: @{username}'s ${request.token_symbol} (position: {queue_position})")
                
                # If queue is getting large, warn the user
                if queue_position > 5:
                    # Send a quick status update
                    await self._send_queue_status_reply(tweet_id, username, queue_position)
                
                return f"✅ Deployment queued (position: {queue_position})"
                
            except asyncio.QueueFull:
                await self.send_twitter_reply_instructions(tweet_id, username, 
                    "⏳ System overloaded! Please try again in a few minutes.")
                return "❌ Queue is full"
                
        except Exception as e:
            self.logger.error(f"Error processing tweet: {e}")
            return f"❌ Error processing request: {str(e)}"
    
    def get_deployment_stats(self) -> Dict:
        """Get deployment statistics"""
        with sqlite3.connect(self.db_path, detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES) as conn:
            cursor = conn.execute('''
                SELECT 
                    COUNT(*) as total,
                    SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) as successful,
                    COUNT(DISTINCT username) as unique_users,
                    SUM(CASE WHEN image_ipfs IS NOT NULL THEN 1 ELSE 0 END) as with_images
                FROM deployments
                WHERE requested_at > datetime('now', '-24 hours')
            ''')
            stats = cursor.fetchone()
        
        return {
            'total_requests_24h': stats[0],
            'successful_deploys_24h': stats[1],
            'unique_users_24h': stats[2],
            'tokens_with_images_24h': stats[3],
            'current_balance': self.get_eth_balance(),
            'user_deposits': self.get_total_user_deposits(),
            'available_balance': self.get_available_balance(),
            'queue_size': self.deployment_queue.qsize(),
            'active_deployments': len(self.active_deployments)
        }

    async def start_realtime_monitoring(self):
        """Start real-time monitoring using TwitterMonitor"""
        # Start the deployment worker
        asyncio.create_task(self.deployment_worker())
        print("🏃 Deployment worker started")
        
        # Start queue monitor
        asyncio.create_task(self.queue_monitor())
        print("📊 Queue monitor started")
        
        # Start monitoring
        monitor = TwitterMonitor(self)
        await monitor.start_realtime_monitoring()
    
    async def queue_monitor(self):
        """Periodically show queue health and check balance safety"""
        last_stats_time = 0
        last_safety_check = 0
        
        while True:
            try:
                await asyncio.sleep(60)  # Check every minute
                
                # Safety check every 5 minutes
                current_time = time.time()
                if current_time - last_safety_check >= 300:  # 5 minutes
                    total_balance = self.get_eth_balance()
                    user_deposits = self.get_total_user_deposits()
                    
                    # CRITICAL SAFETY CHECK
                    if total_balance < user_deposits:
                        self.logger.critical(f"⚠️ CRITICAL: Bot balance ({total_balance:.4f}) is LESS than user deposits ({user_deposits:.4f})!")
                        print(f"\n🚨 CRITICAL ALERT: Bot balance below user deposits!")
                        print(f"   Total: {total_balance:.4f} ETH")
                        print(f"   User deposits: {user_deposits:.4f} ETH")
                        print(f"   DEFICIT: {user_deposits - total_balance:.4f} ETH")
                        print(f"⚠️  FREE DEPLOYMENTS DISABLED UNTIL RESOLVED!")
                    
                    last_safety_check = current_time
                
                # Show stats if queue has activity
                queue_size = self.deployment_queue.qsize()
                active_count = len(self.active_deployments)
                
                if queue_size > 0 or active_count > 0:
                    current_time = time.time()
                    
                    # Only show stats every 5 minutes unless queue is getting full
                    if queue_size >= 5 or (current_time - last_stats_time) >= 300:
                        total_balance = self.get_eth_balance()
                        user_deposits = self.get_total_user_deposits()
                        available_balance = self.get_available_balance()
                        
                        print(f"\n📊 Queue Status Update:")
                        print(f"   • Queue: {queue_size}/10 pending")
                        print(f"   • Active: {active_count} deploying")
                        print(f"   • Total Balance: {total_balance:.4f} ETH")
                        print(f"   • User Deposits: {user_deposits:.4f} ETH (protected)")
                        print(f"   • Available: {available_balance:.4f} ETH")
                        
                        if queue_size >= 8:
                            print(f"   ⚠️  Queue nearly full! Consider increasing gas limit.")
                        
                        if available_balance < 0.1:
                            print(f"   ⚠️  LOW BOT BALANCE! Free deployments may fail.")
                        
                        last_stats_time = current_time
                        
            except Exception as e:
                self.logger.error(f"Queue monitor error: {e}")
                await asyncio.sleep(60)
    
    async def deployment_worker(self):
        """Worker that processes deployment queue sequentially"""
        print("👷 Deployment worker ready")
        
        while True:
            try:
                # Get next deployment from queue
                request = await self.deployment_queue.get()
                
                # Check if user already has an active deployment
                async with self.deployment_lock:
                    if request.username.lower() in self.active_deployments:
                        print(f"⏳ User @{request.username} already has active deployment, skipping duplicate")
                        await self.send_twitter_reply(request, success=False)
                        continue
                    
                    # Mark as active
                    self.active_deployments[request.username.lower()] = request.tweet_id
                
                try:
                    # Show queue status
                    queue_size = self.deployment_queue.qsize()
                    if queue_size > 0:
                        print(f"\n📦 Processing deployment (queue: {queue_size} pending)")
                    
                    # CRITICAL SAFETY CHECK before every deployment
                    total_balance = self.get_eth_balance()
                    user_deposits = self.get_total_user_deposits()
                    
                    if total_balance < user_deposits:
                        self.logger.critical(f"SAFETY STOP: Cannot deploy - bot balance below user deposits!")
                        print(f"🚨 DEPLOYMENT BLOCKED - Bot balance safety violation!")
                        request.status = "failed"
                        await self.send_twitter_reply_instructions(request.tweet_id, request.username, 
                            "❌ System maintenance - please try again later.")
                        continue
                    
                    # Re-validate deployment eligibility (things may have changed while in queue)
                    can_deploy, rate_msg = self.check_rate_limits(request.username, request.follower_count)
                    
                    if not can_deploy:
                        print(f"❌ User @{request.username} no longer eligible: {rate_msg}")
                        request.status = "cancelled"
                        await self.send_twitter_reply_instructions(request.tweet_id, request.username, rate_msg)
                        continue
                    
                    print(f"✅ Re-validated eligibility: {rate_msg}")
                    
                    # Process the deployment
                    success = await self.deploy_token(request)
                    
                    # Send notifications
                    self.send_telegram_notification(request, success)
                    await self.send_twitter_reply(request, success)
                    
                    if success:
                        print(f"✅ Deployment complete for @{request.username}")
                    else:
                        print(f"❌ Deployment failed for @{request.username}")
                        
                except Exception as e:
                    self.logger.error(f"Deployment worker error: {e}")
                    request.status = "failed"
                    await self.send_twitter_reply(request, success=False)
                    
                finally:
                    # Remove from active deployments
                    async with self.deployment_lock:
                        self.active_deployments.pop(request.username.lower(), None)
                    
                    # Mark task as done
                    self.deployment_queue.task_done()
                    
                # Small delay between deployments to prevent overwhelming the network
                await asyncio.sleep(2)
                
            except asyncio.CancelledError:
                print("👷 Deployment worker shutting down")
                break
            except Exception as e:
                self.logger.error(f"Deployment worker critical error: {e}")
                await asyncio.sleep(5)  # Wait before retrying

    def get_user_balance(self, username: str) -> float:
        """Get user's ETH balance from database"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT balance FROM users WHERE LOWER(twitter_username) = LOWER(?)",
                (username,)
            )
            result = cursor.fetchone()
            return result[0] if result else 0.0
    
    def check_holder_status(self, username: str) -> bool:
        """Check if user is a verified holder"""
        # First check manual whitelist in .env (for special cases)
        holder_list = os.getenv('HOLDER_LIST', '')
        if holder_list:
            for entry in holder_list.split(','):
                if ':' in entry:
                    holder_user, holder_addr = entry.split(':')
                    if holder_user.lower() == username.lower():
                        self.logger.info(f"@{username} is whitelisted holder")
                        return True
        
        # Check database for $DOK holder status
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT is_holder, eth_address FROM users WHERE LOWER(twitter_username) = LOWER(?)",
                (username,)
            )
            result = cursor.fetchone()
            
            if not result:
                return False
            
            is_holder, wallet = result
            
            # SECURITY: Check if user has ever deposited from this wallet
            # This proves they own the wallet
            cursor = conn.execute(
                "SELECT COUNT(*) FROM deposits WHERE LOWER(twitter_username) = LOWER(?) AND from_address = ? AND confirmed = 1",
                (username, wallet)
            )
            deposit_count = cursor.fetchone()[0]
            
            if deposit_count == 0:
                # No deposits from this wallet = not verified
                self.logger.info(f"@{username} has not deposited from wallet {wallet[:6]}...{wallet[-4:]} - holder benefits disabled")
                return False
            
            # Wallet is verified through deposits - check DOK balance
            if wallet and not is_holder:
                # Import holder verification dynamically
                try:
                    from holder_verification import check_holder_status as verify_dok_holder
                    
                    # Check real-time holder status
                    is_holder_now, balance, percentage = verify_dok_holder(wallet)
                    
                    if is_holder_now:
                        # Update database
                        conn.execute(
                            "UPDATE users SET is_holder = 1, holder_balance = ? WHERE LOWER(twitter_username) = LOWER(?)",
                            (balance, username)
                        )
                        conn.commit()
                        self.logger.info(f"Updated @{username} to holder status with {balance:.0f} DOK ({percentage:.2f}%) - wallet verified via deposits")
                        return True
                except Exception as e:
                    self.logger.error(f"Error checking real-time holder status: {e}")
            
            return bool(is_holder)
    
    async def _send_queue_status_reply(self, tweet_id: str, username: str, position: int) -> bool:
        """Send a quick status update about queue position"""
        try:
            if username.lower() == self.bot_username.lower():
                return False
            
            api_key = os.getenv('TWITTER_API_KEY')
            api_secret = os.getenv('TWITTER_API_SECRET')
            access_token = os.getenv('TWITTER_ACCESS_TOKEN')
            access_token_secret = os.getenv('TWITTER_ACCESS_TOKEN_SECRET')
            
            if not all([api_key, api_secret, access_token, access_token_secret]):
                return False
            
            reply_text = f"""@{username} Queued! Position: {position}

Your token will deploy soon ⏳"""
            
            import tweepy
            
            try:
                client = tweepy.Client(
                    consumer_key=api_key,
                    consumer_secret=api_secret,
                    access_token=access_token,
                    access_token_secret=access_token_secret
                )
                
                response = client.create_tweet(
                    text=reply_text,
                    in_reply_to_tweet_id=tweet_id
                )
                
                return response.data is not None
                    
            except Exception:
                return False
            
        except Exception:
            return False
    
    async def send_twitter_reply_instructions(self, tweet_id: str, username: str, instructions: str) -> bool:
        """Reply with instructions to use Telegram when gas is high"""
        try:
            # SAFETY: Check if this is from the bot itself
            if username.lower() == self.bot_username.lower():
                # Check if this is the first deployment ever
                with sqlite3.connect(self.db_path) as conn:
                    cursor = conn.execute(
                        "SELECT COUNT(*) FROM deployments WHERE status = 'success'"
                    )
                    successful_deploys = cursor.fetchone()[0]
                
                if successful_deploys > 0:
                    # Skip replying to own tweets after first deployment
                    self.logger.warning(f"Skipping instruction reply to own tweet from @{username}")
                    return False
                else:
                    # Allow reply to first deployment
                    self.logger.info("First deployment - allowing instruction reply to bot's own tweet")
            
            # Check if we have all OAuth 1.0a credentials
            api_key = os.getenv('TWITTER_API_KEY')
            api_secret = os.getenv('TWITTER_API_SECRET')
            access_token = os.getenv('TWITTER_ACCESS_TOKEN')
            access_token_secret = os.getenv('TWITTER_ACCESS_TOKEN_SECRET')
            
            if not all([api_key, api_secret, access_token, access_token_secret]):
                self.logger.warning("Twitter OAuth credentials not complete - skipping instruction reply")
                return False
            
            # Simple, clean message directing to Telegram channel
            # Extract key info from instructions
            if "Gas too high" in instructions:
                gas_match = re.search(r'\((\d+\.?\d*) gwei\)', instructions)
                gas_value = gas_match.group(1) if gas_match else "high"
                reply_text = f"""@{username} Gas too high! ({gas_value} gwei)

Free tier: ≤3 gwei only
Deposit ETH for any gas: t.me/DeployOnKlik"""
            elif "Not enough followers" in instructions:
                followers_match = re.search(r'You have: ([\d,]+) followers', instructions)
                follower_count = followers_match.group(1) if followers_match else "?"
                reply_text = f"""@{username} Need 1,500+ followers for free deploys!

You have: {follower_count}
Or deposit ETH: t.me/DeployOnKlik"""
            elif "Daily free limit reached" in instructions or "Daily limit reached" in instructions:
                reply_text = f"""@{username} Daily limit reached! (1 free/day)

Deposit ETH for unlimited:
t.me/DeployOnKlik"""
            elif "Holder daily limit reached" in instructions:
                reply_text = f"""@{username} Holder limit reached (2/2 today)

Thank you for supporting $KLIK! 🎯"""
            elif "balance" in instructions.lower():
                reply_text = f"""@{username} Insufficient balance!

Quick & easy deposits:
t.me/DeployOnKlik"""
            else:
                # Generic message
                reply_text = f"""@{username} Can't deploy right now.

Info & deposits: t.me/DeployOnKlik"""
            
            # Use tweepy
            import tweepy
            
            try:
                client = tweepy.Client(
                    consumer_key=api_key,
                    consumer_secret=api_secret,
                    access_token=access_token,
                    access_token_secret=access_token_secret
                )
                
                response = client.create_tweet(
                    text=reply_text,
                    in_reply_to_tweet_id=tweet_id
                )
                
                if response.data:
                    self.logger.info(f"✅ Instruction reply sent! Tweet ID: {response.data['id']}")
                    return True
                else:
                    return False
                    
            except tweepy.TooManyRequests:
                self.logger.error("Rate limit reached for Twitter replies")
                return False
            
        except Exception as e:
            self.logger.error(f"Error sending instruction reply: {e}")
            return False

async def main(mode: str = "realtime"):
    """Main function - defaults to real-time monitoring
    
    Args:
        mode: Either 'test' for testing deployment or 'realtime' for monitoring (default)
    """
    deployer = KlikTokenDeployer()
    
    # Check balance
    balance = deployer.get_eth_balance()
    if balance < 0.01:
        print(f"⚠️  WARNING: Low balance ({balance:.4f} ETH)")
        print("   Consider adding more ETH for gas fees")
    
    if mode == "test":
        # Test mode
        test_tweet = {
            'id': '1234567890',
            'author_username': 'testuser',
            'text': f'@{deployer.bot_username} $TEST - Test Token',
            'in_reply_to_status_id': None,
            'media': [],
            'parent_media': [],
            'follower_count': 5000  # Test with 5k followers
        }
    
        print(f"\n🧪 TESTING DEPLOYMENT")
        print(f"📝 Tweet: {test_tweet['text']}")
        print(f"👤 User: @{test_tweet['author_username']}")
        
        # Confirm before deploying
        confirm = input("\n⚠️  This will deploy a real token! Continue? (y/N): ")
        if confirm.lower() != 'y':
            print("❌ Deployment cancelled")
            return
        
        result = await deployer.process_tweet_mention(test_tweet)
        print(f"\n📋 Result: {result}")
        
        # Show stats
        stats = deployer.get_deployment_stats()
        print(f"\n📊 DEPLOYMENT STATS:")
        print(f"   Total Balance: {stats['current_balance']:.4f} ETH")
        print(f"   User Deposits: {stats['user_deposits']:.4f} ETH")
        print(f"   Available for Bot: {stats['available_balance']:.4f} ETH")
        print(f"   24h Requests: {stats['total_requests_24h']}")
        print(f"   24h Successful: {stats['successful_deploys_24h']}")
        print(f"   24h With Images: {stats['tokens_with_images_24h']}")
        
    else:
        # Real-time mode (default)
        try:
            await deployer.start_realtime_monitoring()
        except KeyboardInterrupt:
            print("\n👋 Bot stopped by user")
        except Exception as e:
            print(f"❌ Error: {e}")

if __name__ == "__main__":
    import sys
    
    # Check command line arguments
    if len(sys.argv) > 1 and sys.argv[1] == "--test":
        # Test mode
        print("🧪 KLIK FINANCE TEST MODE")
        asyncio.run(main("test"))
    else:
        # Real-time mode (default)
        asyncio.run(main("realtime")) 