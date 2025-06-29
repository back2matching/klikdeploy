#!/usr/bin/env python3
"""
Test script for a single deployment with 0x69 vanity address
"""

import asyncio
import sys
import os
sys.path.append('.')

from klik_token_deployer import KlikTokenDeployer
from deployer.models import DeploymentRequest
from datetime import datetime

async def test_single_deployment():
    """Test a single deployment with vanity address"""
    
    print("🧪 Testing Single 0x69 Vanity Deployment")
    print("=" * 60)
    
    # Initialize deployer
    deployer = KlikTokenDeployer()
    
    # Check balance
    balance = deployer.get_eth_balance()
    print(f"💰 Current Balance: {balance:.4f} ETH")
    
    if balance < 0.05:
        print("❌ Insufficient balance for testing! Need at least 0.05 ETH")
        return False
    
    # Create test deployment request
    request = DeploymentRequest(
        tweet_id='test_vanity_123',
        username='testuser_vanity',
        token_name='VanityTest',
        token_symbol='VANITY',
        requested_at=datetime.now(),
        tweet_url='https://x.com/testuser_vanity/status/test_vanity_123',
        parent_tweet_id=None,
        image_url=None,
        follower_count=5000
    )
    
    print(f"🎯 Test Token: {request.token_name} ({request.token_symbol})")
    print(f"👤 Test User: @{request.username}")
    
    # Generate vanity salt first to show predicted address
    try:
        print(f"\n🔮 Generating 0x69 vanity address...")
        salt, predicted_address = await deployer.generate_salt_and_address(
            request.token_name, 
            request.token_symbol
        )
        
        print(f"✅ Vanity address generated!")
        print(f"   🎯 Predicted: {predicted_address}")
        print(f"   🧂 Salt: {salt}")
        print(f"   ✨ Starts with: 0x{predicted_address[2:4]}")
        
        # Validate it's actually 0x69
        if not predicted_address[2:4].lower() == "69":
            print(f"❌ ERROR: Address doesn't start with 0x69!")
            return False
            
        # Store in request
        request.salt = salt
        request.predicted_address = predicted_address
        
    except Exception as e:
        print(f"❌ Failed to generate vanity address: {e}")
        return False
    
    # Show deployment preview
    print(f"\n📋 DEPLOYMENT PREVIEW")
    print(f"=" * 60)
    print(f"Token: {request.token_name} ({request.token_symbol})")
    print(f"Predicted Address: {predicted_address}")
    print(f"DexScreener: https://dexscreener.com/ethereum/{predicted_address}")
    print(f"=" * 60)
    
    # Ask for confirmation
    confirm = input(f"\n⚠️  Deploy REAL token with 0x69 address? (y/N): ")
    if confirm.lower() != 'y':
        print("❌ Deployment cancelled")
        return False
    
    # Perform the deployment
    print(f"\n🚀 Starting deployment...")
    
    try:
        success = await deployer.deploy_token(request)
        
        if success:
            print(f"\n🎉 DEPLOYMENT SUCCESS!")
            print(f"   Token Address: {request.token_address}")
            print(f"   Transaction: https://etherscan.io/tx/{request.tx_hash}")
            print(f"   DexScreener: https://dexscreener.com/ethereum/{request.token_address}")
            
            # Verify the address matches prediction
            if request.token_address and request.predicted_address:
                if request.token_address.lower() == request.predicted_address.lower():
                    print(f"   ✅ ADDRESS PREDICTION VERIFIED!")
                else:
                    print(f"   ⚠️  Address mismatch:")
                    print(f"      Predicted: {request.predicted_address}")
                    print(f"      Actual: {request.token_address}")
            
            # Check if it actually starts with 0x69
            if request.token_address and request.token_address[2:4].lower() == "69":
                print(f"   🎯 CONFIRMED: Address starts with 0x69!")
                return True
            else:
                print(f"   ❌ ERROR: Address doesn't start with 0x69")
                return False
        else:
            print(f"\n❌ DEPLOYMENT FAILED!")
            print(f"   Status: {request.status}")
            return False
            
    except Exception as e:
        print(f"\n❌ DEPLOYMENT ERROR: {e}")
        return False

async def main():
    print("🎯 Klik Finance 0x69 Vanity Address Test")
    print("This will deploy a REAL token on Ethereum mainnet!")
    print("")
    
    success = await test_single_deployment()
    
    if success:
        print(f"\n🎉 SUCCESS! 0x69 vanity deployment works perfectly!")
        print(f"✅ Ready to implement in production!")
    else:
        print(f"\n❌ Test failed. Need to investigate issues.")

if __name__ == "__main__":
    asyncio.run(main()) 