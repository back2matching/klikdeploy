# Klik Finance Fee Detection & Buyback System v1.03

## Overview

The automated fee detection system monitors incoming fee claims from the Klik Finance platform and implements v1.03 flywheel mechanics for the Deploy On Klik bot:

- **25%** of received fees → Automatic source token buyback & hold (pump chart)
- **25%** of received fees → Automatic DOK buyback & hold (pump chart)  
- **50%** of received fees → Bot owner treasury (protected)

## How It Works

### Passive Fee Detection
1. Platform (Alex04) runs `collectFees()` for our deployed tokens (1-2x per week)
2. ETH fees are sent to our deployer wallet automatically
3. Our system detects these incoming transfers from Klik Factory
4. System decodes the transaction to identify which token generated the fees
5. Executes automatic buybacks for both source token and DOK

### No Active Claiming
- We DO NOT claim fees ourselves (saves gas)
- Platform handles all fee collection on a random schedule
- We only process what we receive

## Features

### 1. Balance Segregation
The system tracks different balance sources separately to ensure proper fund management:

- **User Deposits**: Protected, only used for user's own deployments
- **Platform Fees**: Protected, 0.01 ETH fees from pay-per-deploy users
- **Fee Detection Revenue**: Protected, 50% treasury from detected fee claims
- **Original Funding**: Used for free deployments only

### 2. Fee Detection Interface

#### Via Test Script:
```bash
python test_fee_detection.py
```

Options:
1. Detect incoming fee claims - Shows unprocessed fee transfers
2. Test buyback split logic - Mock test of the split calculations
3. Test small DOK buyback - Execute a small test buyback

### 3. Automatic Buyback Process

When fees are detected:
1. System identifies new incoming transfers from Klik Factory
2. Decodes transaction to find source token (via tokenId)
3. Calculates splits: 25% source token, 25% DOK, 50% treasury
4. Executes swap on Uniswap V2: ETH → Source Token → Hold
5. Executes swap on Uniswap V2: ETH → DOK → Hold
6. Records all transactions in database

## Database Schema

### fee_claims
Tracks all detected fee claim transactions:
- `token_address`: Token that generated the fees
- `claimed_amount`: Total ETH received
- `buyback_amount`: 25% for source token buyback
- `dok_buyback_amount`: 25% for DOK buyback  
- `treasury_amount`: 50% for developer
- `claim_tx_hash`: Incoming fee transfer hash
- `source_buyback_tx_hash`: Source token buyback tx
- `dok_buyback_tx_hash`: DOK buyback tx
- `status`: 'detected', 'processing', 'completed'

### balance_sources
Segregates balance by source:
- `source_type`: 'deposit', 'fee_detection', 'pay_per_deploy'
- `amount`: ETH amount
- `tx_hash`: Related transaction
- `description`: Human-readable description

## Security Features

1. **Passive Only**: No active claiming reduces attack surface
2. **Balance Protection**: Free deployments cannot use earned revenue
3. **Atomic Updates**: Database uses atomic operations to prevent race conditions
4. **Transaction Verification**: All incoming transfers are verified on-chain

## Configuration

The system uses these contract addresses:
- **Klik Factory**: `0x930f9FA91E1E46d8e44abC3517E2965C6F9c4763`
- **DOK Token**: `0x69ca61398eCa94D880393522C1Ef5c3D8c058837`
- **Uniswap V2 Router**: `0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D`
- **Bought tokens held in deployer wallet**

## Fee Detection Process

### 1. Monitor Incoming Transfers
```python
# Check for internal ETH transfers from Klik Factory
transfers = alchemy_getAssetTransfers({
    "fromAddress": KLIK_FACTORY,
    "toAddress": DEPLOYER_ADDRESS,
    "category": ["internal"]
})
```

### 2. Decode Transaction
```python
# Decode collectFee call to get tokenId
decoded = decode_collect_fee_transaction(tx_hash)
token_address = decoded['deployed_token']
```

### 3. Execute Buybacks
```python
# 25% for source token
await execute_token_buyback(token_address, amount * 0.25)

# 25% for DOK
await execute_dok_buyback(amount * 0.25)

# 50% kept in treasury
```

## V1.03 Flywheel Mechanics

The dual buyback system creates constant buying pressure:
1. Source token buyback supports individual token prices (pumps chart)
2. DOK buyback supports the ecosystem token (pumps chart)
3. All bought tokens held by bot (community can decide future use)
4. Treasury funds ensure long-term sustainability

## Future Enhancements

1. **Automated Processing**: Cron job to check and process detected fees
2. **Multi-DEX Support**: Check multiple DEXs for best execution
3. **Notification System**: Alert when fees are detected and processed
4. **Analytics Dashboard**: Track buyback impact on token prices

## Migration from Active Claiming

- All active fee claiming functions have been deprecated
- `/claim` command removed from Telegram bot
- Focus shifted to passive detection and processing
- Gas savings passed to users through continued free deployments
