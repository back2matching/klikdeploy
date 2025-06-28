#!/usr/bin/env python3
"""
$DOK Token Holder Verification System
Checks if users hold 0.5%+ of supply for holder benefits
"""

import os
import sqlite3
from web3 import Web3
from dotenv import load_dotenv
import logging

load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Token configuration
DOK_TOKEN_ADDRESS = "0x69ca61398eCa94D880393522C1Ef5c3D8c058837"
TOTAL_SUPPLY = 1_000_000_000  # 1 billion tokens
MIN_HOLDER_PERCENTAGE = 0.5  # 0.5% of supply
MIN_HOLDER_AMOUNT = int(TOTAL_SUPPLY * MIN_HOLDER_PERCENTAGE / 100)  # 5,000,000 DOK

# Standard ERC20 ABI for balanceOf
ERC20_ABI = [
    {
        "constant": True,
        "inputs": [{"name": "_owner", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"name": "balance", "type": "uint256"}],
        "type": "function"
    },
    {
        "constant": True,
        "inputs": [],
        "name": "decimals",
        "outputs": [{"name": "", "type": "uint8"}],
        "type": "function"
    },
    {
        "constant": True,
        "inputs": [],
        "name": "totalSupply",
        "outputs": [{"name": "", "type": "uint256"}],
        "type": "function"
    },
    {
        "constant": True,
        "inputs": [],
        "name": "symbol",
        "outputs": [{"name": "", "type": "string"}],
        "type": "function"
    }
]

# Initialize Web3
w3 = Web3(Web3.HTTPProvider(os.getenv('ALCHEMY_RPC_URL')))
if not w3.is_connected():
    raise Exception("Failed to connect to Ethereum")

# Initialize token contract
dok_token = w3.eth.contract(address=DOK_TOKEN_ADDRESS, abi=ERC20_ABI)

def check_holder_status(wallet_address: str) -> tuple[bool, float, float]:
    """
    Check if a wallet holds enough $DOK tokens
    Returns: (is_holder, balance, percentage_of_supply)
    """
    try:
        # Validate address
        if not w3.is_address(wallet_address):
            logger.error(f"Invalid address: {wallet_address}")
            return False, 0, 0
        
        # Convert to checksum address (required by Web3.py)
        checksum_address = w3.to_checksum_address(wallet_address)
        
        # Get token balance
        balance_raw = dok_token.functions.balanceOf(checksum_address).call()
        
        # Get decimals (should be 18 for standard tokens)
        decimals = dok_token.functions.decimals().call()
        
        # Convert to human-readable balance
        balance = balance_raw / (10 ** decimals)
        
        # Calculate percentage of supply
        percentage = (balance / TOTAL_SUPPLY) * 100
        
        # Check if holder
        is_holder = balance >= MIN_HOLDER_AMOUNT
        
        logger.info(f"Wallet {checksum_address}: {balance:,.2f} DOK ({percentage:.4f}% of supply) - Holder: {is_holder}")
        
        return is_holder, balance, percentage
        
    except Exception as e:
        logger.error(f"Error checking holder status for {wallet_address}: {e}")
        return False, 0, 0

def update_all_holder_statuses():
    """Update holder status for all users with registered wallets"""
    conn = sqlite3.connect('deployments.db')
    
    try:
        # Get all users with wallets
        cursor = conn.execute(
            "SELECT twitter_username, eth_address FROM users WHERE eth_address IS NOT NULL"
        )
        users = cursor.fetchall()
        
        updated = 0
        new_holders = []
        lost_holders = []
        
        for username, wallet in users:
            # Get current holder status
            cursor = conn.execute(
                "SELECT is_holder FROM users WHERE twitter_username = ?",
                (username,)
            )
            current_status = cursor.fetchone()[0]
            
            # Check actual holder status
            is_holder, balance, percentage = check_holder_status(wallet)
            
            # Update if changed
            if is_holder != current_status:
                conn.execute(
                    "UPDATE users SET is_holder = ?, holder_balance = ? WHERE twitter_username = ?",
                    (is_holder, balance, username)
                )
                updated += 1
                
                if is_holder:
                    new_holders.append(f"@{username} ({balance:,.0f} DOK - {percentage:.2f}%)")
                else:
                    lost_holders.append(f"@{username}")
            else:
                # Update balance anyway
                conn.execute(
                    "UPDATE users SET holder_balance = ? WHERE twitter_username = ?",
                    (balance, username)
                )
        
        conn.commit()
        
        # Report results
        print("\n🔍 HOLDER STATUS UPDATE COMPLETE")
        print("=" * 50)
        print(f"✅ Checked {len(users)} users")
        print(f"📊 Updated {updated} holder statuses")
        print(f"💎 Minimum holder amount: {MIN_HOLDER_AMOUNT:,} DOK ({MIN_HOLDER_PERCENTAGE}%)")
        
        if new_holders:
            print(f"\n🎯 NEW HOLDERS ({len(new_holders)}):")
            for holder in new_holders:
                print(f"   • {holder}")
        
        if lost_holders:
            print(f"\n❌ LOST HOLDER STATUS ({len(lost_holders)}):")
            for user in lost_holders:
                print(f"   • {user}")
        
        # Show current holder stats
        cursor = conn.execute(
            "SELECT COUNT(*) FROM users WHERE is_holder = 1"
        )
        total_holders = cursor.fetchone()[0]
        
        cursor = conn.execute(
            "SELECT twitter_username, holder_balance FROM users WHERE is_holder = 1 ORDER BY holder_balance DESC LIMIT 10"
        )
        top_holders = cursor.fetchall()
        
        print(f"\n📊 HOLDER STATISTICS")
        print("=" * 50)
        print(f"Total $DOK holders: {total_holders}")
        
        if top_holders:
            print("\nTop 10 Holders:")
            for i, (username, balance) in enumerate(top_holders, 1):
                percentage = (balance / TOTAL_SUPPLY) * 100
                print(f"   {i}. @{username}: {balance:,.0f} DOK ({percentage:.2f}%)")
        
    except Exception as e:
        logger.error(f"Error updating holder statuses: {e}")
        conn.rollback()
    finally:
        conn.close()

def verify_specific_user(twitter_username: str):
    """Verify holder status for a specific user"""
    conn = sqlite3.connect('deployments.db')
    
    try:
        # Get user's wallet
        cursor = conn.execute(
            "SELECT eth_address FROM users WHERE LOWER(twitter_username) = LOWER(?)",
            (twitter_username,)
        )
        result = cursor.fetchone()
        
        if not result or not result[0]:
            print(f"❌ User @{twitter_username} not found or no wallet registered")
            return
        
        wallet = result[0]
        
        # Check holder status
        is_holder, balance, percentage = check_holder_status(wallet)
        
        # Update database
        conn.execute(
            "UPDATE users SET is_holder = ?, holder_balance = ? WHERE LOWER(twitter_username) = LOWER(?)",
            (is_holder, balance, twitter_username)
        )
        conn.commit()
        
        # Display results
        print(f"\n📊 HOLDER VERIFICATION: @{twitter_username}")
        print("=" * 50)
        print(f"Wallet: {wallet}")
        print(f"Balance: {balance:,.2f} DOK")
        print(f"Percentage: {percentage:.4f}% of supply")
        print(f"Required: {MIN_HOLDER_AMOUNT:,} DOK ({MIN_HOLDER_PERCENTAGE}%)")
        print(f"Status: {'✅ HOLDER' if is_holder else '❌ NOT A HOLDER'}")
        
        if is_holder:
            # Check if wallet has deposited
            cursor = conn.execute(
                "SELECT COUNT(*) FROM deposits WHERE LOWER(twitter_username) = LOWER(?) AND LOWER(from_address) = LOWER(?) AND confirmed = 1",
                (twitter_username, wallet)
            )
            deposit_count = cursor.fetchone()[0]
            
            if deposit_count > 0:
                print(f"\n🎯 Holder Benefits ACTIVE:")
                print(f"   • 2 FREE deployments per day (gas ≤ 15 gwei)")
                print(f"   • NO platform fees (save 0.01 ETH per deploy)")
                print(f"   • Priority support")
                print(f"   • Wallet verified ✅ ({deposit_count} deposits)")
            else:
                print(f"\n⚠️  Holder Benefits INACTIVE:")
                print(f"   You have {balance:,.0f} DOK but wallet not verified!")
                print(f"   **Deposit 0.03+ ETH from this wallet to verify ownership**")
                print(f"   This security measure prevents wallet theft.")
        else:
            needed = MIN_HOLDER_AMOUNT - balance
            print(f"\n💡 Need {needed:,.0f} more DOK to become a holder")
        
    except Exception as e:
        logger.error(f"Error verifying user: {e}")
    finally:
        conn.close()

def get_token_info():
    """Get basic token information"""
    try:
        symbol = dok_token.functions.symbol().call()
        decimals = dok_token.functions.decimals().call()
        total_supply_raw = dok_token.functions.totalSupply().call()
        total_supply = total_supply_raw / (10 ** decimals)
        
        print(f"\n🪙 TOKEN INFORMATION")
        print("=" * 50)
        print(f"Token: {symbol}")
        print(f"Address: {DOK_TOKEN_ADDRESS}")
        print(f"Total Supply: {total_supply:,.0f}")
        print(f"Decimals: {decimals}")
        print(f"Holder Requirement: {MIN_HOLDER_AMOUNT:,} {symbol} ({MIN_HOLDER_PERCENTAGE}%)")
        
    except Exception as e:
        logger.error(f"Error getting token info: {e}")

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        if sys.argv[1] == "update":
            # Update all holder statuses
            update_all_holder_statuses()
        elif sys.argv[1] == "info":
            # Show token info
            get_token_info()
        else:
            # Verify specific user
            verify_specific_user(sys.argv[1])
    else:
        print("Usage:")
        print("  python holder_verification.py update     - Update all holder statuses")
        print("  python holder_verification.py info       - Show token information")
        print("  python holder_verification.py username   - Check specific user")
        print("\nExample:")
        print("  python holder_verification.py deployonklik") 