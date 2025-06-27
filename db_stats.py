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
    
    # 3. Top Users
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
    
    # 4. Popular Tokens
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
    
    # 5. Daily Trend
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
    
    tables = ["deployments", "users", "deposits", "daily_limits", "balance_sources", "fee_claims"]
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