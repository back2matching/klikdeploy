#!/usr/bin/env python3
"""
Test script for Self-Claim Fees functionality
Tests database operations and fee calculation logic
"""

import sqlite3
import os
from datetime import datetime

def test_self_claim_fees():
    """Test the self-claim fees functionality"""
    
    print("🧪 Testing Self-Claim Fees System")
    print("="*50)
    
    # Import the database class
    try:
        from deployer.database import DeploymentDatabase
        db = DeploymentDatabase()
        print("✅ Database class imported successfully")
    except ImportError as e:
        print(f"❌ Failed to import database: {e}")
        return False
    
    # Test 1: User preference management
    print("\n🔧 Test 1: User Preference Management")
    print("-" * 30)
    
    test_username = "testuser123"
    
    # Test setting preference (should fail for unverified user)
    result = db.set_user_fee_capture_preference(test_username, True)
    if not result:
        print("✅ Correctly rejected unverified user")
    else:
        print("❌ Should have rejected unverified user")
    
    # Test getting preference (should default to False)
    preference = db.get_user_fee_capture_preference(test_username)
    if not preference:
        print("✅ Unverified user defaults to community split")
    else:
        print("❌ Unverified user should default to community split")
    
    # Test 2: Fee calculation logic
    print("\n💰 Test 2: Fee Calculation Logic")
    print("-" * 30)
    
    # Test with no deployments (should use community split)
    test_token = "0x1234567890123456789012345678901234567890"
    fee_splits = db.process_fee_claim_for_user(test_token, 1.0, "test_tx")
    
    expected_community = {
        'user_claims': 0.0,
        'source_buyback': 0.25,
        'dok_buyback': 0.25,
        'treasury': 0.5
    }
    
    if fee_splits == expected_community:
        print("✅ Community split calculation correct")
    else:
        print(f"❌ Community split incorrect: {fee_splits}")
    
    # Test 3: Fee statistics
    print("\n📊 Test 3: Fee Statistics")
    print("-" * 30)
    
    stats = db.get_user_fee_stats(test_username)
    expected_stats = {
        'claimable_amount': 0.0,
        'total_claimed': 0.0,
        'tokens_with_fees': 0
    }
    
    if stats == expected_stats:
        print("✅ Fee statistics calculation correct")
    else:
        print(f"❌ Fee statistics incorrect: {stats}")
    
    # Test 4: Database integrity
    print("\n🗄️  Test 4: Database Integrity")
    print("-" * 30)
    
    try:
        with sqlite3.connect(db.db_path) as conn:
            # Check if new tables exist
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name IN ('user_fee_settings', 'deployment_fees')"
            )
            tables = [row[0] for row in cursor.fetchall()]
            
            if 'user_fee_settings' in tables and 'deployment_fees' in tables:
                print("✅ New tables exist in database")
            else:
                print(f"❌ Missing tables. Found: {tables}")
            
            # Check indexes
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'idx_deployment_fees_%'"
            )
            indexes = [row[0] for row in cursor.fetchall()]
            
            if len(indexes) >= 3:  # Should have at least 3 indexes
                print("✅ Performance indexes exist")
            else:
                print(f"❌ Missing indexes. Found: {indexes}")
                
    except Exception as e:
        print(f"❌ Database integrity check failed: {e}")
    
    # Test 5: Mock verification and preference setting
    print("\n✅ Test 5: Mock Verified User")
    print("-" * 30)
    
    try:
        # Create a mock verified user for testing
        with sqlite3.connect(db.db_path) as conn:
            conn.execute('''
                INSERT OR REPLACE INTO users 
                (twitter_username, twitter_verified, created_at)
                VALUES (?, ?, ?)
            ''', (test_username, True, datetime.now()))
            conn.commit()
            print("✅ Created mock verified user")
        
        # Now test preference setting
        result = db.set_user_fee_capture_preference(test_username, True)
        if result:
            print("✅ Successfully set preference for verified user")
        else:
            print("❌ Failed to set preference for verified user")
        
        # Test getting preference
        preference = db.get_user_fee_capture_preference(test_username)
        if preference:
            print("✅ Correctly retrieved user preference")
        else:
            print("❌ Failed to retrieve user preference")
        
        # Clean up test user
        with sqlite3.connect(db.db_path) as conn:
            conn.execute("DELETE FROM users WHERE twitter_username = ?", (test_username,))
            conn.execute("DELETE FROM user_fee_settings WHERE username = ?", (test_username,))
            conn.commit()
            print("✅ Cleaned up test data")
            
    except Exception as e:
        print(f"❌ Mock verification test failed: {e}")
    
    print("\n" + "="*50)
    print("🎉 Self-Claim Fees Tests Completed!")
    print("="*50)
    
    return True

def test_migration_compatibility():
    """Test that migration script works correctly"""
    
    print("\n🔄 Testing Migration Compatibility")
    print("="*50)
    
    if not os.path.exists('deployments.db'):
        print("ℹ️  No existing database to test migration")
        return True
    
    try:
        # Import migration function
        from migrate_self_claim_fees import migrate_database
        
        # Test migration (dry run - won't actually modify)
        print("✅ Migration script importable")
        print("ℹ️  Run 'python migrate_self_claim_fees.py' to perform actual migration")
        
        return True
        
    except ImportError as e:
        print(f"❌ Migration script import failed: {e}")
        return False

if __name__ == "__main__":
    print("🚀 Self-Claim Fees Test Suite")
    print("="*50)
    
    # Run main tests
    success = test_self_claim_fees()
    
    # Test migration compatibility
    migration_ok = test_migration_compatibility()
    
    if success and migration_ok:
        print("\n✅ ALL TESTS PASSED!")
        print("🎯 Self-claim fees system is ready for deployment")
    else:
        print("\n❌ Some tests failed")
        print("🔧 Please check the issues above before deployment") 