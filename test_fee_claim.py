#!/usr/bin/env python3
"""
Test script for fee claiming system
"""

import asyncio
import os
from dotenv import load_dotenv
from klik_factory_interface import factory_interface

# Load env
load_dotenv()

async def test_fee_claim():
    """Test fee claiming for DOK token"""
    print("🧪 Testing Fee Claim System")
    print("="*50)
    
    # DOK token address
    dok_token = "0x69ca61398eCa94D880393522C1Ef5c3D8c058837"
    
    print(f"\n1️⃣ Finding tokenId for DOK token...")
    
    # Test finding the tokenId
    token_id = await factory_interface.get_token_id_for_token(dok_token)
    
    if token_id is None:
        print("❌ Could not find tokenId for DOK token")
        print("This might mean:")
        print("- The token doesn't have a pool in Klik Factory")
        print("- The pool search needs optimization")
        return
    
    print(f"✅ Found tokenId: {token_id}")
    
    # Show what the claim transaction would look like
    print(f"\n2️⃣ Fee claim would execute:")
    print(f"   Contract: {factory_interface.factory.address}")
    print(f"   Function: collectFees({token_id})")
    print(f"   From: {factory_interface.account.address}")
    
    # Ask if user wants to execute
    response = input("\n⚠️  Execute actual fee claim? (yes/no): ").lower()
    
    if response == 'yes':
        print("\n3️⃣ Executing fee claim...")
        try:
            tx_hash = await factory_interface.claim_fees_for_token(dok_token)
            if tx_hash:
                print(f"✅ Fee claim successful!")
                print(f"   TX: {tx_hash}")
                print(f"   View: https://etherscan.io/tx/{tx_hash}")
            else:
                print("❌ Fee claim failed!")
        except Exception as e:
            print(f"❌ Error: {e}")
    else:
        print("\n⏭️  Skipping actual execution")

async def test_dok_price():
    """Test DOK price fetching"""
    print("\n🧪 Testing DOK Price Fetch")
    print("="*50)
    
    price = await factory_interface.get_dok_price_v3()
    print(f"DOK Price: {price:.8f} ETH")
    print(f"1 ETH = {1/price:,.0f} DOK")

async def check_all_pools():
    """Check all recent pools"""
    print("\n📊 Checking recent pools...")
    
    try:
        factory = factory_interface.factory
        pairs_length = factory.functions.allPairsLength().call()
        print(f"Total pools: {pairs_length}")
        
        # Check last 10 pools
        start = max(0, pairs_length - 10)
        for i in range(start, pairs_length):
            pair_address = factory.functions.allPairs(i).call()
            print(f"\nPool #{i}: {pair_address}")
            
            # Get tokens in pool
            try:
                pair_contract = factory_interface.w3.eth.contract(
                    address=pair_address, 
                    abi=[
                        {"constant": True, "inputs": [], "name": "token0", "outputs": [{"name": "", "type": "address"}], "type": "function"},
                        {"constant": True, "inputs": [], "name": "token1", "outputs": [{"name": "", "type": "address"}], "type": "function"}
                    ]
                )
                token0 = pair_contract.functions.token0().call()
                token1 = pair_contract.functions.token1().call()
                print(f"  Token0: {token0}")
                print(f"  Token1: {token1}")
            except:
                print("  Could not read tokens")
                
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    print("Choose an option:")
    print("1. Test fee claim for DOK")
    print("2. Check all recent pools")
    
    choice = input("\nEnter choice (1 or 2): ")
    
    if choice == "1":
        asyncio.run(test_fee_claim())
    elif choice == "2":
        asyncio.run(check_all_pools())
    else:
        print("Invalid choice!") 