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
from typing import Dict, Optional, Tuple
import logging
from asyncio import Queue, Lock

# Web3 and blockchain
from web3 import Web3
from eth_account import Account

# Environment and HTTP
from dotenv import load_dotenv
import aiohttp
import requests

# Database for tracking - moved to database service

# For address calculation
from eth_hash.auto import keccak
from eth_utils import to_checksum_address

# Twitter monitoring
from twitter_monitor import TwitterMonitor

# For image handling
import base64

# Import data models and services
from deployer.models import DeploymentRequest
from deployer.services import IPFSService
from deployer.database import DeploymentDatabase

class KlikTokenDeployer:
    """Twitter-triggered token deployer for Klik Finance"""
    
    def __init__(self):
        """Initialize the deployer"""
        load_dotenv()
        self._setup_logging()
        self._load_config()
        self._setup_web3()
        self.db_path = 'deployments.db'
        
        # Rate limiting
        self.deployment_history = []
        self.user_deployments = {}
        
        # Twitter reply rate limiting
        self.twitter_reply_history = []  # Track Twitter replies
        
        # Twitter API Basic tier limits ($200/month)
        # 50,000 posts/month at app level = ~1667/day = ~69/hour = ~17/15min
        # 3,000 posts/month at user level = ~100/day
        self.twitter_tier = os.getenv('TWITTER_API_TIER', 'basic').lower()
        tier_limits = {
            'v2': 15,         # Free tier: conservative
            'free': 15,       # Same as v2
            'basic': 60,      # Basic tier: 50k/month = ~69/hour (conservative at 60)
            'pro': 150,       # Pro tier  
            'enterprise': 500 # Enterprise tier
        }
        self.twitter_reply_limit = tier_limits.get(self.twitter_tier, 60)
        self.twitter_reply_window = 900  # 15 minutes in seconds
        
        # Also track daily limit - Basic tier has much higher limits
        self.twitter_daily_limit = 1500  # Conservative under 1667/day limit
        self.twitter_daily_window = 86400  # 24 hours in seconds
        
        print(f"🐦 Twitter API: {self.twitter_reply_limit} replies/15min, {self.twitter_daily_limit}/day")
        
        # Queue system for deployments
        self.deployment_queue = Queue(maxsize=10)  # Max 10 pending deployments
        self.deployment_lock = Lock()  # For critical sections
        self.active_deployments = {}  # Track active deployments by user
        self.nonce_lock = Lock()  # Separate lock for nonce management
        self.last_nonce = None
        self.last_nonce_time = 0
        
        # Initialize services
        self.ipfs_service = IPFSService()
        self.db = DeploymentDatabase(self.db_path)
        
        # Clean up any expired or excessive cooldowns from old system
        cleaned = self.db.cleanup_expired_cooldowns()
        if cleaned > 0:
            print(f"🧹 Cleaned up {cleaned} old/expired cooldowns")
        
        print("🚀 KLIK FINANCE TWITTER DEPLOYER v2.0")
        print("=" * 50)
        print("💰 Deploy tokens via Twitter mentions")
        print("📋 FREE Tier: 250+ followers, 3 deploys/week ≤2 gwei")
        print("🌟 VIP Tier: 20k+ followers, 3 deploys/week ≤6 gwei")
        print("🎯 HOLDER: 5M+ $DOK, 10 deploys/week ≤10 gwei + NO FEES!")
        print("🖼️  Auto-attach images from parent tweets")
        print("🔗 Auto-link to deployment tweet")
        print("📦 Queue System: ENABLED (max 10 pending)")
        print(f"⏱️  Rate Limit: {self.max_deploys_per_hour} deploys per hour")
        
        # Show gas optimization status
        print(f"⛽ Gas Optimization: {'AGGRESSIVE' if self.aggressive_gas_optimization else 'CONSERVATIVE'}")
        print(f"   • Priority fee range: {self.min_priority_fee_gwei}-{self.max_priority_fee_gwei} gwei")
        print(f"   • Smart pricing: Saves 60-70% on gas costs")
        
        # Show balance breakdown
        total_balance = self.get_eth_balance()
        user_deposits = self.get_total_user_deposits()
        available_balance = self.get_available_balance()
        available_for_free = self.get_available_balance_for_free_deploys()
        
        # Get earned balances
        earned_fees = self.db.get_balance_by_source('fee_detection')
        platform_fees = self.db.get_balance_by_source('pay_per_deploy')
        dev_protected = self.db.get_balance_by_source('dev_protected')
        gas_expenses = self.db.get_balance_by_source('gas_expenses')
        
        print(f"💰 Total Balance: {total_balance:.4f} ETH")
        print(f"   • User deposits: {user_deposits:.4f} ETH (protected)")
        print(f"   • Fee detection treasury: {earned_fees:.4f} ETH (funds free deploys)")
        print(f"   • Gas expenses (free/holder): {gas_expenses:.4f} ETH (spent from treasury)")
        print(f"   • Dev protected fund: {dev_protected:.4f} ETH (protected)")
        print(f"   • Platform fees: {platform_fees:.4f} ETH (protected)")
        print(f"   • Available for bot: {available_balance:.4f} ETH")
        print(f"   • Available for FREE deploys: {available_for_free:.4f} ETH")
        
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
            print(f"✅ Twitter replies: ENABLED")
            print(f"   → Rate limit: {self.twitter_reply_limit}/15min, {self.twitter_daily_limit}/day")
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
        
        # Show Twitter rate limit status on startup
        self.debug_twitter_rate_limits()
    
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
        
        # Gas optimization settings
        self.aggressive_gas_optimization = os.getenv('AGGRESSIVE_GAS_OPTIMIZATION', 'true').lower() == 'true'
        self.min_priority_fee_gwei = float(os.getenv('MIN_PRIORITY_FEE_GWEI', '0.1'))
        self.max_priority_fee_gwei = float(os.getenv('MAX_PRIORITY_FEE_GWEI', '2.0'))
    
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
    

    
    def get_eth_balance(self) -> float:
        """Get current ETH balance"""
        balance_wei = self.w3.eth.get_balance(self.deployer_address)
        return float(self.w3.from_wei(balance_wei, 'ether'))
    
    def get_total_user_deposits(self) -> float:
        """Get total balance of all user deposits"""
        return self.db.get_total_user_deposits()
    
    def get_available_balance(self) -> float:
        """Get balance available for bot operations (excludes user deposits)"""
        total_balance = self.get_eth_balance()
        user_deposits = self.get_total_user_deposits()
        
        # Available = total - user deposits (with safety buffer)
        available = total_balance - (user_deposits * 1.05)  # 5% buffer for gas fluctuations
        
        return max(0, available)  # Never negative
    
    def get_available_balance_for_free_deploys(self) -> float:
        """Get balance available for FREE deployments only
        
        This excludes:
        - User deposits (protected for pay-per-deploy)
        - Platform fees (0.01 ETH per pay-per-deploy - protected)
        - Dev protected fund (manually moved from treasury - protected)
        
        But INCLUDES fee detection treasury since that's meant to fund free operations
        """
        total_balance = self.get_eth_balance()
        
        # Get truly protected balances only (not treasury, that's for free deployments)
        user_deposits = self.db.get_total_user_deposits()
        deployment_fees = self.db.get_balance_by_source('pay_per_deploy')
        dev_protected = self.db.get_balance_by_source('dev_protected')
        
        # Available for free deploys = total - user deposits, platform fees, and dev protected
        protected_total = user_deposits + deployment_fees + dev_protected
        available = total_balance - (protected_total * 1.05)  # 5% buffer
        
        return max(0, available)
    
    def check_progressive_cooldown(self, username: str) -> tuple[bool, str, int]:
        """Check progressive cooldown for free deployments
        
        Returns:
            tuple: (can_deploy, message, days_until_cooldown_ends)
        """
        return self.db.check_progressive_cooldown(username)
    
    def check_holder_weekly_deployments(self, username: str) -> int:
        """Check how many holder deployments user has made this week
        
        Returns:
            int: Number of holder deployments in the last 7 days
        """
        return self.db.check_holder_weekly_deployments(username)
    
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
    
    def get_optimal_gas_parameters(self) -> Tuple[int, int, float]:
        """Calculate optimal gas parameters based on network conditions
        
        Returns:
            Tuple of (max_priority_fee_wei, max_fee_per_gas_wei, base_fee_multiplier)
        """
        try:
            # Get recent blocks to analyze gas prices
            latest_block = self.w3.eth.get_block('latest', full_transactions=True)
            base_fee = latest_block['baseFeePerGas']
            
            # Get the last few blocks to check network congestion
            blocks_to_check = 5
            priority_fees = []
            gas_used_ratios = []
            
            for i in range(blocks_to_check):
                try:
                    block = self.w3.eth.get_block(latest_block['number'] - i, full_transactions=True)
                    if block and block['transactions']:
                        # Calculate gas used ratio
                        gas_used_ratio = block['gasUsed'] / block['gasLimit']
                        gas_used_ratios.append(gas_used_ratio)
                        
                        # Get priority fees from transactions
                        for tx in block['transactions'][:10]:  # Sample first 10 txs
                            if 'maxPriorityFeePerGas' in tx and 'maxFeePerGas' in tx:
                                effective_priority = min(
                                    tx['maxPriorityFeePerGas'],
                                    tx['maxFeePerGas'] - block['baseFeePerGas']
                                )
                                if effective_priority > 0:
                                    priority_fees.append(effective_priority)
                except:
                    continue
            
            # Calculate average network congestion
            avg_gas_used_ratio = sum(gas_used_ratios) / len(gas_used_ratios) if gas_used_ratios else 0.5
            
            # Determine network state and optimal parameters
            # ALWAYS cap priority fees to reasonable levels!
            min_priority = self.w3.to_wei(self.min_priority_fee_gwei, 'gwei')
            max_priority = self.w3.to_wei(self.max_priority_fee_gwei, 'gwei')
            
            if avg_gas_used_ratio < 0.5:
                # Low congestion - minimal priority fee
                max_priority_fee = min_priority  # Just use minimum (0.1 gwei)
                base_multiplier = 1.05 if self.aggressive_gas_optimization else 1.08
                
            elif avg_gas_used_ratio < 0.8:
                # Medium congestion - slightly higher but still low
                max_priority_fee = self.w3.to_wei(0.5, 'gwei')  # Fixed 0.5 gwei
                base_multiplier = 1.1
                
            else:
                # High congestion - cap at max setting (now 0.5 gwei max)
                max_priority_fee = max_priority  # Cap at configured max
                base_multiplier = 1.15 if self.aggressive_gas_optimization else 1.2
            
            # Calculate max fee
            max_fee_per_gas = int(base_fee * base_multiplier) + max_priority_fee
            
            # Log the decision
            self.logger.info(f"Gas optimization: congestion={avg_gas_used_ratio:.2f}, "
                           f"base_fee={base_fee/1e9:.2f} gwei, "
                           f"priority={max_priority_fee/1e9:.2f} gwei, "
                           f"multiplier={base_multiplier}")
            
            return max_priority_fee, max_fee_per_gas, base_multiplier
            
        except Exception as e:
            self.logger.warning(f"Failed to optimize gas, using defaults: {e}")
            # Fallback to conservative defaults
            base_fee = self.w3.eth.get_block('latest')['baseFeePerGas']
            max_priority_fee = self.w3.to_wei(0.5, 'gwei')  # Lower default than before
            max_fee_per_gas = int(base_fee * 1.15) + max_priority_fee
            return max_priority_fee, max_fee_per_gas, 1.15
    

    
    def parse_tweet_for_token(self, tweet_text: str) -> Optional[Dict[str, str]]:
        """Parse tweet text to extract token name/symbol
        
        REQUIRES $ symbol to reduce spam/clutter
        
        Examples:
        "@DeployOnKlik $MEME" -> {symbol: "MEME", name: "MEME"}
        "@DeployOnKlik $DOG - DogeCoin" -> {symbol: "DOG", name: "DogeCoin"}
        "@DeployOnKlik $CAT + CatCoin" -> {symbol: "CAT", name: "CatCoin"}
        "@DeployOnKlik PEPE" -> None (no $ symbol - rejected)
        
        Returns:
            Dict with 'symbol' and 'name' if valid
            Dict with 'error' and 'error_type' if invalid
            None if not a deployment attempt
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
        
        # BLOCK DOK TICKER - prevent spam of the bot's own token
        if symbol == 'DOK':
            self.logger.warning(f"Blocked DOK ticker deployment attempt from tweet: {tweet_text[:50]}...")
            return {'error': 'DOK ticker is reserved', 'error_type': 'reserved_ticker'}
        
        # Check symbol length BEFORE other validations
        if len(symbol) > 16:
            return {
                'error': f'Symbol too long ({len(symbol)} chars, max 16)',
                'error_type': 'symbol_too_long',
                'symbol_attempted': symbol
            }
        
        # Check if symbol is alphanumeric (allowing underscores)
        if not symbol.replace('_', '').isalnum():
            return {
                'error': 'Symbol must be letters and numbers only',
                'error_type': 'invalid_characters',
                'symbol_attempted': symbol
            }
        
        # Additional validation
        if not symbol:
            return None
        
        # Look for name after a dash or plus sign, but stop at URLs or mentions
        name_match = re.search(r'\$[a-zA-Z0-9]+\s*[-–+]\s*([^@\s]+(?:\s+[^@\s]+)*?)(?:\s+https?://|\s+@|\s*$)', text)
        if not name_match:
            # Try simpler pattern without URL/mention check
            name_match = re.search(r'\$[a-zA-Z0-9]+\s*[-–+]\s*([^@\n]+?)(?:\s+https?://|\s*$)', text)
        
        if name_match:
            name = name_match.group(1).strip()
            # Remove any trailing URLs that might have been caught
            name = re.sub(r'\s*https?://\S+\s*$', '', name).strip()
        else:
            name = symbol
        
        # Validate name length
        if len(name) > 30:
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
        
        # For EIP-1559, use optimal gas parameters for accurate calculations
        latest_block = self.w3.eth.get_block('latest')
        base_fee = latest_block['baseFeePerGas']
        
        # Get optimal gas parameters for accurate cost estimates
        max_priority_fee, max_fee_per_gas, base_multiplier = self.get_optimal_gas_parameters()
        
        # Use the actual current gas price for cost calculations (same as preview)
        likely_gas_gwei = current_gas_gwei
        
        # Get gas limits from config - updated for new tiers
        free_gas_limit = float(os.getenv('FREE_DEPLOY_GAS_LIMIT', '2'))
        vip_gas_limit = float(os.getenv('VIP_DEPLOY_GAS_LIMIT', '6'))  # VIP FREE up to 6 gwei
        holder_gas_limit = float(os.getenv('HOLDER_MAX_GAS_LIMIT', '10'))  # Reduced from 15 to 10
        
        # Check overall hourly spam protection
        recent_deploys = [
            d for d in self.deployment_history 
            if d > now - timedelta(hours=1)
        ]
        
        if len(recent_deploys) >= self.max_deploys_per_hour:
            # Log this important event
            self.logger.warning(f"⚠️ HOURLY RATE LIMIT HIT: {len(recent_deploys)}/{self.max_deploys_per_hour} deploys in last hour")
            print(f"\n⚠️ SYSTEM RATE LIMIT: {self.max_deploys_per_hour} deploys/hour reached!")
            print(f"   Recent deployments: {len(recent_deploys)}")
            print(f"   User affected: @{username}")
            print(f"   Time until reset: ~{60 - ((now - recent_deploys[0]).seconds // 60)} minutes")
            return False, f"⏳ System limit reached ({self.max_deploys_per_hour} deploys/hour). Try again later."
        
        # Estimate deployment cost using realistic gas usage
        # Use 6.5M units as typical for Klik factory deployments
        realistic_gas_units = 6_500_000
        # Use current gas price (same as preview) for consistency
        realistic_gas_cost = float(self.w3.from_wei(current_gas_price * realistic_gas_units, 'ether'))
        
        # Debug: Log the values
        debug_rates = os.getenv('DEBUG_RATES', 'false').lower() == 'true'
        if debug_rates:
            self.logger.debug(f"Rate check gas: current_gas={current_gas_gwei:.2f} gwei")
            self.logger.debug(f"Rate check cost: gas_cost={realistic_gas_cost:.4f} ETH for {realistic_gas_units/1e6:.1f}M units")
        
        # Check if user is a holder
        is_holder = self.check_holder_status(username)
        
        # Check if user qualifies for VIP tier (20k+ followers)
        is_vip = follower_count >= 20000
        if debug_rates:
            self.logger.debug(f"User @{username} has {follower_count:,} followers (VIP: {is_vip})")
        
        # Calculate total cost
        # Bot owner doesn't pay fees on their own deployments!
        is_bot_owner = username.lower() == self.bot_username.lower()
        # Fee only applies to pay-per-deploy, NOT free deployments!
        # And holders/bot owner never pay fees even on pay-per-deploy
        fee = 0  # Will be calculated properly based on deployment type later
        total_cost = realistic_gas_cost + fee  # For now, just gas cost
        
        # Get user balance
        user_balance = self.get_user_balance(username)
        if debug_rates:
            self.logger.debug(f"User @{username} balance: {user_balance:.4f} ETH")
        
        # CRITICAL: Check bot's available balance for free/holder deployments
        available_bot_balance = self.get_available_balance()
        
        # CRITICAL: Check bot's available balance for free/holder deployments
        available_bot_balance_for_free = self.get_available_balance_for_free_deploys()
        
        # Get deployment counts
        free_deploys_today, _ = self.db.get_daily_deployment_stats(username, today)
        
        # Get holder weekly deployments
        holder_deploys_this_week = self.check_holder_weekly_deployments(username) if is_holder else 0
        
        # Tier 1: Free deployment 
        # Standard users: gas <= 3 gwei AND 1500+ followers
        # VIP users (20k+ followers): gas <= 6 gwei
        gas_limit_for_user = vip_gas_limit if is_vip else free_gas_limit
        
        # Minimum follower count for FREE deployments
        min_followers_for_free = int(os.getenv('MIN_FOLLOWER_COUNT', '250'))
        
        # Check progressive cooldown for non-holders before allowing free deployment
        if not is_holder and not (user_balance >= realistic_gas_cost):  # Only for users seeking free deployment
            can_deploy_free, cooldown_msg, cooldown_days = self.check_progressive_cooldown(username)
            if not can_deploy_free:
                # User is in progressive cooldown
                # Calculate pay-per-deploy cost with fee
                cooldown_fee = 0 if is_bot_owner else 0.01
                cooldown_total = realistic_gas_cost + cooldown_fee
                
                if user_balance >= cooldown_total:
                    # They can still pay to deploy
                    return True, f"💰 Pay-per-deploy ({cooldown_msg.lower()}. Cost: {cooldown_total:.4f} ETH)"
                else:
                    # Cannot deploy at all - now with relaxed cooldowns
                    if cooldown_days >= 30:
                        # Serious spam - 30 day cooldown
                        return False, f"""🚫 SPAM COOLDOWN: 30-DAY TIMEOUT!

You attempted 4+ deployments in ONE DAY.
This is considered abuse of the free tier.

Cooldown ends: {cooldown_days} days

Learn more: t.me/DeployOnKlik"""
                    elif cooldown_days >= 7:
                        # Weekly limit exceeded
                        return False, f"""⏳ COOLDOWN: Weekly limit exceeded!

You used all 3 free deploys this week.
Next free deploy: {cooldown_days} days

Want to deploy NOW? 
💰 Deposit ETH: t.me/DeployOnKlik
🎯 Or hold 5M+ $DOK for 10/week"""
                    else:
                        # Should not happen with new system
                        return False, f"""⏳ COOLDOWN: Please wait {cooldown_days} days

Want to deploy NOW?
💰 Deposit ETH: t.me/DeployOnKlik
🎯 Or hold 5M+ $DOK for 10/week"""
        
        if likely_gas_gwei <= gas_limit_for_user:
            # Check follower count for free deployments
            if follower_count < min_followers_for_free and not is_holder:
                # Not enough followers for free deployment, check if they can pay
                # Calculate pay-per-deploy cost with fee
                follower_fee = 0 if is_bot_owner else 0.01
                follower_total = realistic_gas_cost + follower_fee
                
                if user_balance >= follower_total:
                    return True, f"💰 Pay-per-deploy (cost: {follower_total:.4f} ETH, balance: {user_balance:.4f} ETH)"
                else:
                    return False, f"""❌ Not enough followers for free deployment!

You have: {follower_count:,} followers
Need: {min_followers_for_free:,} followers for free deploys

💰 Or deposit {follower_total:.4f} ETH to deploy now:
t.me/DeployOnKlik"""
            
            # SAFETY: Check if bot has enough balance for free deployments
            if available_bot_balance_for_free < realistic_gas_cost * 1.1:
                # Bot doesn't have enough balance for free deployment
                # Calculate pay-per-deploy cost with fee
                bot_low_fee = 0 if (is_holder or is_bot_owner) else 0.01
                bot_low_total = realistic_gas_cost + bot_low_fee
                
                if user_balance >= bot_low_total:
                    return True, f"💰 Pay-per-deploy (bot low on funds - cost: {bot_low_total:.4f} ETH, your balance: {user_balance:.4f} ETH)"
                else:
                    return False, f"""❌ Bot balance too low for free deployment!

Bot needs more ETH for free deploys.
Deposit to deploy now: t.me/DeployOnKlik"""
            
            if is_holder and holder_deploys_this_week < 10:  # 10 per week for holders!
                return True, f"✅ Holder deployment allowed (gas: {likely_gas_gwei:.1f} gwei, {holder_deploys_this_week}/10 used this week)"
            else:
                # For non-holders, use progressive cooldown system (already checked earlier)
                # If we reached here, the progressive cooldown already approved the deployment
                # (otherwise it would have returned False earlier in the function)
                if is_vip and likely_gas_gwei > free_gas_limit:
                    return True, f"✅ Free deployment allowed (gas: {likely_gas_gwei:.1f} gwei, 20k+ followers benefit)"
                else:
                    return True, f"✅ Free deployment allowed (gas: {likely_gas_gwei:.1f} gwei)"
        
        # Tier 2: Holder deployment (gas <= 15 gwei)
        if is_holder:
            if likely_gas_gwei > holder_gas_limit:
                return False, f"""❌ Gas too high for holders!

Gas: {likely_gas_gwei:.1f} gwei (limit: {holder_gas_limit:.0f})

Please wait for gas to drop or visit t.me/DeployOnKlik"""
            
            # SAFETY: Check if bot has enough balance for holder deployments
            if available_bot_balance_for_free < realistic_gas_cost * 1.1:
                # Bot doesn't have enough balance for holder deployment
                # Holders never pay fees, even on pay-per-deploy
                holder_low_total = realistic_gas_cost  # No fee for holders
                
                if user_balance >= holder_low_total:
                    return True, f"💰 Pay-per-deploy (bot low on funds - cost: {holder_low_total:.4f} ETH, your balance: {user_balance:.4f} ETH)"
                else:
                    return False, f"""❌ Bot balance too low for holder deployment!

Bot needs more ETH for free deploys.
Your balance: {user_balance:.4f} ETH
Deposit more: t.me/DeployOnKlik"""
            
            if holder_deploys_this_week < 10:  # 10 per week for holders!
                return True, f"🎯 Holder deployment allowed ({holder_deploys_this_week}/10 used this week, gas: {likely_gas_gwei:.1f} gwei)"
            else:
                return False, f"🎯 Holder weekly limit reached (10/10 used). Thank you for supporting $KLIK!"
        
        # Tier 3: Pay per deploy (check balance)
        # NOW calculate the fee for pay-per-deploy
        pay_deploy_fee = 0 if (is_holder or is_bot_owner) else 0.01
        pay_deploy_total = realistic_gas_cost + pay_deploy_fee
        
        if user_balance >= pay_deploy_total:
            return True, f"💰 Pay-per-deploy (cost: {pay_deploy_total:.4f} ETH, balance: {user_balance:.4f} ETH)"
        
        # Cannot deploy - insufficient balance
        return False, f"""❌ Gas too high! ({likely_gas_gwei:.1f} gwei)

Cost: {pay_deploy_total:.4f} ETH
Your balance: {user_balance:.4f} ETH

To deploy when gas > 2 gwei:
Visit t.me/DeployOnKlik 💬

Quick & easy deposits!"""
    
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
            gas_limit_for_user = 6 if request.follower_count >= 20000 else 2  # 20k+ followers get 6 gwei limit
            min_followers_for_free = int(os.getenv('MIN_FOLLOWER_COUNT', '250'))
            
            # Check if qualifies for free deployment
            if likely_gas_gwei <= gas_limit_for_user and request.follower_count >= min_followers_for_free and not is_holder:
                deployment_type = 'free'
            elif is_holder and likely_gas_gwei <= 10:  # Holder gas limit (reduced from 15)
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
                image_ipfs = await self.ipfs_service.upload_image_to_ipfs(request.image_url)
                if image_ipfs:
                    metadata_obj["image"] = image_ipfs
                    print(f"✅ Image uploaded: {image_ipfs}")
            
            # Try to upload metadata to IPFS
            metadata = None
            if self.ipfs_service.pinata_api_key or self.ipfs_service.web3_storage_token:
                metadata_ipfs = self.ipfs_service.upload_metadata_to_ipfs(metadata_obj)
                if metadata_ipfs:
                    metadata = metadata_ipfs
                    print(f"📦 Metadata uploaded to IPFS: {metadata_ipfs}")
            
            # Fall back to JSON if IPFS fails
            if not metadata:
                metadata = json.dumps(metadata_obj)
            
            # Get base fee and calculate EIP-1559 gas parameters
            latest_block = self.w3.eth.get_block('latest')
            base_fee = latest_block['baseFeePerGas']
            
            # Use optimal gas parameters based on network conditions
            max_priority_fee, max_fee_per_gas, base_multiplier = self.get_optimal_gas_parameters()
            
            # Log gas optimization info
            print(f"🎯 Gas Optimization: Network congestion analyzed")
            print(f"   • Base multiplier: {base_multiplier}x (was 1.2x)")
            print(f"   • Priority fee: {max_priority_fee/1e9:.2f} gwei (was 1 gwei)")
            
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
                
                # Use tighter gas limits based on network conditions and deployment type
                if deployment_type in ['free', 'holder']:
                    # Bot paying - be more aggressive with gas limits
                    if base_multiplier <= 1.05:
                        # Low congestion - minimal buffer
                        gas_limit = int(gas_estimate * 1.02)  # 2% buffer
                        buffer_pct = 2
                    elif base_multiplier <= 1.1:
                        # Medium congestion
                        gas_limit = int(gas_estimate * 1.03)  # 3% buffer
                        buffer_pct = 3
                    else:
                        # High congestion - still conservative
                        gas_limit = int(gas_estimate * 1.05)  # 5% buffer
                        buffer_pct = 5
                else:
                    # User paying - slightly more conservative
                    if gas_estimate > 4_000_000:
                        gas_limit = int(gas_estimate * 1.05)
                        buffer_pct = 5
                    else:
                        gas_limit = int(gas_estimate * 1.08)  # 8% buffer
                        buffer_pct = 8
                
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
                    self.db.update_deployment(request)
                    
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
                
                # Update daily limits
                self.db.update_daily_limits(request.username, deployment_type)
                
                # Update cooldown tracking for free deployments
                if deployment_type == 'free':
                    self.db.update_cooldown_after_deployment(request.username, deployment_type)
                    
                    # Track gas cost against treasury
                    self.db.record_free_deployment_gas_cost(
                        actual_gas_cost, 
                        request.tx_hash, 
                        f"Gas for free deploy: ${request.token_symbol} by @{request.username}"
                    )
                elif deployment_type == 'holder':
                    self.db.update_cooldown_after_deployment(request.username, deployment_type)
                    
                    # Track gas cost against treasury (holders don't pay, but bot does)
                    self.db.record_free_deployment_gas_cost(
                        actual_gas_cost, 
                        request.tx_hash, 
                        f"Gas for holder deploy: ${request.token_symbol} by @{request.username}"
                    )
                elif deployment_type == 'pay-per-deploy':
                    # Deduct from balance
                    # Bot owner also pays no fee on their own deployments
                    is_bot_owner = request.username.lower() == self.bot_username.lower()
                    fee = 0 if (is_holder or is_bot_owner) else 0.01  # Holders and bot owner pay no fee!
                    new_balance = self.db.update_user_balance_after_deployment(
                        request.username, actual_gas_cost, fee, request.tx_hash, request.token_symbol
                    )
                    
                    if new_balance is not None:
                        if fee > 0:
                            print(f"💰 Deducted {actual_gas_cost + fee:.4f} ETH from balance (gas: {actual_gas_cost:.4f}, fee: {fee:.4f})")
                        else:
                            print(f"🎯 Deducted {actual_gas_cost:.4f} ETH from holder balance (gas only, NO FEES!)")
                        print(f"   New balance: {new_balance:.4f} ETH")
                        
                        # Log balance change for audit trail
                        self.logger.info(f"Balance deduction: @{request.username} -{actual_gas_cost + fee:.4f} ETH (new balance: {new_balance:.4f})")
                
                # Store image IPFS if we have it
                if image_ipfs:
                    self.db.update_image_ipfs(request.tweet_id, image_ipfs)
                
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
            self.db.update_deployment(request)
    
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
            # Check Twitter reply rate limit first
            now = time.time()
            # Remove replies older than 15 minutes
            self.twitter_reply_history = [t for t in self.twitter_reply_history if now - t < self.twitter_reply_window]
            
            # Also check daily limit (24 hours)
            daily_replies = [t for t in self.twitter_reply_history if now - t < self.twitter_daily_window]
            
            if len(self.twitter_reply_history) >= self.twitter_reply_limit:
                self.logger.warning(f"Twitter reply rate limit reached: {len(self.twitter_reply_history)}/{self.twitter_reply_limit} in 15 minutes")
                print(f"⚠️  Skipping Twitter reply - rate limit ({self.twitter_reply_limit} replies/15min)")
                return False
            
            if len(daily_replies) >= self.twitter_daily_limit:
                self.logger.warning(f"Twitter daily limit reached: {len(daily_replies)}/{self.twitter_daily_limit} in 24 hours")
                print(f"⚠️  Skipping Twitter reply - daily limit ({self.twitter_daily_limit} replies/day)")
                return False
            
            # SAFETY: Check if this is from the bot itself
            if request.username.lower() == self.bot_username.lower():
                # Check if this is the first deployment ever
                successful_deploys = self.db.get_successful_deploys_count()
                
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
                    # Track this reply for rate limiting
                    self.twitter_reply_history.append(time.time())
                    return True
                else:
                    self.logger.error(f"Failed to send reply: No response data")
                    return False
                    
            except tweepy.TooManyRequests as e:
                # This is Twitter's API rate limit, not our internal tracking
                self.logger.error(f"Twitter API rate limit hit: {e}")
                print(f"⚠️  Twitter API returned rate limit error!")
                print(f"   This is Twitter's limit, not the bot's internal tracking")
                print(f"   Bot thought it had sent: {len(self.twitter_reply_history)} replies in 15 min")
                # Don't add to history since the tweet wasn't actually sent
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
                successful_deploys = self.db.get_successful_deploys_count()
                
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
            
            # Handle different parse results
            if token_info is None:
                # Not a deployment attempt (no $ symbol)
                # Check if this looks like a deployment attempt before replying
                cleaned_text = tweet_text.replace('@DeployOnKlik', '').strip().lower()
                
                # Only reply if they:
                # 1. Used very explicit deployment keywords
                # 2. The tweet is more than just a few words
                
                # More strict keywords - must be very clear deployment intent
                explicit_keywords = [
                    'deploy', 'launch', 'create token', 'make token', 
                    'ticker:', 'symbol:', 'token name:', 
                    'deploy my', 'launch my', 'create my'
                ]
                has_explicit_keyword = any(keyword in cleaned_text for keyword in explicit_keywords)
                
                # Check if tweet has substance (not just "alpha" or "gm")
                word_count = len(cleaned_text.split())
                has_substance = word_count >= 3  # At least 3 words after removing mention
                
                # Only send format help if VERY clear they're trying to deploy
                if has_explicit_keyword and has_substance:
                    error_msg = "❌ Invalid format. You MUST include $ before the symbol. Use: @DeployOnKlik $SYMBOL or @DeployOnKlik $SYMBOL - Token Name"
                    
                    # Send Twitter reply to help the user
                    await self.send_twitter_reply_format_error(tweet_id, username, tweet_text)
                    
                    return error_msg
                else:
                    # This is just a conversation mention, ignore it
                    self.logger.info(f"Ignoring conversation mention from @{username}: {tweet_text[:100]}")
                    return "✅ Ignored - not a deployment request"
            
            # Check if it's an error response
            elif 'error' in token_info:
                error_type = token_info.get('error_type', 'unknown')
                error_msg = token_info.get('error', 'Invalid format')
                
                if error_type == 'reserved_ticker':
                    # DOK ticker blocked - log but don't reply
                    print(f"🚫 Blocked DOK ticker deployment from @{username} (ignored silently)")
                    self.logger.warning(f"Ignored DOK deployment attempt from @{username}")
                    return "❌ DOK ticker blocked (ignored)"
                
                elif error_type == 'symbol_too_long':
                    symbol = token_info.get('symbol_attempted', '')
                    specific_msg = f"❌ Symbol too long! ${symbol} has {len(symbol)} characters (max 16)"
                    
                    # Send specific error reply
                    await self.send_twitter_reply_specific_error(tweet_id, username, specific_msg)
                    return f"❌ {error_msg}"
                
                elif error_type == 'invalid_characters':
                    symbol = token_info.get('symbol_attempted', '')
                    specific_msg = f"❌ Invalid symbol! ${symbol} contains invalid characters. Use letters and numbers only"
                    
                    # Send specific error reply
                    await self.send_twitter_reply_specific_error(tweet_id, username, specific_msg)
                    return f"❌ {error_msg}"
                
                else:
                    # Generic error
                    await self.send_twitter_reply_format_error(tweet_id, username, tweet_text)
                    return f"❌ {error_msg}"
            
            # Valid token info - proceed with deployment
            else:
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
                
                # Log the deployment request details
                self.logger.info(f"Processing deployment request: @{username} - {tweet_text[:100]}{'...' if len(tweet_text) > 100 else ''}")
                
                # Show deployment preview and ask for confirmation
                print(f"\n📋 DEPLOYMENT PREVIEW")
                print(f"=" * 50)
                print(f"💰 Token: {request.token_name} ({request.token_symbol})")
                print(f"👤 User: @{request.username}")
                print(f"📝 Tweet: {tweet_text[:100]}{'...' if len(tweet_text) > 100 else ''}")
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
                
                # ALWAYS generate vanity salt for 0x69 addresses (not just manual mode!)
                print("\n🔮 Generating vanity address...")
                try:
                    salt, predicted_address = await self.generate_salt_and_address(
                        request.token_name, 
                        request.token_symbol
                    )
                    # Store in request for later use
                    request.salt = salt
                    request.predicted_address = predicted_address
                    
                    print(f"🎯 Vanity address generated: {predicted_address}")
                    print(f"   (Address starts with 0x{predicted_address[2:4]})")
                    
                except Exception as e:
                    print(f"⚠️  Failed to generate vanity address: {e}")
                    print("   Will use random salt instead")
                
                # Only ask for confirmation if running in interactive mode AND they can deploy
                if os.getenv('AUTO_DEPLOY', 'false').lower() != 'true':
                    # Show detailed preview for manual deployments
                    if request.predicted_address:
                        print(f"\n{'='*60}")
                        print(f"🎯 TOKEN WILL BE DEPLOYED AT:")
                        print(f"   {request.predicted_address}")
                        print(f"{'='*60}")
                        print(f"📝 Copy this address NOW to set up buy orders!")
                        print(f"📈 DexScreener: https://dexscreener.com/ethereum/{request.predicted_address}")
                        print(f"⏱️  You have time before confirming deployment")
                        print(f"{'='*60}")
                    
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
                self.db.save_deployment(request)
                
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
        stats = self.db.get_deployment_stats()
        
        return {
            **stats,
            'current_balance': self.get_eth_balance(),
            'user_deposits': self.get_total_user_deposits(),
            'available_balance': self.get_available_balance(),
            'queue_size': self.deployment_queue.qsize(),
            'active_deployments': len(self.active_deployments)
        }
    
    def debug_twitter_rate_limits(self):
        """Debug Twitter rate limit tracking"""
        now = time.time()
        
        # Clean up old entries
        self.twitter_reply_history = [t for t in self.twitter_reply_history if now - t < self.twitter_daily_window]
        
        # Count replies in different windows
        replies_15min = len([t for t in self.twitter_reply_history if now - t < self.twitter_reply_window])
        replies_24h = len([t for t in self.twitter_reply_history if now - t < self.twitter_daily_window])
        
        print("\n🐦 TWITTER RATE LIMIT DEBUG:")
        print(f"   Current time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"   15-min window: {replies_15min}/{self.twitter_reply_limit} replies")
        print(f"   24-hour window: {replies_24h}/{self.twitter_daily_limit} replies")
        print(f"   Total tracked: {len(self.twitter_reply_history)} timestamps")
        
        if self.twitter_reply_history:
            # Show recent entries
            print("\n   Recent reply timestamps:")
            for i, ts in enumerate(self.twitter_reply_history[-10:], 1):
                age_seconds = int(now - ts)
                age_mins = age_seconds // 60
                timestamp = datetime.fromtimestamp(ts).strftime('%H:%M:%S')
                print(f"   {i}. {timestamp} ({age_mins}m {age_seconds % 60}s ago)")
        
        # Check if we would be rate limited
        would_be_limited = replies_15min >= self.twitter_reply_limit or replies_24h >= self.twitter_daily_limit
        print(f"\n   Would be rate limited: {'YES ⚠️' if would_be_limited else 'NO ✅'}")
        
        if would_be_limited:
            if replies_15min >= self.twitter_reply_limit:
                # Calculate when 15-min window will reset
                oldest_15min = min([t for t in self.twitter_reply_history if now - t < self.twitter_reply_window])
                reset_in = int(self.twitter_reply_window - (now - oldest_15min))
                print(f"   15-min limit resets in: {reset_in // 60}m {reset_in % 60}s")
            
            if replies_24h >= self.twitter_daily_limit:
                # Calculate when daily limit will reset
                oldest_24h = min(self.twitter_reply_history)
                reset_in = int(self.twitter_daily_window - (now - oldest_24h))
                print(f"   Daily limit resets in: {reset_in // 3600}h {(reset_in % 3600) // 60}m")
        
        return {
            'replies_15min': replies_15min,
            'replies_24h': replies_24h,
            'is_limited': would_be_limited
        }
    
    def clear_twitter_rate_limits(self):
        """Clear Twitter rate limit history - use for troubleshooting"""
        old_count = len(self.twitter_reply_history)
        self.twitter_reply_history = []
        print(f"🧹 Cleared {old_count} Twitter reply timestamps from rate limit tracking")
        return old_count
    
    def debug_user_deployments(self, username: str):
        """Debug a user's deployment history and cooldown status"""
        print(f"\n🔍 DEBUG: Deployment status for @{username}")
        print("=" * 60)
        
        # Check cooldown status
        can_deploy, msg, cooldown_days = self.db.check_progressive_cooldown(username)
        print(f"Cooldown Status: {'✅ Can deploy' if can_deploy else '❌ In cooldown'}")
        print(f"Message: {msg}")
        if cooldown_days > 0:
            print(f"Days remaining: {cooldown_days}")
        
        # Get recent deployments
        recent = self.db.get_recent_deployments(username, days=7)
        print(f"\nLast 7 days deployments: {len(recent)}")
        for symbol, deployed_at in recent:
            print(f"  - ${symbol} at {deployed_at.strftime('%Y-%m-%d %H:%M')}")
        
        # Check holder status
        is_holder = self.check_holder_status(username)
        print(f"\nHolder Status: {'🎯 YES' if is_holder else '❌ NO'}")
        
        # Check balance
        balance = self.get_user_balance(username)
        print(f"ETH Balance: {balance:.4f} ETH")
        
        print("=" * 60)

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
                
                # Calculate hourly deployment count
                now = datetime.now()
                recent_deploys = [
                    d for d in self.deployment_history 
                    if d > now - timedelta(hours=1)
                ]
                hourly_count = len(recent_deploys)
                hourly_percentage = (hourly_count / self.max_deploys_per_hour) * 100
                
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
                        print(f"   • Hourly Rate: {hourly_count}/{self.max_deploys_per_hour} ({hourly_percentage:.0f}%)")
                        
                        # Show Twitter reply rate
                        current_ts = time.time()
                        twitter_replies = len([t for t in self.twitter_reply_history if current_ts - t < self.twitter_reply_window])
                        twitter_daily = len([t for t in self.twitter_reply_history if current_ts - t < self.twitter_daily_window])
                        twitter_percentage = (twitter_replies / self.twitter_reply_limit) * 100
                        twitter_daily_percentage = (twitter_daily / self.twitter_daily_limit) * 100
                        print(f"   • Twitter Replies: {twitter_replies}/{self.twitter_reply_limit} ({twitter_percentage:.0f}%) in 15min, {twitter_daily}/{self.twitter_daily_limit} ({twitter_daily_percentage:.0f}%) today")
                        
                        print(f"   • Total Balance: {total_balance:.4f} ETH")
                        print(f"   • User Deposits: {user_deposits:.4f} ETH (protected)")
                        print(f"   • Available: {available_balance:.4f} ETH")
                        
                        if twitter_replies >= self.twitter_reply_limit * 0.8:  # 80% of limit
                            print(f"   ⚠️  TWITTER REPLY LIMIT: Only {self.twitter_reply_limit - twitter_replies} replies remaining!")
                        
                        if hourly_count >= self.max_deploys_per_hour * 0.9:  # 90% of limit
                            print(f"   ⚠️  APPROACHING HOURLY LIMIT! Only {self.max_deploys_per_hour - hourly_count} deploys remaining")
                        
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
                    
                    # Show if using vanity address
                    if request.predicted_address:
                        print(f"🎯 Deploying with vanity address: {request.predicted_address}")
                        print(f"   (Starts with 0x{request.predicted_address[2:4]})")
                    
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
        return self.db.get_user_balance(username)
    
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
        is_holder, wallet = self.db.check_holder_status(username)
        
        if not is_holder and wallet:
            # Wallet exists but not marked as holder - check real-time DOK balance
            try:
                from holder_verification import check_holder_status as verify_dok_holder
                
                # Check real-time holder status
                is_holder_now, balance, percentage = verify_dok_holder(wallet)
                
                if is_holder_now:
                    # Update database
                    self.db.update_holder_status(username, True, balance)
                    self.logger.info(f"Updated @{username} to holder status with {balance:.0f} DOK ({percentage:.2f}%) - wallet verified via deposits")
                    return True
            except Exception as e:
                self.logger.error(f"Error checking real-time holder status: {e}")
        
        return is_holder
    
    async def _send_queue_status_reply(self, tweet_id: str, username: str, position: int) -> bool:
        """Send a quick status update about queue position"""
        try:
            # Check Twitter reply rate limit first
            now = time.time()
            self.twitter_reply_history = [t for t in self.twitter_reply_history if now - t < self.twitter_reply_window]
            daily_replies = [t for t in self.twitter_reply_history if now - t < self.twitter_daily_window]
            
            if len(self.twitter_reply_history) >= self.twitter_reply_limit:
                return False
            
            if len(daily_replies) >= self.twitter_daily_limit:
                return False
                
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
                
                if response.data:
                    self.twitter_reply_history.append(time.time())
                    return True
                else:
                    return False
                    
            except Exception:
                return False
            
        except Exception:
            return False
    
    async def send_twitter_reply_instructions(self, tweet_id: str, username: str, instructions: str) -> bool:
        """Reply with instructions to use Telegram when gas is high"""
        try:
            # Check Twitter reply rate limit first
            now = time.time()
            self.twitter_reply_history = [t for t in self.twitter_reply_history if now - t < self.twitter_reply_window]
            
            # Check daily limit
            daily_replies = [t for t in self.twitter_reply_history if now - t < self.twitter_daily_window]
            
            if len(self.twitter_reply_history) >= self.twitter_reply_limit:
                self.logger.warning(f"Twitter instruction reply rate limit: {len(self.twitter_reply_history)}/{self.twitter_reply_limit}")
                return False
            
            if len(daily_replies) >= self.twitter_daily_limit:
                self.logger.warning(f"Twitter daily limit: {len(daily_replies)}/{self.twitter_daily_limit}")
                return False
            
            # SAFETY: Check if this is from the bot itself
            if username.lower() == self.bot_username.lower():
                # Check if this is the first deployment ever
                successful_deploys = self.db.get_successful_deploys_count()
                
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
            if "System limit reached" in instructions:
                # Extract the limit number if possible
                limit_match = re.search(r'\((\d+) deploys/hour\)', instructions)
                limit_num = limit_match.group(1) if limit_match else "30"
                reply_text = f"""@{username} System busy! ({limit_num} deploys/hour limit)

Please try again in a few minutes ⏳

Status: t.me/DeployOnKlik"""
            elif "COOLDOWN" in instructions or "BAN" in instructions:
                # Handle new progressive cooldown messages
                if "SPAM BAN" in instructions:
                    # User tried 5+ deploys in one day - serious spam
                    reply_text = f"""@{username} SPAM BAN! 🚫

5+ attempts in 24 hours is serious abuse.
30-day ban applied.

Learn the rules: t.me/DeployOnKlik"""
                elif "Cooldown violation" in instructions:
                    # User tried to deploy while in cooldown - escalated
                    reply_text = f"""@{username} Cooldown violation! ⚠️

Attempting to deploy during cooldown.
Escalated to 30-day ban.

Follow the rules: t.me/DeployOnKlik"""
                elif "Weekly limit" in instructions:
                    # User has used all 3 free deploys this week
                    cooldown_match = re.search(r'Next free deploy: (\d+) days', instructions)
                    days = cooldown_match.group(1) if cooldown_match else "7"
                    
                    # Get their recent deployments to show WITH ADDRESSES
                    recent_deploys = self.db.get_recent_deployments_with_addresses(username, days=7)
                    
                    if recent_deploys:
                        # Show actual deployments (may be less than 3 if some failed or were deleted)
                        actual_count = len(recent_deploys)
                        deploys_to_show = recent_deploys[:3]  # Show up to 3
                        
                        # ALWAYS show full DexScreener links with ticker
                        deploy_lines = []
                        for symbol, address, _ in deploys_to_show:
                            if address:
                                deploy_lines.append(f"${symbol}: https://dexscreener.com/ethereum/{address}")
                            else:
                                deploy_lines.append(f"${symbol} (no address)")
                        
                        deploy_text = "\n".join(deploy_lines)
                        reply_text = f"""@{username} Used all 3 free deploys this week! 

{deploy_text}

7-day cooldown. Deposit to deploy: t.me/DeployOnKlik"""
                    else:
                        # No deployments found but hit limit (shouldn't happen)
                        reply_text = f"""@{username} Used all 3 free deploys this week!

7-day cooldown applied.
💰 Deposit ETH: t.me/DeployOnKlik
🎯 Hold 5M+ $DOK for 10/week"""
                else:
                    # Generic cooldown message
                    reply_text = f"""@{username} Cooldown active! (3 free/week limit)

Skip cooldown:
💰 Deposit ETH: t.me/DeployOnKlik
🎯 Hold 5M+ $DOK for 10/week"""
            elif "Gas too high" in instructions:
                gas_match = re.search(r'\((\d+\.?\d*) gwei\)', instructions)
                gas_value = gas_match.group(1) if gas_match else "high"
                reply_text = f"""@{username} Gas too high! ({gas_value} gwei)

Free tier: ≤2 gwei only
Deposit ETH for any gas: t.me/DeployOnKlik"""
            elif "Not enough followers" in instructions:
                followers_match = re.search(r'You have: ([\d,]+) followers', instructions)
                follower_count = followers_match.group(1) if followers_match else "?"
                reply_text = f"""@{username} Need 250+ followers for free deploys!

You have: {follower_count}
Or deposit ETH: t.me/DeployOnKlik"""
            elif "already used your free deployment" in instructions or "already deployed" in instructions:
                # Get user's recent deployments to show what they've deployed
                recent_deploys = self.db.get_recent_deployments_with_addresses(username, days=7)
                
                if recent_deploys:
                    # Show their recent deployments with full DexScreener links
                    if len(recent_deploys) == 1:
                        # Single deployment - show full DexScreener link
                        symbol, address, _ = recent_deploys[0]
                        reply_text = f"""@{username} You already deployed ${symbol}!

${symbol}: https://dexscreener.com/ethereum/{address}

Want more? (3 free/week limit)
💰 Deposit: t.me/DeployOnKlik
🎯 Hold $DOK for 10/week"""
                    else:
                        # Multiple deployments - show full DexScreener links with ticker
                        deploy_count = len(recent_deploys[:3])
                        deploy_lines = []
                        for symbol, address, _ in recent_deploys[:3]:
                            if address:
                                deploy_lines.append(f"${symbol}: https://dexscreener.com/ethereum/{address}")
                            else:
                                deploy_lines.append(f"${symbol} (no address)")
                        
                        deploy_text = "\n".join(deploy_lines)
                        reply_text = f"""@{username} Already deployed {deploy_count} this week!

{deploy_text}

Limit: 3/week | Deposit: t.me/DeployOnKlik"""
                else:
                    # Fallback if no deployment found
                    reply_text = f"""@{username} Free deploy already used! (3/week limit)

Want more?
💰 Deposit ETH: t.me/DeployOnKlik
🎯 Hold 5M+ $DOK for 10/week"""
            elif "Holder weekly limit reached" in instructions:
                reply_text = f"""@{username} Holder limit reached (10/10 this week)

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
                    self.twitter_reply_history.append(time.time())
                    return True
                else:
                    return False
                    
            except tweepy.TooManyRequests as e:
                # This is Twitter's API rate limit, not our internal tracking
                self.logger.error(f"Twitter API rate limit hit (instructions): {e}")
                print(f"⚠️  Twitter API returned rate limit error!")
                print(f"   Internal tracking: {len(self.twitter_reply_history)}/{self.twitter_reply_limit}")
                return False
            
        except Exception as e:
            self.logger.error(f"Error sending instruction reply: {e}")
            return False

    async def send_twitter_reply_format_error(self, tweet_id: str, username: str, tweet_text: str) -> bool:
        """Reply with helpful format instructions when user uses wrong format"""
        try:
            # Check Twitter reply rate limit first
            now = time.time()
            self.twitter_reply_history = [t for t in self.twitter_reply_history if now - t < self.twitter_reply_window]
            daily_replies = [t for t in self.twitter_reply_history if now - t < self.twitter_daily_window]
            
            if len(self.twitter_reply_history) >= self.twitter_reply_limit:
                self.logger.warning(f"Twitter format error reply rate limit: {len(self.twitter_reply_history)}/{self.twitter_reply_limit}")
                return False
            
            if len(daily_replies) >= self.twitter_daily_limit:
                self.logger.warning(f"Twitter daily limit: {len(daily_replies)}/{self.twitter_daily_limit}")
                return False
            
            # SAFETY: Check if this is from the bot itself
            if username.lower() == self.bot_username.lower():
                self.logger.warning(f"Skipping format error reply to own tweet from @{username}")
                return False
            
            # Check if we have all OAuth 1.0a credentials
            api_key = os.getenv('TWITTER_API_KEY')
            api_secret = os.getenv('TWITTER_API_SECRET')
            access_token = os.getenv('TWITTER_ACCESS_TOKEN')
            access_token_secret = os.getenv('TWITTER_ACCESS_TOKEN_SECRET')
            
            if not all([api_key, api_secret, access_token, access_token_secret]):
                self.logger.warning("Twitter OAuth credentials not complete - skipping format error reply")
                return False
            
            # Analyze what went wrong
            cleaned_text = tweet_text.replace('@DeployOnKlik', '').strip()
            cleaned_lower = cleaned_text.lower()
            
            # Create helpful reply based on what they did wrong
            if '$' not in tweet_text:
                # Check if they mentioned ticker/symbol in some way
                if any(word in cleaned_lower for word in ['ticker:', 'symbol:', 'token:']):
                    reply_text = f"""@{username} You need a $ before the ticker!

✅ Correct: @DeployOnKlik $GM
✅ Also OK: @DeployOnKlik $GM - Good Morning Token

You tried: "{cleaned_text[:40]}{"..." if len(cleaned_text) > 40 else ""}" """
                else:
                    reply_text = f"""@{username} Missing $ symbol!

✅ Correct: @DeployOnKlik $TICKER
✅ Also OK: @DeployOnKlik $TICKER - Name
✅ Also OK: @DeployOnKlik $TICKER + Name

You sent: "{cleaned_text[:50]}{"..." if len(cleaned_text) > 50 else ""}" """
            else:
                # They have $ but something else is wrong
                reply_text = f"""@{username} Invalid format detected!

✅ Use: @DeployOnKlik $TICKER
✅ Or: @DeployOnKlik $TICKER - Token Name
✅ Or: @DeployOnKlik $TICKER + Token Name

Symbol must be 1-10 letters/numbers only."""
            
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
                    self.logger.info(f"✅ Format error reply sent! Tweet ID: {response.data['id']}")
                    self.twitter_reply_history.append(time.time())
                    print(f"📱 Sent format help reply to @{username}")
                    return True
                else:
                    return False
                    
            except tweepy.TooManyRequests as e:
                # This is Twitter's API rate limit, not our internal tracking
                self.logger.error(f"Twitter API rate limit hit (format error): {e}")
                print(f"⚠️  Twitter API returned rate limit error!")
                print(f"   Internal tracking: {len(self.twitter_reply_history)}/{self.twitter_reply_limit}")
                return False
            except Exception as e:
                self.logger.error(f"Tweepy error sending format reply: {e}")
                return False
            
        except Exception as e:
            self.logger.error(f"Error sending format error reply: {e}")
            return False

    async def send_twitter_reply_specific_error(self, tweet_id: str, username: str, error_message: str) -> bool:
        """Reply with specific error message (symbol too long, invalid chars, etc)"""
        try:
            # Check Twitter reply rate limit first
            now = time.time()
            self.twitter_reply_history = [t for t in self.twitter_reply_history if now - t < self.twitter_reply_window]
            daily_replies = [t for t in self.twitter_reply_history if now - t < self.twitter_daily_window]
            
            if len(self.twitter_reply_history) >= self.twitter_reply_limit:
                self.logger.warning(f"Twitter specific error reply rate limit: {len(self.twitter_reply_history)}/{self.twitter_reply_limit}")
                return False
            
            if len(daily_replies) >= self.twitter_daily_limit:
                self.logger.warning(f"Twitter daily limit: {len(daily_replies)}/{self.twitter_daily_limit}")
                return False
            
            # SAFETY: Check if this is from the bot itself
            if username.lower() == self.bot_username.lower():
                self.logger.warning(f"Skipping specific error reply to own tweet from @{username}")
                return False
            
            # Check if we have all OAuth 1.0a credentials
            api_key = os.getenv('TWITTER_API_KEY')
            api_secret = os.getenv('TWITTER_API_SECRET')
            access_token = os.getenv('TWITTER_ACCESS_TOKEN')
            access_token_secret = os.getenv('TWITTER_ACCESS_TOKEN_SECRET')
            
            if not all([api_key, api_secret, access_token, access_token_secret]):
                self.logger.warning("Twitter OAuth credentials not complete - skipping specific error reply")
                return False
            
            # Create helpful reply based on the specific error
            reply_text = f"""@{username} {error_message}

✅ Valid format: @DeployOnKlik $TICKER
✅ Symbol rules: 1-16 characters, letters/numbers only

Try again with a shorter symbol!"""
            
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
                    self.logger.info(f"✅ Specific error reply sent! Tweet ID: {response.data['id']}")
                    self.twitter_reply_history.append(time.time())
                    print(f"📱 Sent specific error reply to @{username}: {error_message}")
                    return True
                else:
                    return False
                    
            except tweepy.TooManyRequests as e:
                # This is Twitter's API rate limit, not our internal tracking
                self.logger.error(f"Twitter API rate limit hit (specific error): {e}")
                print(f"⚠️  Twitter API returned rate limit error!")
                print(f"   Internal tracking: {len(self.twitter_reply_history)}/{self.twitter_reply_limit}")
                return False
            except Exception as e:
                self.logger.error(f"Tweepy error sending specific error reply: {e}")
                return False
            
        except Exception as e:
            self.logger.error(f"Error sending specific error reply: {e}")
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