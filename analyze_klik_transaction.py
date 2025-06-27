#!/usr/bin/env python3
"""
Analyze Klik Finance transactions to understand fee claiming
"""

import asyncio
import os
import json
from web3 import Web3
from dotenv import load_dotenv
import requests
import logging

# Load environment
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Get RPC URL
RPC_URL = os.getenv('ALCHEMY_RPC_URL')
w3 = Web3(Web3.HTTPProvider(RPC_URL))

# Known addresses
KLIK_FACTORY = "0x930f9FA91E1E46d8e44abC3517E2965C6F9c4763"
DOK_TOKEN = "0x69ca61398eCa94D880393522C1Ef5c3D8c058837"

def analyze_transaction(tx_hash: str):
    """Analyze a transaction in detail"""
    print(f"\n🔍 Analyzing transaction: {tx_hash}")
    print("="*80)
    
    try:
        # Get transaction
        tx = w3.eth.get_transaction(tx_hash)
        receipt = w3.eth.get_transaction_receipt(tx_hash)
        
        print(f"From: {tx['from']}")
        print(f"To: {tx['to']}")
        print(f"Value: {w3.from_wei(tx['value'], 'ether')} ETH")
        print(f"Gas Used: {receipt['gasUsed']:,}")
        print(f"Status: {'Success' if receipt['status'] == 1 else 'Failed'}")
        
        # Decode input data
        input_hex = tx['input'].hex() if isinstance(tx['input'], bytes) else tx['input']
        print(f"\nInput Data: {input_hex[:66]}...")
        
        # Get method ID (first 4 bytes)
        method_id = input_hex[:10]
        print(f"Method ID: {method_id}")
        
        # If it's collectFees (0xb17acdcd)
        if method_id == '0xb17acdcd':
            # Extract tokenId from input data
            token_id = int(input_hex[10:74], 16)
            print(f"Function: collectFees")
            print(f"Token ID: {token_id}")
            
            # Try to find what token this is for
            print(f"\n🔎 Looking up pool at index {token_id}...")
            try:
                # Get the pool at this index
                response = requests.post(RPC_URL, json={
                    "jsonrpc": "2.0",
                    "method": "eth_call",
                    "params": [{
                        "to": KLIK_FACTORY,
                        "data": f"0x1e3dd18b{token_id:064x}"  # allPairs(uint256)
                    }, "latest"],
                    "id": 1
                })
                
                if response.status_code == 200:
                    result = response.json().get('result')
                    if result and result != '0x':
                        pool_address = '0x' + result[-40:]
                        print(f"Pool Address: {pool_address}")
                        
                        # Get tokens in this pool
                        # token0()
                        response = requests.post(RPC_URL, json={
                            "jsonrpc": "2.0",
                            "method": "eth_call",
                            "params": [{
                                "to": pool_address,
                                "data": "0x0dfe1681"  # token0()
                            }, "latest"],
                            "id": 1
                        })
                        
                        if response.status_code == 200:
                            result = response.json().get('result')
                            if result:
                                token0 = '0x' + result[-40:]
                                print(f"Token0: {token0}")
                                if token0.lower() == DOK_TOKEN.lower():
                                    print("  ✅ This is DOK!")
                        
                        # token1()
                        response = requests.post(RPC_URL, json={
                            "jsonrpc": "2.0",
                            "method": "eth_call",
                            "params": [{
                                "to": pool_address,
                                "data": "0xd21220a7"  # token1()
                            }, "latest"],
                            "id": 1
                        })
                        
                        if response.status_code == 200:
                            result = response.json().get('result')
                            if result:
                                token1 = '0x' + result[-40:]
                                print(f"Token1: {token1}")
                                if token1.lower() == DOK_TOKEN.lower():
                                    print("  ✅ This is DOK!")
                
            except Exception as e:
                print(f"Error looking up pool: {e}")
        
        # Analyze logs
        print(f"\n📜 Transaction Logs ({len(receipt['logs'])} logs):")
        for i, log in enumerate(receipt['logs']):
            print(f"\nLog {i}:")
            print(f"  Address: {log['address']}")
            print(f"  Topics: {len(log['topics'])}")
            if log['topics']:
                topic0_hex = log['topics'][0].hex() if isinstance(log['topics'][0], bytes) else log['topics'][0]
                print(f"    Topic 0: {topic0_hex[:16]}...")
            
            # Check for Transfer events
            if log['topics'] and log['topics'][0].hex() == '0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef':
                print("  ✅ This is a Transfer event")
                if len(log['topics']) >= 3:
                    from_hex = log['topics'][1].hex() if isinstance(log['topics'][1], bytes) else log['topics'][1]
                    to_hex = log['topics'][2].hex() if isinstance(log['topics'][2], bytes) else log['topics'][2]
                    from_addr = '0x' + from_hex[-40:]
                    to_addr = '0x' + to_hex[-40:]
                    print(f"    From: {from_addr}")
                    print(f"    To: {to_addr}")
                    
                    # Check if it's a DOK transfer
                    if log['address'].lower() == DOK_TOKEN.lower():
                        print("    🔥 DOK Transfer!")
                        # Decode amount
                        if log['data'] != '0x':
                            data_hex = log['data'].hex() if isinstance(log['data'], bytes) else log['data']
                            amount = int(data_hex, 16)
                            print(f"    Amount: {amount / 1e18:,.2f} DOK")
        
        # Use Alchemy's enhanced APIs
        print("\n🔮 Using Alchemy Enhanced APIs...")
        
        # Get asset transfers
        response = requests.post(RPC_URL, json={
            "jsonrpc": "2.0",
            "method": "alchemy_getAssetTransfers",
            "params": [{
                "fromBlock": hex(receipt['blockNumber']),
                "toBlock": hex(receipt['blockNumber']),
                "fromAddress": tx['from'],
                "category": ["internal", "erc20"],
                "withMetadata": True
            }],
            "id": 1
        })
        
        if response.status_code == 200:
            transfers = response.json().get('result', {}).get('transfers', [])
            print(f"\nFound {len(transfers)} transfers:")
            for transfer in transfers:
                print(f"\n  Transfer:")
                print(f"    Asset: {transfer.get('asset', 'ETH')}")
                print(f"    From: {transfer.get('from')}")
                print(f"    To: {transfer.get('to')}")
                print(f"    Value: {transfer.get('value')} {transfer.get('asset', 'ETH')}")
                
    except Exception as e:
        print(f"Error: {e}")

def find_dok_pool():
    """Try to find the DOK pool and its tokenId"""
    print("\n🔍 Searching for DOK pool in Klik Factory...")
    print("="*80)
    
    # From the transaction analysis, we know tokenId 1018175 is for DOK
    # Let's verify this
    print("\n1️⃣ Verifying known tokenId 1018175...")
    
    try:
        # Check if tokenId 1018175 gives us a pool with DOK
        token_id = 1018175
        response = requests.post(RPC_URL, json={
            "jsonrpc": "2.0",
            "method": "eth_call",
            "params": [{
                "to": KLIK_FACTORY,
                "data": f"0x1e3dd18b{token_id:064x}"  # allPairs(uint256)
            }, "latest"],
            "id": 1
        })
        
        if response.status_code == 200:
            result = response.json().get('result')
            if result and result != '0x' and len(result) >= 42:
                pool_address = Web3.to_checksum_address('0x' + result[-40:])
                print(f"Pool at index {token_id}: {pool_address}")
                
                # Verify this pool contains DOK
                # token0()
                response = requests.post(RPC_URL, json={
                    "jsonrpc": "2.0",
                    "method": "eth_call",
                    "params": [{
                        "to": pool_address,
                        "data": "0x0dfe1681"  # token0()
                    }, "latest"],
                    "id": 1
                })
                
                token0 = None
                if response.status_code == 200:
                    result = response.json().get('result')
                    if result and len(result) >= 42:
                        token0 = Web3.to_checksum_address('0x' + result[-40:])
                        print(f"Token0: {token0}")
                
                # token1()
                response = requests.post(RPC_URL, json={
                    "jsonrpc": "2.0",
                    "method": "eth_call",
                    "params": [{
                        "to": pool_address,
                        "data": "0xd21220a7"  # token1()
                    }, "latest"],
                    "id": 1
                })
                
                token1 = None
                if response.status_code == 200:
                    result = response.json().get('result')
                    if result and len(result) >= 42:
                        token1 = Web3.to_checksum_address('0x' + result[-40:])
                        print(f"Token1: {token1}")
                
                if DOK_TOKEN in [token0, token1]:
                    print(f"\n✅ CONFIRMED: Token ID {token_id} is for DOK!")
                    print(f"   Pool Address: {pool_address}")
                    return token_id, pool_address
                else:
                    print(f"❌ Pool at {token_id} does not contain DOK")
    
    except Exception as e:
        print(f"Error verifying tokenId: {e}")
    
    # If verification failed, try searching
    print("\n2️⃣ Searching through all pairs...")
    
    try:
        # Get total pairs
        response = requests.post(RPC_URL, json={
            "jsonrpc": "2.0",
            "method": "eth_call",
            "params": [{
                "to": KLIK_FACTORY,
                "data": "0x574f2ba3"  # allPairsLength()
            }, "latest"],
            "id": 1
        })
        
        if response.status_code == 200:
            result = response.json().get('result')
            if result:
                pairs_length = int(result, 16)
                print(f"Total pairs: {pairs_length}")
                
                # Check specific ranges around the known tokenId
                ranges_to_check = [
                    (1018170, 1018180),  # Around the known ID
                    (pairs_length - 10, pairs_length),  # Latest pairs
                ]
                
                for start, end in ranges_to_check:
                    print(f"\nChecking range {start} to {end}...")
                    for i in range(max(0, start), min(pairs_length, end)):
                        # Get pair address
                        response = requests.post(RPC_URL, json={
                            "jsonrpc": "2.0",
                            "method": "eth_call",
                            "params": [{
                                "to": KLIK_FACTORY,
                                "data": f"0x1e3dd18b{i:064x}"  # allPairs(uint256)
                            }, "latest"],
                            "id": 1
                        })
                        
                        if response.status_code == 200:
                            result = response.json().get('result')
                            if result and result != '0x' and len(result) >= 42:
                                pair_address = Web3.to_checksum_address('0x' + result[-40:])
                                print(f"  Checking {i}: {pair_address[:10]}...")
                                
                                # Quick check if it matches known DOK pool
                                if pair_address.lower() == "0xf6e2edc5953da297947c6c68911e16cf1c9b64b6":
                                    print(f"\n✅ FOUND DOK POOL!")
                                    print(f"   Token ID: {i}")
                                    print(f"   Pool Address: {pair_address}")
                                    return i, pair_address
                
    except Exception as e:
        print(f"Error searching: {e}")
    
    return None, None

if __name__ == "__main__":
    # Analyze the transaction provided by the user
    tx_hash = "0xaf643cceb4cba24532afc4181c3746124e0af601e21e4e670a3ba27b4661acf9"
    analyze_transaction(tx_hash)
    
    # Try to find DOK pool
    token_id, pool = find_dok_pool()
    
    if token_id is not None:
        print(f"\n✅ Summary:")
        print(f"   To claim fees for DOK, use tokenId: {token_id}")
        print(f"   Pool address: {pool}")
        print(f"\n   In the frontend, when you enter DOK address:")
        print(f"   {DOK_TOKEN}")
        print(f"   It finds this tokenId and calls collectFees({token_id})") 