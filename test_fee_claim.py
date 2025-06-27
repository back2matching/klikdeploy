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
    
    # Simulate the claim first
    print(f"\n2️⃣ Simulating fee claim to check available fees...")
    
    simulation = await factory_interface.simulate_fee_claim(dok_token)
    
    if simulation['success']:
        if isinstance(simulation.get('claimable_eth'), (int, float)) and simulation['claimable_eth'] > 0:
            print(f"\n💰 Simulation Results (using Alchemy simulateAssetChanges):")
            print(f"   Claimable ETH: {simulation['claimable_eth']:.6f} ETH")
            
            if simulation.get('claimable_dok', 0) > 0:
                print(f"   Claimable DOK: {simulation['claimable_dok']:,.2f} DOK")
            
            # Calculate splits
            total_eth = simulation['claimable_eth']
            buyback_amount = total_eth * 0.25
            incentive_amount = total_eth * 0.25
            dev_amount = total_eth * 0.5
            
            print(f"\n📊 V1.02 Distribution:")
            print(f"   Buyback (25%): {buyback_amount:.6f} ETH")
            print(f"   Incentives (25%): {incentive_amount:.6f} ETH")
            print(f"   Developer (50%): {dev_amount:.6f} ETH")
            
            if 'gas_used' in simulation:
                print(f"\n⛽ Estimated gas: {simulation['gas_used']}")
                
                # Convert hex gas to readable format
                gas_amount = int(simulation['gas_used'], 16) if isinstance(simulation['gas_used'], str) and simulation['gas_used'].startswith('0x') else simulation['gas_used']
                gas_price_gwei = 30  # Estimate 30 gwei
                gas_cost_eth = (gas_amount * gas_price_gwei) / 1e9
                gas_cost_usd = gas_cost_eth * 2500  # Estimate $2500/ETH
                
                print(f"   Gas: {gas_amount:,} units @ {gas_price_gwei} gwei")
                print(f"   Cost: {gas_cost_eth:.6f} ETH (~${gas_cost_usd:.2f})")
        elif simulation.get('claimable_eth') == 0:
            print(f"\n❌ No fees available to claim")
            print(f"   Token ID: {simulation.get('token_id', 'Unknown')}")
        else:
            print(f"\n⚠️  {simulation.get('message', 'Cannot determine exact amount')}")
            if 'gas_estimate' in simulation:
                print(f"   Gas estimate: {simulation['gas_estimate']:,}")
                print(f"   This indicates fees exist but exact amount requires execution")
    else:
        print(f"\n❌ Simulation failed: {simulation.get('error', 'Unknown error')}")
    
    # Show what the claim transaction would look like
    print(f"\n3️⃣ Fee claim would execute:")
    print(f"   Contract: {factory_interface.factory.address}")
    print(f"   Function: collectFees({token_id})")
    print(f"   From: {factory_interface.account.address}")
    
    # Ask if user wants to execute
    response = input("\n⚠️  Execute actual fee claim? (yes/no): ").lower()
    
    if response == 'yes':
        print("\n4️⃣ Executing fee claim...")
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

async def simulate_custom_token():
    """Simulate fee claim for a custom token"""
    token_address = input("Enter token address to simulate: ").strip()
    
    if not token_address.startswith('0x') or len(token_address) != 42:
        print("❌ Invalid token address format")
        return
    
    print(f"\n🔍 Simulating fee claim for {token_address}...")
    
    simulation = await factory_interface.simulate_fee_claim(token_address)
    
    if simulation['success']:
        if isinstance(simulation.get('claimable_eth'), (int, float)) and simulation['claimable_eth'] > 0:
            print(f"\n💰 Simulation Results (using Alchemy simulateAssetChanges):")
            print(f"   Token ID: {simulation.get('token_id', 'Unknown')}")
            print(f"   Claimable ETH: {simulation['claimable_eth']:.6f} ETH")
            
            if simulation.get('claimable_dok', 0) > 0:
                print(f"   Claimable DOK: {simulation['claimable_dok']:,.2f} DOK")
            
            # Calculate splits
            total = simulation['claimable_eth']
            print(f"\n📊 V1.02 Distribution:")
            print(f"   Buyback (25%): {total * 0.25:.6f} ETH")
            print(f"   Incentives (25%): {total * 0.25:.6f} ETH")
            print(f"   Developer (50%): {total * 0.5:.6f} ETH")
            
            if 'gas_used' in simulation:
                print(f"\n⛽ Estimated gas: {simulation['gas_used']}")
                
                # Convert hex gas to readable format
                gas_amount = int(simulation['gas_used'], 16) if isinstance(simulation['gas_used'], str) and simulation['gas_used'].startswith('0x') else simulation['gas_used']
                gas_price_gwei = 30  # Estimate 30 gwei
                gas_cost_eth = (gas_amount * gas_price_gwei) / 1e9
                gas_cost_usd = gas_cost_eth * 2500  # Estimate $2500/ETH
                
                print(f"   Gas: {gas_amount:,} units @ {gas_price_gwei} gwei")
                print(f"   Cost: {gas_cost_eth:.6f} ETH (~${gas_cost_usd:.2f})")
        elif simulation.get('claimable_eth') == 0:
            print(f"\n❌ No fees available to claim")
        else:
            print(f"\n⚠️  {simulation.get('message', 'Cannot determine exact amount')}")
            if 'gas_estimate' in simulation:
                print(f"   Fees may exist but exact amount requires execution")
    else:
        print(f"\n❌ {simulation.get('error', 'Simulation failed')}")

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

async def test_small_buyback():
    """Test a small manual buyback of DOK"""
    print("\n🧪 Testing Small DOK Buyback")
    print("="*50)
    
    amount_eth = 0.01
    print(f"\nTesting buyback of {amount_eth} ETH worth of DOK...")
    
    # Get current DOK price
    dok_price = await factory_interface.get_dok_price_v3()
    expected_dok = amount_eth / dok_price
    
    print(f"\nCurrent DOK price: {dok_price:.8f} ETH")
    print(f"Expected DOK from buyback: {expected_dok:,.2f} DOK")
    print(f"Will be sent to burn address: 0x000000000000000000000000000000000000dEaD")
    
    response = input("\n⚠️  Execute buyback? (yes/no): ").lower()
    
    if response == 'yes':
        print("\n🔄 Executing buyback...")
        result = await factory_interface.execute_dok_buyback_v3(amount_eth, "manual_test")
        
        if result['success']:
            print(f"✅ Buyback successful!")
            print(f"   TX: {result['tx_hash']}")
            print(f"   DOK burned: {result.get('dok_amount', expected_dok):,.2f}")
            print(f"   View: https://etherscan.io/tx/{result['tx_hash']}")
        else:
            print(f"❌ Buyback failed: {result.get('error', 'Unknown error')}")
    else:
        print("\n⏭️  Skipping buyback")

if __name__ == "__main__":
    print("Choose an option:")
    print("1. Test fee claim for DOK")
    print("2. Simulate fee claim for custom token")
    print("3. Check all recent pools")
    print("4. Test small DOK buyback (0.01 ETH)")
    
    choice = input("\nEnter choice (1-4): ")
    
    if choice == "1":
        asyncio.run(test_fee_claim())
    elif choice == "2":
        asyncio.run(simulate_custom_token())
    elif choice == "3":
        asyncio.run(check_all_pools())
    elif choice == "4":
        asyncio.run(test_small_buyback())
    else:
        print("Invalid choice!") 