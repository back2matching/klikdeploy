#!/usr/bin/env python3
"""
Migration script for Self-Claim Fees feature
Adds new tables and columns needed for user fee capture functionality
"""

import sqlite3
import os
from datetime import datetime

def migrate_database(db_path='deployments.db'):
    """Migrate database to support self-claim fees"""
    
    print(f"🔄 Migrating database: {db_path}")
    
    if not os.path.exists(db_path):
        print(f"❌ Database not found: {db_path}")
        return False
    
    # Backup the database first
    backup_path = f"{db_path}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    import shutil
    shutil.copy2(db_path, backup_path)
    print(f"📦 Created backup: {backup_path}")
    
    try:
        with sqlite3.connect(db_path) as conn:
            print("📊 Adding new tables for self-claim fees...")
            
            # User fee capture settings table
            conn.execute('''
                CREATE TABLE IF NOT EXISTS user_fee_settings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE,
                    fee_capture_enabled BOOLEAN DEFAULT FALSE,
                    last_modified TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (username) REFERENCES users(twitter_username)
                )
            ''')
            print("✅ Added user_fee_settings table")
            
            # Individual deployment fee tracking
            conn.execute('''
                CREATE TABLE IF NOT EXISTS deployment_fees (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    deployment_id INTEGER,
                    token_address TEXT,
                    token_symbol TEXT,
                    username TEXT,
                    total_fees_generated REAL DEFAULT 0,
                    user_claimable_amount REAL DEFAULT 0,
                    claimed_amount REAL DEFAULT 0,
                    claim_tx_hash TEXT,
                    claimed_at TIMESTAMP,
                    status TEXT DEFAULT 'pending', -- 'pending', 'claimable', 'claimed'
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (deployment_id) REFERENCES deployments(id),
                    FOREIGN KEY (username) REFERENCES users(twitter_username)
                )
            ''')
            print("✅ Added deployment_fees table")
            
            # Create indexes for better performance
            conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_deployment_fees_username 
                ON deployment_fees(username)
            ''')
            
            conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_deployment_fees_token 
                ON deployment_fees(token_address)
            ''')
            
            conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_deployment_fees_status 
                ON deployment_fees(status)
            ''')
            
            print("✅ Added performance indexes")
            
            # Populate deployment_fees for existing deployments
            print("📊 Backfilling deployment fee tracking for existing deployments...")
            
            cursor = conn.execute('''
                SELECT id, username, token_address, token_symbol 
                FROM deployments 
                WHERE status = 'success' AND token_address IS NOT NULL
            ''')
            
            existing_deployments = cursor.fetchall()
            backfilled_count = 0
            
            for deployment_id, username, token_address, token_symbol in existing_deployments:
                # Check if already exists
                cursor = conn.execute(
                    "SELECT id FROM deployment_fees WHERE deployment_id = ?",
                    (deployment_id,)
                )
                
                if not cursor.fetchone():
                    # Add fee tracking record
                    conn.execute('''
                        INSERT INTO deployment_fees 
                        (deployment_id, token_address, token_symbol, username, status)
                        VALUES (?, ?, ?, ?, 'pending')
                    ''', (deployment_id, token_address, token_symbol, username.lower()))
                    backfilled_count += 1
            
            print(f"✅ Backfilled {backfilled_count} deployment fee records")
            
            conn.commit()
            
        print(f"\n🎉 Migration completed successfully!")
        print(f"📊 Summary:")
        print(f"   • Added user_fee_settings table")
        print(f"   • Added deployment_fees table") 
        print(f"   • Added performance indexes")
        print(f"   • Backfilled {backfilled_count} existing deployments")
        print(f"   • Backup saved as: {backup_path}")
        print(f"\n✅ Self-claim fees feature is now ready!")
        
        return True
        
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        
        # Restore backup on failure
        print("🔄 Restoring backup...")
        shutil.copy2(backup_path, db_path)
        print(f"✅ Database restored from backup")
        
        return False

if __name__ == "__main__":
    print("🚀 Self-Claim Fees Migration Script")
    print("="*50)
    
    # Check if database exists
    if os.path.exists('deployments.db'):
        migrate_database('deployments.db')
    else:
        print("❌ No deployments.db found in current directory")
        print("   Please run this script from the same directory as your database") 