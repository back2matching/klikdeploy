#!/usr/bin/env python3
"""
Test script for fee detection and buyback system
"""

import asyncio
import os
from dotenv import load_dotenv
from klik_factory_interface import factory_interface
from web3 import Web3
import requests
import sqlite3
from datetime import datetime, timedelta

# Load env
load_dotenv()

# Initialize Web3
RPC_URL = os.getenv('ALCHEMY_RPC_URL')
DEPLOYER_ADDRESS = os.getenv('DEPLOYER_ADDRESS')
w3 = Web3(Web3.HTTPProvider(RPC_URL))

# Klik Factory contract address
KLIK_FACTORY = "0x930f9FA91E1E46d8e44abC3517E2965C6F9c4763"

async def detect_incoming_fee_claims():
    """Detect incoming fee claims from Klik Factory to our deployer wallet"""
    print("\n🔍 Detecting Incoming Fee Claims")
    print("="*50)
    
    # Get recent internal transactions to our deployer
    print(f"Checking internal transactions to: {DEPLOYER_ADDRESS}")
    print(f"Looking for transfers from: {KLIK_FACTORY}\n")
    
    try:
        # Use Alchemy to get internal transactions
        response = requests.post(RPC_URL, json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "alchemy_getAssetTransfers",
            "params": [{
                "fromBlock": "0x0",  # You can adjust this to recent blocks
                "toBlock": "latest",
                "toAddress": DEPLOYER_ADDRESS,
                "fromAddress": KLIK_FACTORY,
                "category": ["internal"],  # Internal ETH transfers
                "excludeZeroValue": True,
                "maxCount": "0x64"  # Last 100
            }]
        })
        
        if response.status_code == 200:
            data = response.json()
            transfers = data.get('result', {}).get('transfers', [])
            
            print(f"Found {len(transfers)} internal transfers from Klik Factory\n")
            
            # Check database for already processed claims
            conn = sqlite3.connect('deployments.db')
            
            # Process last 3 transfers with full decoding
            for i, transfer in enumerate(transfers[-3:]):
                tx_hash = transfer['hash']
                value = float(transfer['value'])
                block_num = int(transfer['blockNum'], 16) if isinstance(transfer['blockNum'], str) else transfer['blockNum']
                
                # Check if already processed
                cursor = conn.execute(
                    "SELECT id FROM fee_claims WHERE claim_tx_hash = ?",
                    (tx_hash,)
                )
                is_processed = cursor.fetchone() is not None
                
                print(f"Transfer #{i+1}:")
                print(f"TX: {tx_hash}")
                print(f"   Amount: {value:.6f} ETH")
                print(f"   Block: {block_num}")
                print(f"   Status: {'✅ Already processed' if is_processed else '🆕 New claim!'}")
                
                # Decode the transaction to get token details
                print(f"   Decoding collectFee transaction...")
                decoded = await factory_interface.decode_collect_fee_transaction(tx_hash)
                
                if decoded and 'deployed_token' in decoded:
                    token_addr = decoded['deployed_token']
                    token_info = decoded.get('token_info', {})
                    
                    if token_info:
                        print(f"   Token: ${token_info['symbol']} - {token_info['name']}")
                    print(f"   Token Address: {token_addr}")
                    print(f"   Token ID: {decoded['token_id']}")
                    print(f"   Pool: {decoded.get('pool_address', 'Unknown')}")
                    
                    if not is_processed:
                        # Calculate splits
                        source_buyback = value * 0.25
                        dok_buyback = value * 0.25
                        treasury = value * 0.5
                        
                        print(f"\n   💡 Buyback Plan:")
                        print(f"   - {source_buyback:.6f} ETH → Buy ${token_info.get('symbol', 'TOKEN')} (pump & hold)")
                        print(f"   - {dok_buyback:.6f} ETH → Buy $DOK (pump & hold)")
                        print(f"   - {treasury:.6f} ETH → Treasury (keep as ETH)")
                else:
                    print(f"   ❌ Could not decode transaction")
                
                print()
            
            # Summary (calculate before closing connection)
            unprocessed_count = 0
            unprocessed_value = 0.0
            
            for t in transfers:
                cursor = conn.execute(
                    "SELECT id FROM fee_claims WHERE claim_tx_hash = ?", 
                    (t['hash'],)
                )
                if not cursor.fetchone():
                    unprocessed_count += 1
                    unprocessed_value += float(t['value'])
            
            conn.close()
            
            print(f"\n📊 Summary:")
            print(f"   Total fee claims: {len(transfers)}")
            print(f"   Unprocessed claims: {unprocessed_count}")
            
            if unprocessed_count > 0:
                print(f"   Total unprocessed value: {unprocessed_value:.6f} ETH")
                print(f"   Potential DOK buyback: {unprocessed_value * 0.25:.6f} ETH")
                print(f"   Potential source token buybacks: {unprocessed_value * 0.25:.6f} ETH")
                print(f"   Treasury earnings: {unprocessed_value * 0.5:.6f} ETH")
                
        else:
            print(f"❌ Error fetching transfers: {response.status_code}")
            
    except Exception as e:
        print(f"❌ Error: {e}")

async def test_buyback_split():
    """Test the buyback split logic with a mock fee claim"""
    print("\n💰 Testing Buyback Split Logic")
    print("="*50)
    
    # Mock values for testing
    total_received = 0.1  # 0.1 ETH received from fee claim
    source_token = "0x692Ea3f6E92000a966874715A6cC53c6E74E269F"  # Example token (MOON)
    
    print(f"Mock Fee Claim:")
    print(f"   Total Received: {total_received} ETH")
    print(f"   Source Token: {source_token}")
    print(f"   DOK Token: 0x69ca61398eCa94D880393522C1Ef5c3D8c058837\n")
    
    # Calculate splits
    source_buyback = total_received * 0.25
    dok_buyback = total_received * 0.25
    treasury = total_received * 0.5
    
    print(f"Split Calculation:")
    print(f"   Source Token Buyback (25%): {source_buyback:.6f} ETH")
    print(f"   DOK Buyback (25%): {dok_buyback:.6f} ETH")
    print(f"   Treasury (50%): {treasury:.6f} ETH")
    print(f"   Total: {source_buyback + dok_buyback + treasury:.6f} ETH\n")
    
    # Show what would happen
    print(f"Execution Plan:")
    print(f"1. Buy {source_buyback:.6f} ETH of source token (pump & hold)")
    print(f"2. Buy {dok_buyback:.6f} ETH of DOK (pump & hold)")
    print(f"3. Keep {treasury:.6f} ETH in treasury\n")
    
    response = input("Test actual buyback execution? (yes/no): ").lower()
    
    if response == 'yes':
        # Test DOK buyback only (smaller amount)
        test_amount = 0.001  # Small test amount
        print(f"\n🧪 Testing with {test_amount} ETH for DOK buyback...")
        
        result = await factory_interface.execute_dok_buyback_v3(test_amount, "test_split")
        
        if result['success']:
            print(f"✅ Test buyback successful!")
            print(f"   TX: {result['tx_hash']}")
            print(f"   DOK burned: {result.get('dok_amount', 0):,.2f}")
        else:
            print(f"❌ Test buyback failed: {result.get('error', 'Unknown error')}")

async def test_small_dok_buyback():
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
    print(f"Will be held in deployer wallet")
    
    response = input("\n⚠️  Execute buyback? (yes/no): ").lower()
    
    if response == 'yes':
        print("\n🔄 Executing buyback...")
        result = await factory_interface.execute_dok_buyback_v3(amount_eth, "manual_test")
        
        if result['success']:
            print(f"✅ Buyback successful!")
            print(f"   TX: {result['tx_hash']}")
            print(f"   DOK bought: {result.get('dok_amount', expected_dok):,.2f} (now holding)")
            print(f"   View: https://etherscan.io/tx/{result['tx_hash']}")
        else:
            print(f"❌ Buyback failed: {result.get('error', 'Unknown error')}")
    else:
        print("\n⏭️  Skipping buyback")

async def process_single_fee_claim():
    """Process a single fee claim through the entire pipeline"""
    print("\n🚀 Processing Single Fee Claim Pipeline")
    print("="*50)
    
    # Step 1: Find an unprocessed fee claim
    print("Step 1: Finding unprocessed fee claims...")
    
    try:
        # Get recent internal transactions
        response = requests.post(RPC_URL, json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "alchemy_getAssetTransfers",
            "params": [{
                "fromBlock": "0x0",
                "toBlock": "latest",
                "toAddress": DEPLOYER_ADDRESS,
                "fromAddress": KLIK_FACTORY,
                "category": ["internal"],
                "excludeZeroValue": True,
                "maxCount": "0x64"
            }]
        })
        
        if response.status_code != 200:
            print(f"❌ Error fetching transfers: {response.status_code}")
            return
            
        data = response.json()
        transfers = data.get('result', {}).get('transfers', [])
        
        if not transfers:
            print("❌ No fee claims found")
            return
        
        # Find first unprocessed transfer
        conn = sqlite3.connect('deployments.db')
        unprocessed_transfer = None
        
        for transfer in reversed(transfers):  # Start from newest
            tx_hash = transfer['hash']
            cursor = conn.execute(
                "SELECT id FROM fee_claims WHERE claim_tx_hash = ?",
                (tx_hash,)
            )
            if not cursor.fetchone():
                unprocessed_transfer = transfer
                break
        
        if not unprocessed_transfer:
            print("❌ No unprocessed fee claims found")
            print(f"   Total transfers: {len(transfers)}")
            print("   All have been processed already")
            conn.close()
            return
        
        # Step 2: Decode the transaction
        tx_hash = unprocessed_transfer['hash']
        value = float(unprocessed_transfer['value'])
        
        print(f"\n✅ Found unprocessed claim: {tx_hash}")
        print(f"   Amount: {value:.6f} ETH")
        
        print("\nStep 2: Decoding transaction to get token details...")
        decoded = await factory_interface.decode_collect_fee_transaction(tx_hash)
        
        if decoded is None:
            print(f"❌ Transaction decode returned None")
            print(f"   TX: {tx_hash}")
            print(f"   This might not be a collectFees transaction")
            conn.close()
            return
        
        if 'deployed_token' not in decoded:
            print(f"❌ No deployed_token in decoded data")
            print(f"   Decoded data: {decoded}")
            conn.close()
            return
        
        token_address = decoded['deployed_token']
        if not token_address:
            print(f"❌ Empty token address")
            conn.close()
            return
        
        token_info = decoded.get('token_info', {})
        token_symbol = token_info.get('symbol', 'UNKNOWN') if token_info else 'UNKNOWN'
        token_name = token_info.get('name', 'Unknown Token') if token_info else 'Unknown Token'
        
        print(f"✅ Decoded successfully!")
        print(f"   Token: ${token_symbol} - {token_name}")
        print(f"   Address: {token_address}")
        print(f"   Token ID: {decoded['token_id']}")
        
        # Step 3: Calculate splits
        print("\nStep 3: Calculating buyback splits...")
        source_buyback = value * 0.25
        dok_buyback = value * 0.25
        treasury = value * 0.5
        
        print(f"   Source token buyback: {source_buyback:.6f} ETH")
        print(f"   DOK buyback: {dok_buyback:.6f} ETH")
        print(f"   Treasury: {treasury:.6f} ETH")
        
        # Ask for confirmation
        print("\n" + "="*50)
        print("READY TO EXECUTE BUYBACKS:")
        print(f"1. Buy {source_buyback:.6f} ETH of ${token_symbol} → Hold (pump chart)")
        print(f"2. Buy {dok_buyback:.6f} ETH of $DOK → Hold (pump chart)")
        print(f"3. Keep {treasury:.6f} ETH in treasury")
        print("="*50)
        
        response = input("\n⚠️  Execute buybacks? (yes/no): ").lower()
        
        if response != 'yes':
            print("\n⏭️  Skipping execution")
            conn.close()
            return
        
        # Step 4: Execute buybacks
        print("\nStep 4: Executing buybacks...")
        
        # Record the fee claim as processing
        conn.execute('''
            INSERT INTO fee_claims 
            (token_address, token_symbol, token_name, pool_address, 
             claimed_amount, buyback_amount, incentive_amount, dev_amount,
             claim_tx_hash, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'processing')
        ''', (token_address, token_symbol, token_name, decoded.get('pool_address'),
              value, source_buyback, dok_buyback, treasury,
              tx_hash))
        conn.commit()
        
        # Execute source token buyback
        print(f"\n🔄 Buying ${token_symbol}...")
        source_result = await factory_interface.execute_token_buyback(
            token_address, 
            source_buyback
            # Will automatically hold in our wallet
        )
        
        if source_result['success']:
            print(f"✅ ${token_symbol} buyback successful!")
            print(f"   TX: {source_result['tx_hash']}")
        else:
            print(f"❌ ${token_symbol} buyback failed: {source_result.get('error', 'Unknown error')}")
        
        # Execute DOK buyback
        print(f"\n🔄 Buying $DOK...")
        dok_result = await factory_interface.execute_dok_buyback_v3(dok_buyback, tx_hash)
        
        if dok_result['success']:
            print(f"✅ $DOK buyback successful!")
            print(f"   TX: {dok_result['tx_hash']}")
            if dok_result.get('dok_amount', 0) > 0:
                print(f"   DOK bought: {dok_result.get('dok_amount', 0):,.2f} (now holding)")
        else:
            print(f"❌ $DOK buyback failed: {dok_result.get('error', 'Unknown error')}")
        
        # Update database with results
        if source_result['success'] and dok_result['success']:
            status = 'completed'
        elif source_result['success'] or dok_result['success']:
            status = 'partial'
        else:
            status = 'failed'
        
        # Update the fee claim record
        conn.execute('''
            UPDATE fee_claims 
            SET status = ?,
                buyback_tx_hash = ?,
                buyback_dok_amount = ?
            WHERE claim_tx_hash = ?
        ''', (status, 
              source_result.get('tx_hash', ''),
              dok_result.get('dok_amount', 0),
              tx_hash))
        
        # Record treasury amount in balance_sources
        conn.execute('''
            INSERT INTO balance_sources (source_type, amount, tx_hash, description)
            VALUES ('fee_detection', ?, ?, ?)
        ''', (treasury, tx_hash, f"Treasury from ${token_symbol} fees"))
        
        conn.commit()
        conn.close()
        
        # Final summary
        print("\n" + "="*50)
        print("PIPELINE COMPLETE!")
        print("="*50)
        print(f"Status: {status.upper()}")
        print(f"Source token buyback: {'✅' if source_result['success'] else '❌'}")
        print(f"DOK buyback: {'✅' if dok_result['success'] else '❌'}")
        print(f"Treasury secured: {treasury:.6f} ETH")
        
        if source_result['success']:
            print(f"\n${token_symbol} buyback: https://etherscan.io/tx/{source_result['tx_hash']}")
        if dok_result['success']:
            print(f"$DOK buyback: https://etherscan.io/tx/{dok_result['tx_hash']}")
            
    except Exception as e:
        print(f"\n❌ Pipeline error: {e}")
        import traceback
        traceback.print_exc()

async def process_all_fee_claims_automated():
    """Automatically process all unprocessed fee claims without manual confirmation"""
    print("\n🤖 AUTOMATED FEE CLAIM PROCESSING")
    print("="*50)
    
    processed_count = 0
    success_count = 0
    failed_count = 0
    total_treasury = 0.0
    total_source_buyback = 0.0
    total_dok_buyback = 0.0
    
    start_time = datetime.now()
    
    try:
        # Get all unprocessed claims first
        print("Fetching all unprocessed fee claims...")
        response = requests.post(RPC_URL, json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "alchemy_getAssetTransfers",
            "params": [{
                "fromBlock": "0x0",
                "toBlock": "latest",
                "toAddress": DEPLOYER_ADDRESS,
                "fromAddress": KLIK_FACTORY,
                "category": ["internal"],
                "excludeZeroValue": True,
                "maxCount": "0x64"
            }]
        })
        
        if response.status_code != 200:
            print(f"❌ Error fetching transfers: {response.status_code}")
            return
            
        data = response.json()
        transfers = data.get('result', {}).get('transfers', [])
        
        if not transfers:
            print("❌ No fee claims found")
            return
        
        # Filter unprocessed claims
        conn = sqlite3.connect('deployments.db')
        unprocessed_claims = []
        
        for transfer in reversed(transfers):
            tx_hash = transfer['hash']
            cursor = conn.execute(
                "SELECT id FROM fee_claims WHERE claim_tx_hash = ?",
                (tx_hash,)
            )
            if not cursor.fetchone():
                unprocessed_claims.append(transfer)
        
        if not unprocessed_claims:
            print("✅ All fee claims have been processed!")
            conn.close()
            return
        
        print(f"\n📊 Found {len(unprocessed_claims)} unprocessed claims")
        print(f"💰 Total value: {sum(float(t['value']) for t in unprocessed_claims):.6f} ETH")
        print("\n🚀 Starting automated processing...\n")
        
        # Process each claim
        for i, claim in enumerate(unprocessed_claims):
            tx_hash = claim['hash']
            value = float(claim['value'])
            
            print(f"[{i+1}/{len(unprocessed_claims)}] Processing {tx_hash[:10]}...")
            print(f"     Amount: {value:.6f} ETH")
            
            # Decode transaction
            try:
                decoded = await factory_interface.decode_collect_fee_transaction(tx_hash)
                
                if decoded is None:
                    print(f"     ❌ Transaction decode returned None")
                    print(f"     TX: {tx_hash}")
                    print(f"     This might not be a collectFees transaction")
                    failed_count += 1
                    processed_count += 1
                    continue
                
                if 'deployed_token' not in decoded:
                    print(f"     ❌ No deployed_token in decoded data")
                    print(f"     Decoded data: {decoded}")
                    failed_count += 1
                    processed_count += 1
                    continue
                
                token_address = decoded['deployed_token']
                if not token_address:
                    print(f"     ❌ Empty token address")
                    failed_count += 1
                    processed_count += 1
                    continue
                
                token_info = decoded.get('token_info', {})
                token_symbol = token_info.get('symbol', 'UNKNOWN') if token_info else 'UNKNOWN'
                token_name = token_info.get('name', 'Unknown Token') if token_info else 'Unknown Token'
                
                print(f"     Token: ${token_symbol}")
                
                # Calculate splits
                source_buyback = value * 0.25
                dok_buyback = value * 0.25
                treasury = value * 0.5
                
                # Track whether both buybacks succeed
                source_success = False
                dok_success = False
                
                # Execute source token buyback
                print(f"     Buying ${token_symbol}...")
                source_result = await factory_interface.execute_token_buyback(
                    token_address, 
                    source_buyback,
                    silent=True  # Silent mode for cleaner automated output
                )
                
                if source_result['success']:
                    print(f"     ✅ ${token_symbol} buyback: {source_result['tx_hash'][:10]}...")
                    source_success = True
                    total_source_buyback += source_buyback
                else:
                    print(f"     ❌ ${token_symbol} buyback failed: {source_result.get('error', 'Unknown error')}")
                
                # Execute DOK buyback
                print(f"     Buying $DOK...")
                dok_result = await factory_interface.execute_dok_buyback_v3(
                    dok_buyback, 
                    tx_hash,
                    silent=True  # Silent mode for cleaner automated output
                )
                
                if dok_result['success']:
                    print(f"     ✅ $DOK buyback: {dok_result['tx_hash'][:10]}...")
                    dok_success = True
                    total_dok_buyback += dok_buyback
                    if 'dok_amount' in dok_result:
                        print(f"     DOK amount: {dok_result['dok_amount']:,.2f}")
                else:
                    print(f"     ❌ $DOK buyback failed: {dok_result.get('error', 'Unknown error')}")
                
                # Only record in database if at least one buyback succeeded
                if source_success or dok_success:
                    # Determine status
                    if source_success and dok_success:
                        status = 'completed'
                        success_count += 1
                    else:
                        status = 'partial'
                        success_count += 1  # Still count as success if partial
                    
                    # Record in database
                    conn.execute('''
                        INSERT INTO fee_claims 
                        (token_address, token_symbol, token_name, pool_address, 
                         claimed_amount, buyback_amount, incentive_amount, dev_amount,
                         claim_tx_hash, buyback_tx_hash, buyback_dok_amount, status)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (token_address, token_symbol, token_name, decoded.get('pool_address'),
                          value, source_buyback, dok_buyback, treasury,
                          tx_hash, 
                          source_result.get('tx_hash', ''),
                          dok_result.get('dok_amount', None),  # Store NULL if we don't have the real amount
                          status))
                    
                    # Record treasury amount
                    conn.execute('''
                        INSERT INTO balance_sources (source_type, amount, tx_hash, description)
                        VALUES ('fee_detection', ?, ?, ?)
                    ''', (treasury, tx_hash, f"Treasury from ${token_symbol} fees"))
                    
                    conn.commit()
                    total_treasury += treasury
                    
                    print(f"     ✅ Recorded as {status}")
                else:
                    print(f"     ❌ Both buybacks failed - not recording")
                    failed_count += 1
                
                processed_count += 1
                print()  # Empty line between claims
                
                # Small delay to avoid rate limits
                await asyncio.sleep(1)
                
            except Exception as e:
                print(f"     ❌ Error processing claim: {e}")
                print(f"     Error type: {type(e).__name__}")
                import traceback
                print(f"     Traceback: {traceback.format_exc()}")
                failed_count += 1
                processed_count += 1
                continue
        
        conn.close()
        
        # Final summary
        duration = (datetime.now() - start_time).total_seconds()
        
        print("\n" + "="*50)
        print("🎉 AUTOMATED PROCESSING COMPLETE!")
        print("="*50)
        print(f"\n📊 Summary:")
        print(f"   Total processed: {processed_count}")
        print(f"   Successful: {success_count}")
        print(f"   Failed: {failed_count}")
        print(f"   Time taken: {duration:.1f} seconds")
        print(f"\n💰 Financial Summary:")
        print(f"   Source token buybacks: {total_source_buyback:.6f} ETH")
        print(f"   DOK buybacks: {total_dok_buyback:.6f} ETH")
        print(f"   Treasury secured: {total_treasury:.6f} ETH")
        print(f"   Total value processed: {total_source_buyback + total_dok_buyback + total_treasury:.6f} ETH")
        
    except KeyboardInterrupt:
        print(f"\n\n⚠️  Interrupted by user. Processed {processed_count} claims.")
    except Exception as e:
        print(f"\n❌ Critical error: {e}")
        import traceback
        traceback.print_exc()

async def process_multiple_fee_claims():
    """Process multiple fee claims with manual confirmation (legacy)"""
    print("\n🚀 Processing Multiple Fee Claims (Manual Mode)")
    print("="*50)
    
    processed_count = 0
    
    while True:
        # Count unprocessed
        response = requests.post(RPC_URL, json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "alchemy_getAssetTransfers",
            "params": [{
                "fromBlock": "0x0",
                "toBlock": "latest",
                "toAddress": DEPLOYER_ADDRESS,
                "fromAddress": KLIK_FACTORY,
                "category": ["internal"],
                "excludeZeroValue": True,
                "maxCount": "0x64"
            }]
        })
        
        if response.status_code != 200:
            break
            
        data = response.json()
        transfers = data.get('result', {}).get('transfers', [])
        
        conn = sqlite3.connect('deployments.db')
        unprocessed_count = sum(1 for t in reversed(transfers) if not conn.execute(
            "SELECT id FROM fee_claims WHERE claim_tx_hash = ?", (t['hash'],)
        ).fetchone())
        conn.close()
        
        if unprocessed_count == 0:
            print("\n✅ All claims processed!")
            break
            
        print(f"\n📊 {unprocessed_count} unprocessed claims remaining")
        
        # Process one
        await process_single_fee_claim()
        processed_count += 1
        
        if unprocessed_count > 1:
            if input(f"\n🔄 Continue? ({unprocessed_count - 1} left) (yes/no): ").lower() != 'yes':
                break
                
        print(f"\n✅ Processed {processed_count} claims total")
        

async def show_unprocessed_summary():
    """Show summary of all unprocessed fee claims"""
    print("\n📊 Unprocessed Fee Claims Summary")
    print("="*50)
    
    try:
        print("Fetching internal transactions...")
        
        # Get recent internal transactions
        response = requests.post(RPC_URL, json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "alchemy_getAssetTransfers",
            "params": [{
                "fromBlock": "0x0",
                "toBlock": "latest",
                "toAddress": DEPLOYER_ADDRESS,
                "fromAddress": KLIK_FACTORY,
                "category": ["internal"],
                "excludeZeroValue": True,
                "maxCount": "0x64"  # 100 transfers
            }]
        })
        
        if response.status_code != 200:
            print(f"❌ Error fetching transfers: HTTP {response.status_code}")
            print(f"Response: {response.text[:200]}...")
            return
            
        data = response.json()
        
        if 'error' in data:
            print(f"❌ RPC Error: {data['error']}")
            return
            
        transfers = data.get('result', {}).get('transfers', [])
        
        if not transfers:
            print("❌ No fee claims found from Klik Factory")
            print(f"   Deployer: {DEPLOYER_ADDRESS}")
            print(f"   Factory: {KLIK_FACTORY}")
            return
        
        print(f"Found {len(transfers)} total fee claims")
        
        # Check database for already processed claims
        print("Checking database for processed claims...")
        conn = sqlite3.connect('deployments.db')
        
        # Ensure fee_claims table exists
        conn.execute('''
            CREATE TABLE IF NOT EXISTS fee_claims (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                token_address TEXT,
                token_symbol TEXT,
                token_name TEXT,
                pool_address TEXT,
                claimed_amount REAL,
                buyback_amount REAL,
                incentive_amount REAL,
                dev_amount REAL,
                claim_tx_hash TEXT UNIQUE,
                buyback_tx_hash TEXT,
                buyback_dok_amount REAL,
                status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.commit()
        
        unprocessed_claims = []
        total_unprocessed_value = 0.0
        processed_count = 0
        
        for transfer in transfers:
            tx_hash = transfer['hash']
            cursor = conn.execute(
                "SELECT id FROM fee_claims WHERE claim_tx_hash = ?",
                (tx_hash,)
            )
            if not cursor.fetchone():
                unprocessed_claims.append(transfer)
                total_unprocessed_value += float(transfer['value'])
            else:
                processed_count += 1
        
        conn.close()
        
        print(f"✅ Analysis complete:")
        print(f"   Total claims: {len(transfers)}")
        print(f"   Processed: {processed_count}")
        print(f"   Unprocessed: {len(unprocessed_claims)}")
        
        if not unprocessed_claims:
            print("\n🎉 All fee claims have been processed!")
            return
        
        print(f"\n💰 Unprocessed value: {total_unprocessed_value:.6f} ETH")
        print(f"\n📊 Split breakdown:")
        print(f"   Source token buybacks: {total_unprocessed_value * 0.25:.6f} ETH")
        print(f"   DOK buybacks: {total_unprocessed_value * 0.25:.6f} ETH")
        print(f"   Treasury: {total_unprocessed_value * 0.5:.6f} ETH")
        
        # Sort by value descending
        unprocessed_claims.sort(key=lambda x: float(x['value']), reverse=True)
        
        print(f"\n📜 Top unprocessed claims (by value):")
        for i, claim in enumerate(unprocessed_claims[:10]):  # Show top 10
            print(f"\n{i+1}. TX: {claim['hash']}")
            print(f"   Amount: {float(claim['value']):.6f} ETH")
            block_num = int(claim['blockNum'], 16) if isinstance(claim['blockNum'], str) else claim['blockNum']
            print(f"   Block: {block_num}")
            
            # Try to decode to show which token it's from
            print(f"   Decoding to find token...")
            decoded = await factory_interface.decode_collect_fee_transaction(claim['hash'])
            if decoded and decoded.get('token_info'):
                token_info = decoded['token_info']
                print(f"   Token: ${token_info.get('symbol', '???')} - {token_info.get('name', 'Unknown')}")
            elif decoded and decoded.get('deployed_token'):
                print(f"   Token: {decoded['deployed_token']}")
            else:
                print(f"   Token: Unable to decode")
                
        if len(unprocessed_claims) > 10:
            print(f"\n... and {len(unprocessed_claims) - 10} more unprocessed claims")
            
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()

async def test_dok_price_v3():
    """Test getting DOK price from V3 pool"""
    print("\n💱 Testing DOK V3 Price Fetching")
    print("="*50)
    
    try:
        price = await factory_interface.get_dok_price_v3()
        
        print(f"\nDOK Price: {price:.8f} ETH")
        print(f"DOK Price in USD: ${price * 2500:.2f} (assuming $2500/ETH)")
        print(f"\n1 ETH buys: {1/price:,.2f} DOK")
        print(f"0.01 ETH buys: {0.01/price:,.2f} DOK")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

async def debug_transaction():
    """Debug a specific transaction to understand the data"""
    print("\n🔍 Debug Transaction")
    print("="*50)
    
    tx_hash = input("Enter transaction hash to debug (or press Enter for default): ").strip()
    if not tx_hash:
        tx_hash = "0x07469be8b6441e959795fdc61c91ba29d0116d5323bf3690571a57514485494a"
    
    print(f"\nChecking transaction: {tx_hash}")
    
    try:
        # Get transaction
        tx = w3.eth.get_transaction(tx_hash)
        receipt = w3.eth.get_transaction_receipt(tx_hash)
        
        print(f"\nTransaction details:")
        print(f"   From: {tx['from']}")
        print(f"   To: {tx['to']}")
        print(f"   Value: {w3.from_wei(tx['value'], 'ether')} ETH")
        print(f"   Input data: {tx['input'][:66]}...")
        
        # Check logs
        print(f"\nLogs ({len(receipt['logs'])} total):")
        for i, log in enumerate(receipt['logs'][:5]):  # Show first 5 logs
            print(f"\nLog {i}:")
            print(f"   Address: {log['address']}")
            print(f"   Topics: {len(log['topics'])}")
            if log['topics']:
                print(f"   Topic 0: {log['topics'][0].hex()}")
            
            # Check if this is a Transfer event
            if log['topics'] and log['topics'][0].hex() == '0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef':
                print("   ✅ This is a Transfer event")
                if len(log['topics']) >= 3:
                    from_addr = '0x' + log['topics'][1].hex()[-40:]
                    to_addr = '0x' + log['topics'][2].hex()[-40:]
                    print(f"   From: {from_addr}")
                    print(f"   To: {to_addr}")
        
        # Try to decode as factory call
        print("\nTrying to decode as collectFees call...")
        from klik_factory_interface import FACTORY_ABI
        factory_contract = w3.eth.contract(address=KLIK_FACTORY, abi=FACTORY_ABI)
        
        try:
            decoded = factory_contract.decode_function_input(tx['input'])
            print(f"✅ Decoded successfully!")
            print(f"   Function: {decoded[0].fn_name}")
            print(f"   Parameters: {decoded[1]}")
        except Exception as e:
            print(f"❌ Could not decode: {e}")
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

async def test_find_dok_pool():
    """Test finding DOK pool on Uniswap V3"""
    print("\n🔍 Finding DOK Pool on Uniswap V3")
    print("="*50)
    
    try:
        pool_address = await factory_interface.find_dok_weth_v3_pool()
        
        if pool_address:
            print(f"\n✅ Found DOK/WETH pool: {pool_address}")
            
            # Now test getting the price
            print("\nTesting price fetch from discovered pool...")
            price = await factory_interface.get_dok_price_v3()
            print(f"\nDOK Price: {price:.8f} ETH")
            print(f"DOK Price in USD: ${price * 2500:.2f} (assuming $2500/ETH)")
        else:
            print("\n❌ No DOK/WETH pool found on Uniswap V3")
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

async def manual_add_treasury_funds():
    """Manually add funds to fee detection treasury for more free deployments"""
    print("\n💰 ADD TREASURY FUNDS FOR FREE DEPLOYMENTS")
    print("="*50)
    
    try:
        # Show current status first
        conn = sqlite3.connect('deployments.db')
        
        # Get current treasury balance
        cursor = conn.execute(
            "SELECT COALESCE(SUM(amount), 0) FROM balance_sources WHERE source_type = 'fee_detection'"
        )
        treasury_balance = cursor.fetchone()[0]
        
        # Get current wallet balance
        current_balance = w3.eth.get_balance(DEPLOYER_ADDRESS)
        wallet_balance = float(w3.from_wei(current_balance, 'ether'))
        
        # Get user deposits (protected)
        cursor = conn.execute(
            "SELECT COALESCE(SUM(balance), 0) FROM users"
        )
        user_deposits = cursor.fetchone()[0]
        
        # Get platform fees (protected)  
        cursor = conn.execute(
            "SELECT COALESCE(SUM(amount), 0) FROM balance_sources WHERE source_type = 'pay_per_deploy'"
        )
        platform_fees = cursor.fetchone()[0]
        
        print(f"💰 Current Status:")
        print(f"   Wallet Balance: {wallet_balance:.4f} ETH")
        print(f"   Treasury (recorded): {treasury_balance:.4f} ETH")
        print(f"   User Deposits: {user_deposits:.4f} ETH (protected)")
        print(f"   Platform Fees: {platform_fees:.4f} ETH (protected)")
        
        # Calculate how much has been spent from treasury
        spent_from_treasury = treasury_balance - (wallet_balance - user_deposits - platform_fees)
        if spent_from_treasury > 0:
            print(f"   ✅ Spent on free deploys: {spent_from_treasury:.4f} ETH")
        
        # Calculate available for free deployments
        protected_total = user_deposits + platform_fees
        available_for_free = wallet_balance - (protected_total * 1.05)
        print(f"   Available for FREE deploys: {available_for_free:.4f} ETH")
        
        print(f"\n💡 How Treasury Works:")
        print(f"   - Fee detection captures 50% of volume fees")
        print(f"   - This treasury funds FREE deployments")
        print(f"   - Spent treasury = gas costs for free deploys")
        
        print(f"\n🎯 Current gas cost per deploy: ~0.013-0.065 ETH")
        if available_for_free > 0:
            estimated_deploys = int(available_for_free / 0.04)  # Conservative estimate
            print(f"   Estimated free deploys remaining: ~{estimated_deploys}")
        
        # Ask if they want to add funds
        print(f"\n" + "="*50)
        amount_str = input("Enter ETH amount to add to treasury (or press Enter to cancel): ").strip()
        
        if not amount_str:
            print("❌ Cancelled")
            conn.close()
            return
            
        try:
            amount = float(amount_str)
            if amount <= 0:
                print("❌ Amount must be positive")
                conn.close()
                return
                
            if amount > 5:
                print("❌ Maximum 5 ETH per addition for safety")
                conn.close()
                return
                
        except ValueError:
            print("❌ Invalid amount")
            conn.close()
            return
        
        # Ask for description
        description = input(f"Description for this {amount} ETH addition: ").strip()
        if not description:
            description = f"Manual treasury addition for free deployments"
            
        # Generate a manual transaction hash (for tracking)
        import hashlib
        import time
        manual_data = f"manual_treasury_{amount}_{time.time()}_{description}"
        manual_tx_hash = "0x" + hashlib.sha256(manual_data.encode()).hexdigest()[:64]
        
        # Confirm the addition
        print(f"\n🔍 CONFIRM TREASURY ADDITION:")
        print(f"   Amount: {amount} ETH")
        print(f"   Description: {description}")
        print(f"   Tracking hash: {manual_tx_hash[:16]}...")
        print(f"\n⚠️  NOTE: This is accounting only - you must manually")
        print(f"   transfer {amount} ETH to the deployer wallet:")
        print(f"   {DEPLOYER_ADDRESS}")
        
        confirm = input(f"\n✅ Add {amount} ETH to treasury? (yes/no): ").lower()
        
        if confirm != 'yes':
            print("❌ Cancelled")
            conn.close()
            return
            
        # Add to treasury
        conn.execute('''
            INSERT INTO balance_sources (source_type, amount, tx_hash, description)
            VALUES ('fee_detection', ?, ?, ?)
        ''', (amount, manual_tx_hash, description))
        
        conn.commit()
        conn.close()
        
        print(f"\n✅ SUCCESS!")
        print(f"   Added {amount} ETH to fee detection treasury")
        print(f"   New treasury total: {treasury_balance + amount:.4f} ETH")
        print(f"   Estimated additional free deploys: ~{int(amount / 0.04)}")
        print(f"\n🚨 IMPORTANT: Transfer {amount} ETH to deployer wallet:")
        print(f"   {DEPLOYER_ADDRESS}")
        print(f"   Otherwise balance calculations will be wrong!")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    while True:
        print("\n" + "="*50)
        print("FEE DETECTION AND BUYBACK SYSTEM")
        print("="*50)
        print("\nChoose an option:")
        print("1. Detect incoming fee claims")
        print("2. Test buyback split logic")
        print("3. Test small DOK buyback (0.01 ETH)")
        print("4. Process single fee claim (FULL PIPELINE)")
        print("5. Debug transaction")
        print("6. Process multiple fee claims (MANUAL mode)")
        print("7. Show unprocessed claims summary")
        print("8. 🤖 AUTOMATED PROCESSING (no confirmations)")
        print("9. Test DOK price from V3 pool")
        print("10. Test finding DOK pool on Uniswap V3")
        print("11. 💰 Add treasury funds for free deployments")
        print("12. Exit")
        
        choice = input("\nEnter choice (1-12): ")
        
        if choice == "1":
            asyncio.run(detect_incoming_fee_claims())
        elif choice == "2":
            asyncio.run(test_buyback_split())
        elif choice == "3":
            asyncio.run(test_small_dok_buyback())
        elif choice == "4":
            asyncio.run(process_single_fee_claim())
        elif choice == "5":
            asyncio.run(debug_transaction())
        elif choice == "6":
            asyncio.run(process_multiple_fee_claims())
        elif choice == "7":
            asyncio.run(show_unprocessed_summary())
        elif choice == "8":
            asyncio.run(process_all_fee_claims_automated())
        elif choice == "9":
            asyncio.run(test_dok_price_v3())
        elif choice == "10":
            asyncio.run(test_find_dok_pool())
        elif choice == "11":
            asyncio.run(manual_add_treasury_funds())
        elif choice == "12":
            print("\n👋 Goodbye!")
            break
        else:
            print("\n❌ Invalid choice! Please try again.")
        
        # Small pause before showing menu again
        if choice in ["1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "11"]:
            input("\n📌 Press Enter to return to menu...") 