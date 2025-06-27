# Klik Finance Fee Claiming System v1.02

## Overview

The automated fee claiming system implements the v1.02 flywheel mechanics for the Deploy On Klik bot:

- **25%** of claimed fees → Automatic DOK buyback & burn
- **25%** of claimed fees → Reserved for future incentives
- **50%** of claimed fees → Bot owner revenue

## Features

### 1. Balance Segregation
The system tracks different balance sources separately to ensure proper fund management:

- **User Deposits**: Protected, only used for user's own deployments
- **Earned Fees**: Protected, belongs to bot owner from fee claims
- **Platform Fees**: Protected, 0.01 ETH fees from pay-per-deploy users
- **Original Funding**: Used for free deployments only

### 2. Fee Claiming Interface

#### Via Telegram Bot UI:
1. Click "💎 Claim Fees" button (bot owner only)
2. Select a token from the list
3. View claimable amount with automatic splits
4. Confirm to execute claim and buyback

#### Via Manual Command:
```
/claim <token_address>
```

Example:
```
/claim 0x69ca61398eCa94D880393522C1Ef5c3D8c058837
```

### 3. Automatic Buyback Process

When fees are claimed:
1. Smart contract sends ETH to bot wallet
2. Bot calculates 25% for buyback
3. Executes swap on Uniswap V2: ETH → DOK
4. Sends DOK directly to burn address (0x000...dead)
5. Records transaction details in database

## Database Schema

### fee_claims
Tracks all fee claim transactions:
- `token_address`: Token contract address
- `claimed_amount`: Total ETH claimed
- `buyback_amount`: 25% for buyback
- `incentive_amount`: 25% for incentives
- `dev_amount`: 50% for developer
- `claim_tx_hash`: Claim transaction hash
- `buyback_tx_hash`: Buyback transaction hash
- `buyback_dok_amount`: DOK tokens burned

### balance_sources
Segregates balance by source:
- `source_type`: 'deposit', 'fee_claim', 'pay_per_deploy'
- `amount`: ETH amount
- `tx_hash`: Related transaction
- `description`: Human-readable description

## Security Features

1. **Owner-Only Access**: Only bot owner (@deployonklik) can claim fees
2. **Balance Protection**: Free deployments cannot use earned revenue
3. **Atomic Updates**: Database uses atomic operations to prevent race conditions
4. **Transaction Verification**: All claims and buybacks are verified on-chain

## Configuration

The system uses these contract addresses:
- **Klik Factory**: `0x930f9FA91E1E46d8e44abC3517E2965C6F9c4763`
- **DOK Token**: `0x69ca61398eCa94D880393522C1Ef5c3D8c058837`
- **Uniswap V2 Router**: `0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D`

## Testing

Use the test script to verify functionality:
```bash
python test_fee_claim.py
```

Options:
1. Test fee claim for DOK token
2. Check all recent pools

## Important Notes

1. **No View Function**: Klik Factory doesn't have a view function for claimable fees. The system attempts to simulate the claim to estimate fees.

2. **Token ID Mapping**: The factory uses token IDs (array indices) rather than direct token addresses. The system searches through the `allPairs` array to find the correct ID.

3. **Buyback Slippage**: Set to 2% by default to handle price fluctuations during the swap.

4. **Gas Buffer**: All transactions use a 10-20% gas buffer to ensure successful execution.

## Future Enhancements

1. **Real-time Price Oracle**: Integrate Chainlink or similar for accurate DOK pricing
2. **Multi-DEX Support**: Check multiple DEXs for best execution price
3. **Batch Claims**: Claim fees from multiple tokens in one transaction
4. **Incentive Distribution**: Automated system for the 25% incentive allocation

## How It Works

### Fee Claiming Process
1. Bot owner uses `/claim <token_address>` or clicks "💎 Claim Fees" button
2. System finds the tokenId for the given token address
3. Calls `collectFees(tokenId)` on the Klik Factory contract
4. Factory transfers accumulated fees (DOK + ETH) to the bot wallet
5. System automatically:
   - Sends 25% of ETH to buyback DOK and burn it
   - Reserves 25% for incentives
   - Credits 50% to bot owner's revenue

### Token Address to TokenId Mapping

Klik Finance uses a tokenId system where each pool has a unique index in the `allPairs` array. When you enter a token address (like DOK), the system needs to find which tokenId corresponds to that token's pool.

**Example**: DOK (0x69ca61398eCa94D880393522C1Ef5c3D8c058837) has tokenId 1018175

The system uses several methods to find the tokenId:
1. **Known Mappings**: Common tokens like DOK have hardcoded tokenIds for efficiency
2. **Alchemy API Search**: Uses enhanced APIs to find pool creation events
3. **Fallback Search**: Iterates through the allPairs array to find the token

### V1.02 Flywheel Mechanics

# ... existing code ... 