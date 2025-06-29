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
        print("3. Export to CSV")
        print("0. Exit")
        
        choice = input(f"\n{Colors.CYAN}Select option: {Colors.ENDC}")
        
        if choice == "1":
            quick_stats()
        elif choice == "2":
            detailed_stats()
        elif choice == "3":
            export_data()
        elif choice == "0":
            print(f"{Colors.GREEN}Goodbye!{Colors.ENDC}")
            break
        else:
            print(f"{Colors.RED}Invalid option!{Colors.ENDC}")
        
        if choice in ["1", "2", "3"]:
            input(f"\n{Colors.YELLOW}Press Enter to continue...{Colors.ENDC}")

if __name__ == "__main__":
    # If run with argument, do quick stats and exit
    if len(sys.argv) > 1 and sys.argv[1] == "--quick":
        quick_stats()
    else:
        main() 