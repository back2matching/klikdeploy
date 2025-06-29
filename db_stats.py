#!/usr/bin/env python3
"""
Klik Finance Database Stats Tool
All-in-one stats viewer and exporter
"""

import sqlite3
import os
import csv
import sys
from datetime import datetime
from typing import Dict, List

# ANSI color codes (disable on Windows if issues)
ENABLE_COLORS = os.name != 'nt' or os.environ.get('ANSICON')

class Colors:
    if ENABLE_COLORS:
        GREEN = '\033[92m'
        YELLOW = '\033[93m'
        RED = '\033[91m'
        CYAN = '\033[96m'
        BOLD = '\033[1m'
        ENDC = '\033[0m'
    else:
        GREEN = YELLOW = RED = CYAN = BOLD = ENDC = ''

def format_eth(amount: float) -> str:
    """Format ETH amount"""
    return f"{amount:.4f} ETH"

def format_address(address: str) -> str:
    """Format ETH address for display"""
    if not address:
        return "None"
    return f"{address[:6]}...{address[-4:]}"

def print_section(title: str):
    """Print section header"""
    print(f"\n{Colors.CYAN}{Colors.BOLD}{title}{Colors.ENDC}")
    print("-" * 40)

def quick_stats():
    """Display quick overview stats"""
    if not os.path.exists("deployments.db"):
        print(f"{Colors.RED}❌ Database not found!{Colors.ENDC}")
        return
    
    conn = sqlite3.connect("deployments.db")
    conn.row_factory = sqlite3.Row
    
    print(f"\n{Colors.BOLD}{'='*60}{Colors.ENDC}")
    print(f"{Colors.BOLD}KLIK FINANCE - QUICK STATS{Colors.ENDC}".center(60))
    print(f"{Colors.BOLD}{'='*60}{Colors.ENDC}")
    
    # Deployments
    cursor = conn.execute("""
        SELECT 
            COUNT(*) as total,
            SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) as successful,
            SUM(CASE WHEN date(requested_at) = date('now') THEN 1 ELSE 0 END) as today
        FROM deployments
    """)
    row = cursor.fetchone()
    
    print_section("📊 DEPLOYMENTS")
    print(f"Total: {row['total']:,} | Success: {row['successful']:,} | Today: {row['today']}")
    
    # Users
    cursor = conn.execute("""
        SELECT 
            COUNT(*) as total,
            SUM(CASE WHEN is_holder THEN 1 ELSE 0 END) as holders,
            SUM(balance) as total_balance
        FROM users
    """)
    row = cursor.fetchone()
    
    print_section("👥 USERS")
    print(f"Total: {row['total']:,} | Holders: {row['holders']} | Balance: {format_eth(row['total_balance'] or 0)}")
    
    # Recent activity
    print_section("🚀 RECENT DEPLOYMENTS")
    cursor = conn.execute("""
        SELECT token_symbol, username, deployed_at
        FROM deployments
        WHERE status = 'success'
        ORDER BY deployed_at DESC
        LIMIT 5
    """)
    
    for row in cursor.fetchall():
        date = datetime.fromisoformat(row['deployed_at']).strftime("%m/%d %H:%M")
        print(f"${row['token_symbol']:<8} by @{row['username']:<15} ({date})")
    
    # Self-Claim Fees Quick Stats
    print_section("💰 SELF-CLAIM FEES")
    
    # Check for both tables
    cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='user_fee_settings'")
    settings_table_exists = cursor.fetchone() is not None
    
    cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='deployment_fees'")  
    fees_table_exists = cursor.fetchone() is not None
    
    if settings_table_exists and fees_table_exists:
        try:
            # Get self-claim users count (handle empty table)
            cursor = conn.execute("SELECT COUNT(*) as count FROM user_fee_settings WHERE fee_capture_enabled = 1")
            self_claim_users = cursor.fetchone()['count'] or 0
            
            # Get total claimable fees
            cursor = conn.execute("SELECT SUM(user_claimable_amount) as total FROM deployment_fees WHERE user_claimable_amount > 0")
            result = cursor.fetchone()
            total_claimable = result['total'] if result and result['total'] else 0
            
            # Get tracked deployments count
            cursor = conn.execute("SELECT COUNT(*) as count FROM deployment_fees")
            tracked_deployments = cursor.fetchone()['count'] or 0
            
            print(f"Self-Claim Users: {self_claim_users} | Tracked Deployments: {tracked_deployments} | Claimable: {format_eth(total_claimable)}")
            
        except Exception as e:
            print(f"Error in fee stats: {e}")
            # Fallback to simple message
            print("✅ Self-claim system ready - no fees claimed yet")
    elif not settings_table_exists or not fees_table_exists:
        print("Not migrated - run: python migrate_self_claim_fees.py")
    else:
        print("✅ Self-claim system ready - waiting for user activity")
    
    conn.close()

def detailed_stats():
    """Display detailed statistics"""
    if not os.path.exists("deployments.db"):
        print(f"{Colors.RED}❌ Database not found!{Colors.ENDC}")
        return
    
    conn = sqlite3.connect("deployments.db")
    conn.row_factory = sqlite3.Row
    
    print(f"\n{Colors.BOLD}{'='*70}{Colors.ENDC}")
    print(f"{Colors.BOLD}KLIK FINANCE - DETAILED STATISTICS{Colors.ENDC}".center(70))
    print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}".center(70))
    print(f"{Colors.BOLD}{'='*70}{Colors.ENDC}")
    
    # 1. Deployment Stats
    print_section("📊 DEPLOYMENT OVERVIEW")
    cursor = conn.execute("""
        SELECT 
            COUNT(*) as total,
            SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) as successful,
            SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed,
            SUM(CASE WHEN date(requested_at) = date('now') THEN 1 ELSE 0 END) as today,
            SUM(CASE WHEN date(requested_at) >= date('now', '-7 days') THEN 1 ELSE 0 END) as week,
            SUM(CASE WHEN date(requested_at) >= date('now', 'start of month') THEN 1 ELSE 0 END) as month
        FROM deployments
    """)
    row = cursor.fetchone()
    
    success_rate = (row['successful'] / row['total'] * 100) if row['total'] > 0 else 0
    
    print(f"Total Deployments: {row['total']:,}")
    print(f"  ✅ Successful: {row['successful']:,} ({success_rate:.1f}%)")
    print(f"  ❌ Failed: {row['failed']:,}")
    print(f"\nTime Periods:")
    print(f"  Today: {row['today']} | This Week: {row['week']} | This Month: {row['month']}")
    
    # 2. Financial Stats
    print_section("💰 FINANCIAL OVERVIEW")
    
    # User balances
    cursor = conn.execute("SELECT SUM(balance) as total FROM users")
    total_balance = cursor.fetchone()['total'] or 0
    print(f"Total User Balances: {format_eth(total_balance)}")
    
    # Revenue breakdown (if balance_sources exists)
    cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='balance_sources'")
    if cursor.fetchone():
        cursor = conn.execute("""
            SELECT source_type, SUM(amount) as total, COUNT(*) as count
            FROM balance_sources
            GROUP BY source_type
        """)
        print("\nRevenue Sources:")
        for row in cursor.fetchall():
            source = row['source_type'].replace('_', ' ').title()
            print(f"  • {source}: {format_eth(row['total'])} ({row['count']} transactions)")
    
    # 3. Self-Claim Fees Overview
    print_section("💰 SELF-CLAIM FEES SYSTEM")
    
    # Check if new tables exist
    cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='user_fee_settings'")
    if cursor.fetchone():
        # Fee capture preferences
        cursor = conn.execute("""
            SELECT 
                COUNT(*) as total_users,
                SUM(CASE WHEN fee_capture_enabled = 1 THEN 1 ELSE 0 END) as self_claim_enabled,
                SUM(CASE WHEN fee_capture_enabled = 0 THEN 1 ELSE 0 END) as community_split
            FROM user_fee_settings
        """)
        fee_prefs = cursor.fetchone()
        
        if fee_prefs['total_users'] > 0:
            print(f"Fee Capture Preferences:")
            print(f"  Self-Claim Enabled: {fee_prefs['self_claim_enabled']} users")
            print(f"  Community Split: {fee_prefs['community_split']} users")
        else:
            print("No fee capture preferences set yet")
        
        # Deployment fees stats
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='deployment_fees'")
        if cursor.fetchone():
            cursor = conn.execute("""
                SELECT 
                    COUNT(*) as total_deployments,
                    COUNT(DISTINCT username) as unique_users,
                    SUM(CASE WHEN user_claimable_amount > 0 THEN user_claimable_amount ELSE 0 END) as total_claimable,
                    SUM(claimed_amount) as total_claimed,
                    COUNT(CASE WHEN status = 'claimable' THEN 1 END) as pending_claims
                FROM deployment_fees
            """)
            fee_stats = cursor.fetchone()
            
            print(f"\nDeployment Fee Statistics:")
            print(f"  Tracked Deployments: {fee_stats['total_deployments']:,}")
            print(f"  Users with Fees: {fee_stats['unique_users']}")
            print(f"  Total Claimable: {format_eth(fee_stats['total_claimable'] or 0)}")
            print(f"  Total Claimed: {format_eth(fee_stats['total_claimed'] or 0)}")
            print(f"  Pending Claims: {fee_stats['pending_claims']}")
            
            # Top users with claimable fees
            cursor = conn.execute("""
                SELECT username, SUM(user_claimable_amount) as claimable
                FROM deployment_fees
                WHERE user_claimable_amount > 0
                GROUP BY username
                ORDER BY claimable DESC
                LIMIT 5
            """)
            
            top_claimers = cursor.fetchall()
            if top_claimers:
                print(f"\nTop Users with Claimable Fees:")
                for i, row in enumerate(top_claimers, 1):
                    print(f"  {i}. @{row['username']}: {format_eth(row['claimable'])}")
    else:
        print("Self-claim fees system not yet migrated")
        print("Run: python migrate_self_claim_fees.py")
    
    # 4. Top Users
    print_section("🏆 TOP DEPLOYERS")
    cursor = conn.execute("""
        SELECT username, COUNT(*) as count,
               SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) as successful
        FROM deployments
        GROUP BY username
        ORDER BY successful DESC
        LIMIT 10
    """)
    
    for i, row in enumerate(cursor.fetchall(), 1):
        print(f"{i:2}. @{row['username']:<20} - {row['successful']} successful ({row['count']} total)")
    
    # 5. Popular Tokens
    print_section("🪙 MOST DEPLOYED TOKENS")
    cursor = conn.execute("""
        SELECT token_symbol, COUNT(*) as count
        FROM deployments
        WHERE status = 'success'
        GROUP BY token_symbol
        ORDER BY count DESC
        LIMIT 10
    """)
    
    for i, row in enumerate(cursor.fetchall(), 1):
        bar = "█" * min(20, row['count'])
        print(f"{i:2}. ${row['token_symbol']:<10} {bar} {row['count']}")
    
    # 6. Daily Trend
    print_section("📈 LAST 7 DAYS TREND")
    cursor = conn.execute("""
        SELECT 
            date(requested_at) as date,
            COUNT(*) as count
        FROM deployments
        WHERE date(requested_at) >= date('now', '-7 days')
        GROUP BY date(requested_at)
        ORDER BY date
    """)
    
    for row in cursor.fetchall():
        date = datetime.strptime(row['date'], '%Y-%m-%d').strftime('%a %m/%d')
        bar = "▓" * min(30, row['count'] * 2)
        print(f"{date}: {bar} {row['count']}")
    
    conn.close()

def user_verification_report():
    """Display detailed user verification and registration status"""
    if not os.path.exists("deployments.db"):
        print(f"{Colors.RED}❌ Database not found!{Colors.ENDC}")
        return
    
    conn = sqlite3.connect("deployments.db")
    conn.row_factory = sqlite3.Row
    
    print(f"\n{Colors.BOLD}{'='*80}{Colors.ENDC}")
    print(f"{Colors.BOLD}KLIK FINANCE - USER VERIFICATION & REGISTRATION REPORT{Colors.ENDC}".center(80))
    print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}".center(80))
    print(f"{Colors.BOLD}{'='*80}{Colors.ENDC}")
    
    # 1. Verification Overview
    print_section("🔐 VERIFICATION OVERVIEW")
    cursor = conn.execute("""
        SELECT 
            COUNT(*) as total_users,
            SUM(CASE WHEN twitter_verified = 1 THEN 1 ELSE 0 END) as verified_users,
            SUM(CASE WHEN twitter_verified = 0 THEN 1 ELSE 0 END) as unverified_users,
            SUM(CASE WHEN twitter_verified = 0 AND balance > 0 THEN 1 ELSE 0 END) as unverified_with_balance,
            SUM(CASE WHEN twitter_verified = 0 AND verification_code IS NOT NULL THEN 1 ELSE 0 END) as pending_verification
        FROM users
    """)
    row = cursor.fetchone()
    
    print(f"Total Users: {row['total_users']:,}")
    print(f"  ✅ Verified: {row['verified_users']} ({(row['verified_users']/row['total_users']*100):.1f}%)")
    print(f"  ❓ Unverified: {row['unverified_users']}")
    print(f"  ⚠️  Unverified with Balance: {row['unverified_with_balance']}")
    print(f"  🔄 Pending Verification: {row['pending_verification']}")
    
    # 2. Account Linking Status
    print_section("🔗 ACCOUNT LINKING STATUS")
    cursor = conn.execute("""
        SELECT 
            COUNT(*) as total,
            SUM(CASE WHEN eth_address IS NOT NULL THEN 1 ELSE 0 END) as with_wallet,
            SUM(CASE WHEN telegram_id IS NOT NULL THEN 1 ELSE 0 END) as with_telegram,
            SUM(CASE WHEN eth_address IS NOT NULL AND telegram_id IS NOT NULL THEN 1 ELSE 0 END) as fully_linked
        FROM users
    """)
    row = cursor.fetchone()
    
    print(f"Account Linking Statistics:")
    print(f"  💳 With Wallet: {row['with_wallet']}/{row['total']} ({(row['with_wallet']/row['total']*100):.1f}%)")
    print(f"  📱 With Telegram: {row['with_telegram']}/{row['total']} ({(row['with_telegram']/row['total']*100):.1f}%)")
    print(f"  🔗 Fully Linked: {row['fully_linked']}/{row['total']} ({(row['fully_linked']/row['total']*100):.1f}%)")
    
    # 3. Self-Claim Fee Settings
    print_section("💰 SELF-CLAIM FEE SETTINGS")
    
    # Check if fee settings table exists
    cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='user_fee_settings'")
    if cursor.fetchone():
        cursor = conn.execute("""
            SELECT 
                COUNT(*) as total_settings,
                SUM(CASE WHEN fee_capture_enabled = 1 THEN 1 ELSE 0 END) as self_claim_enabled,
                SUM(CASE WHEN fee_capture_enabled = 0 THEN 1 ELSE 0 END) as community_split
            FROM user_fee_settings
        """)
        settings = cursor.fetchone()
        
        # Get verified users without fee settings
        cursor = conn.execute("""
            SELECT COUNT(*) as count
            FROM users u
            LEFT JOIN user_fee_settings ufs ON u.twitter_username = ufs.username
            WHERE u.twitter_verified = 1 AND ufs.username IS NULL
        """)
        verified_no_settings = cursor.fetchone()['count']
        
        print(f"Fee Capture Settings:")
        print(f"  🔧 Self-Claim Enabled: {settings['self_claim_enabled']}")
        print(f"  🤝 Community Split: {settings['community_split']}")
        print(f"  ❓ Verified Users w/o Settings: {verified_no_settings}")
    else:
        print("❌ Fee settings table not found - run migration")
    
    # 4. Detailed User List - Verified Users
    print_section("✅ VERIFIED USERS")
    cursor = conn.execute("""
        SELECT 
            u.twitter_username,
            u.eth_address,
            u.telegram_id,
            u.balance,
            u.is_holder,
            COALESCE(ufs.fee_capture_enabled, 0) as fee_capture_enabled,
            (SELECT COUNT(*) FROM deployments d WHERE d.username = u.twitter_username AND d.status = 'success') as deployments
        FROM users u
        LEFT JOIN user_fee_settings ufs ON u.twitter_username = ufs.username
        WHERE u.twitter_verified = 1
        ORDER BY u.balance DESC, deployments DESC
    """)
    
    verified_users = cursor.fetchall()
    if verified_users:
        print(f"{'Username':<20} {'Wallet':<12} {'TG ID':<12} {'Balance':<12} {'Holder':<8} {'Fee Mode':<12} {'Deploys'}")
        print("-" * 95)
        for user in verified_users:
            username = user['twitter_username'][:18]
            wallet = format_address(user['eth_address'])
            tg_id = str(user['telegram_id']) if user['telegram_id'] else "None"
            tg_id = tg_id[:10] + "..." if len(tg_id) > 10 else tg_id
            balance = format_eth(user['balance'] or 0)
            holder = "YES" if user['is_holder'] else "NO"
            fee_mode = "Self-Claim" if user['fee_capture_enabled'] else "Community"
            deploys = user['deployments']
            
            print(f"@{username:<19} {wallet:<12} {tg_id:<12} {balance:<12} {holder:<8} {fee_mode:<12} {deploys}")
    else:
        print("No verified users found")
    
    # 5. Unverified Users with Balance (Security Risk)
    print_section("⚠️  UNVERIFIED USERS WITH BALANCE")
    cursor = conn.execute("""
        SELECT 
            u.twitter_username,
            u.eth_address,
            u.telegram_id,
            u.balance,
            u.verification_code,
            (SELECT COUNT(*) FROM deployments d WHERE d.username = u.twitter_username AND d.status = 'success') as deployments,
            (SELECT SUM(amount) FROM deposits dep WHERE dep.twitter_username = u.twitter_username AND dep.confirmed = 1) as total_deposits
        FROM users u
        WHERE u.twitter_verified = 0 AND u.balance > 0
        ORDER BY u.balance DESC
    """)
    
    unverified_users = cursor.fetchall()
    if unverified_users:
        print(f"{'Username':<20} {'Wallet':<12} {'TG ID':<12} {'Balance':<12} {'Deposits':<12} {'Code':<10} {'Deploys'}")
        print("-" * 100)
        for user in unverified_users:
            username = user['twitter_username'][:18]
            wallet = format_address(user['eth_address'])
            tg_id = str(user['telegram_id']) if user['telegram_id'] else "None"
            tg_id = tg_id[:10] + "..." if len(tg_id) > 10 else tg_id
            balance = format_eth(user['balance'] or 0)
            deposits = format_eth(user['total_deposits'] or 0)
            code = user['verification_code'][:8] if user['verification_code'] else "None"
            deploys = user['deployments']
            
            print(f"@{username:<19} {wallet:<12} {tg_id:<12} {balance:<12} {deposits:<12} {code:<10} {deploys}")
    else:
        print("✅ No unverified users with balance")
    
    # 6. Pending Verifications
    print_section("🔄 PENDING VERIFICATIONS")
    cursor = conn.execute("""
        SELECT 
            u.twitter_username,
            u.verification_code,
            u.balance,
            u.telegram_id,
            (SELECT COUNT(*) FROM deployments d WHERE d.username = u.twitter_username AND d.status = 'success') as deployments
        FROM users u
        WHERE u.twitter_verified = 0 AND u.verification_code IS NOT NULL
        ORDER BY u.balance DESC
    """)
    
    pending_users = cursor.fetchall()
    if pending_users:
        print(f"These users have requested verification but haven't tweeted the code yet:")
        print(f"{'Username':<20} {'Code':<10} {'Balance':<12} {'TG ID':<12} {'Deploys'}")
        print("-" * 70)
        for user in pending_users:
            username = user['twitter_username'][:18]
            code = user['verification_code']
            balance = format_eth(user['balance'] or 0)
            tg_id = str(user['telegram_id']) if user['telegram_id'] else "None"
            tg_id = tg_id[:10] + "..." if len(tg_id) > 10 else tg_id
            deploys = user['deployments']
            
            print(f"@{username:<19} {code:<10} {balance:<12} {tg_id:<12} {deploys}")
    else:
        print("No pending verifications")
    
    # 7. Fee Statistics by User
    cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='deployment_fees'")
    if cursor.fetchone():
        print_section("💰 TOP USERS BY CLAIMABLE FEES")
        cursor = conn.execute("""
            SELECT 
                df.username,
                u.twitter_verified,
                SUM(df.user_claimable_amount) as total_claimable,
                SUM(df.claimed_amount) as total_claimed,
                COUNT(*) as deployments_with_fees
            FROM deployment_fees df
            LEFT JOIN users u ON df.username = u.twitter_username
            WHERE df.user_claimable_amount > 0 OR df.claimed_amount > 0
            GROUP BY df.username
            ORDER BY total_claimable DESC
            LIMIT 10
        """)
        
        fee_users = cursor.fetchall()
        if fee_users:
            print(f"{'Username':<20} {'Verified':<10} {'Claimable':<12} {'Claimed':<12} {'Tokens'}")
            print("-" * 70)
            for user in fee_users:
                username = user['username'][:18]
                verified = "✅ YES" if user['twitter_verified'] else "❌ NO"
                claimable = format_eth(user['total_claimable'] or 0)
                claimed = format_eth(user['total_claimed'] or 0)
                tokens = user['deployments_with_fees']
                
                print(f"@{username:<19} {verified:<10} {claimable:<12} {claimed:<12} {tokens}")
        else:
            print("No users with fees found")
    
    conn.close()

def account_security_audit():
    """Perform security audit of user accounts"""
    if not os.path.exists("deployments.db"):
        print(f"{Colors.RED}❌ Database not found!{Colors.ENDC}")
        return
    
    conn = sqlite3.connect("deployments.db")
    conn.row_factory = sqlite3.Row
    
    print(f"\n{Colors.BOLD}{'='*70}{Colors.ENDC}")
    print(f"{Colors.BOLD}KLIK FINANCE - ACCOUNT SECURITY AUDIT{Colors.ENDC}".center(70))
    print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}".center(70))
    print(f"{Colors.BOLD}{'='*70}{Colors.ENDC}")
    
    # 1. Security Risk Assessment
    print_section("🚨 SECURITY RISKS")
    
    # High-value unverified accounts
    cursor = conn.execute("""
        SELECT COUNT(*) as count, SUM(balance) as total_balance
        FROM users
        WHERE twitter_verified = 0 AND balance >= 0.01
    """)
    risk = cursor.fetchone()
    
    if risk['count'] > 0:
        print(f"⚠️  HIGH RISK: {risk['count']} unverified users with ≥0.01 ETH")
        print(f"   Total at risk: {format_eth(risk['total_balance'])}")
    else:
        print("✅ No high-value unverified accounts")
    
    # Users with deposits but no verification
    cursor = conn.execute("""
        SELECT COUNT(DISTINCT u.twitter_username) as count
        FROM users u
        INNER JOIN deposits d ON u.twitter_username = d.twitter_username
        WHERE u.twitter_verified = 0 AND d.confirmed = 1
    """)
    depositors = cursor.fetchone()['count']
    
    if depositors > 0:
        print(f"⚠️  MEDIUM RISK: {depositors} users deposited but never verified")
    else:
        print("✅ All depositors have verified accounts")
    
    # 2. Wallet Verification Status
    print_section("💳 WALLET VERIFICATION")
    
    # Check users with wallets vs deposit history
    cursor = conn.execute("""
        SELECT 
            u.twitter_username,
            u.eth_address,
            u.balance,
            u.twitter_verified,
            (SELECT COUNT(*) FROM deposits d WHERE d.twitter_username = u.twitter_username AND LOWER(d.from_address) = LOWER(u.eth_address) AND d.confirmed = 1) as verified_deposits,
            (SELECT COUNT(*) FROM deposits d WHERE d.twitter_username = u.twitter_username AND d.confirmed = 1) as total_deposits
        FROM users u
        WHERE u.eth_address IS NOT NULL AND u.balance > 0
        ORDER BY u.balance DESC
    """)
    
    wallet_users = cursor.fetchall()
    verified_wallets = 0
    unverified_wallets = 0
    
    print(f"Wallet Ownership Verification:")
    for user in wallet_users:
        if user['verified_deposits'] > 0:
            verified_wallets += 1
        else:
            unverified_wallets += 1
    
    print(f"  ✅ Verified Ownership: {verified_wallets} users")
    print(f"  ❓ Unverified Ownership: {unverified_wallets} users")
    
    # 3. Suspicious Patterns
    print_section("🔍 SUSPICIOUS PATTERNS")
    
    # Multiple accounts from same Telegram
    cursor = conn.execute("""
        SELECT telegram_id, COUNT(*) as account_count, GROUP_CONCAT(twitter_username) as usernames
        FROM users
        WHERE telegram_id IS NOT NULL
        GROUP BY telegram_id
        HAVING COUNT(*) > 1
    """)
    
    multi_accounts = cursor.fetchall()
    if multi_accounts:
        print(f"Multiple Twitter accounts per Telegram:")
        for account in multi_accounts:
            usernames = account['usernames'].split(',')
            print(f"  TG {account['telegram_id']}: {len(usernames)} accounts ({', '.join(['@' + u for u in usernames[:3]])}{'...' if len(usernames) > 3 else ''})")
    else:
        print("✅ No multiple accounts per Telegram found")
    
    # Same wallet, different users
    cursor = conn.execute("""
        SELECT eth_address, COUNT(*) as user_count, GROUP_CONCAT(twitter_username) as usernames
        FROM users
        WHERE eth_address IS NOT NULL
        GROUP BY LOWER(eth_address)
        HAVING COUNT(*) > 1
    """)
    
    shared_wallets = cursor.fetchall()
    if shared_wallets:
        print(f"\nShared wallets:")
        for wallet in shared_wallets:
            usernames = wallet['usernames'].split(',')
            print(f"  {format_address(wallet['eth_address'])}: {len(usernames)} users ({', '.join(['@' + u for u in usernames])})")
    else:
        print("✅ No shared wallets found")
    
    conn.close()

def export_data():
    """Export database to CSV files"""
    if not os.path.exists("deployments.db"):
        print(f"{Colors.RED}❌ Database not found!{Colors.ENDC}")
        return
    
    conn = sqlite3.connect("deployments.db")
    
    # Create export directory
    export_dir = f"klik_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    os.makedirs(export_dir, exist_ok=True)
    
    print(f"\n📁 Exporting to: {export_dir}/")
    print("="*50)
    
    # Updated table list to include new self-claim fees tables
    tables = [
        "deployments", "users", "deposits", "daily_limits", 
        "balance_sources", "fee_claims", "user_fee_settings", "deployment_fees"
    ]
    exported_count = 0
    
    for table in tables:
        cursor = conn.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table}'")
        if not cursor.fetchone():
            continue
            
        try:
            cursor = conn.execute(f"SELECT * FROM {table}")
            rows = cursor.fetchall()
            
            if rows:
                filename = os.path.join(export_dir, f"{table}.csv")
                with open(filename, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    headers = [description[0] for description in cursor.description]
                    writer.writerow(headers)
                    writer.writerows(rows)
                
                print(f"✅ {table}.csv - {len(rows)} rows")
                exported_count += 1
        except Exception as e:
            print(f"❌ Error exporting {table}: {e}")
    
    # Create summary
    if exported_count > 0:
        summary_file = os.path.join(export_dir, "SUMMARY.txt")
        with open(summary_file, 'w') as f:
            f.write(f"Klik Finance Database Export\n")
            f.write(f"Generated: {datetime.now()}\n")
            f.write(f"Files exported: {exported_count}\n")
            f.write(f"Includes self-claim fees data\n")
        
        print(f"\n✅ Export complete! {exported_count} tables exported.")
    else:
        print(f"{Colors.YELLOW}⚠️  No data to export{Colors.ENDC}")
        os.rmdir(export_dir)
    
    conn.close()

def main():
    """Main menu"""
    while True:
        print(f"\n{Colors.BOLD}📊 KLIK FINANCE DATABASE STATS{Colors.ENDC}")
        print("="*35)
        print("1. Quick Stats")
        print("2. Detailed Analysis")
        print("3. User Verification Report")
        print("4. Account Security Audit")
        print("5. Export to CSV")
        print("0. Exit")
        
        choice = input(f"\n{Colors.CYAN}Select option: {Colors.ENDC}")
        
        if choice == "1":
            quick_stats()
        elif choice == "2":
            detailed_stats()
        elif choice == "3":
            user_verification_report()
        elif choice == "4":
            account_security_audit()
        elif choice == "5":
            export_data()
        elif choice == "0":
            print(f"{Colors.GREEN}Goodbye!{Colors.ENDC}")
            break
        else:
            print(f"{Colors.RED}Invalid option!{Colors.ENDC}")
        
        if choice in ["1", "2", "3", "4", "5"]:
            input(f"\n{Colors.YELLOW}Press Enter to continue...{Colors.ENDC}")

if __name__ == "__main__":
    # If run with argument, do quick stats and exit
    if len(sys.argv) > 1 and sys.argv[1] == "--quick":
        quick_stats()
    else:
        main() 