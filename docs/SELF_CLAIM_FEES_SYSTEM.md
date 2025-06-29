# Self-Claim Fees System

## Overview

The Self-Claim Fees system allows verified users to capture 50% of fees from their token deployments instead of having those fees go to the community buyback system. This is a simple extension of the existing automated fee detection system.

## How It Works

### Current Fee Distribution (Default)
- **25%** → Source token buyback (pumps the token chart)
- **25%** → $DOK buyback (pumps $DOK chart) 
- **50%** → Community treasury (funds free deployments)

### Self-Claim Mode (Verified Users Only)
- **25%** → Source token buyback (pumps the token chart)
- **25%** → $DOK buyback (pumps $DOK chart)
- **50%** → User claimable fees (stored in database)

## System Components

### 1. Automated Fee Detection (`test_fee_detection.py`)
The existing automated fee detection system now checks user preferences:

```python
# For each detected fee, check user preference
fee_splits = db.process_fee_claim_for_user(token_address, value, tx_hash)

# Returns appropriate split based on user settings:
# - Normal: automated buybacks
# - Self-claim: user gets 50% as claimable fees
```

### 2. User Management (Telegram Bot)
Verified users can:
- Toggle self-claim fees on/off
- View accumulated claimable fees
- Claim their fees as ETH withdrawals

### 3. Database Tracking
- `user_fee_settings` - tracks who has self-claim enabled
- `deployment_fees` - tracks claimable amounts per user per token
- Fully backwards compatible with existing system

## Security Protections

### Account Verification Security
The system includes multiple layers of protection against verification exploits:

#### **Twitter Username Changes**
When a user changes their Twitter username:
- ✅ **Verification is automatically RESET** 
- ⚠️ User must re-verify the new Twitter account
- 🔒 Fee capture is disabled until re-verification
- 📝 User is clearly notified about the security reset

```
⚠️ SECURITY: Account verification reset - you must re-verify @newusername to claim fees
```

#### **Wallet Address Changes**  
When a user changes their wallet address:
- ✅ **Verification is automatically RESET**
- ⚠️ User must re-verify their Twitter account
- 🔒 Fee capture is disabled until re-verification
- 💰 They must deposit from the new wallet to prove ownership

#### **Multi-Layer Protection**
1. **Verification Required**: Only Twitter-verified accounts can enable fee capture
2. **Wallet Ownership**: Must deposit from registered wallet to prove control
3. **Automatic Reset**: Changes to critical details reset verification
4. **Real-time Checks**: Fee capture status checked on every fee distribution

### Attack Prevention
The system prevents common verification exploits:

❌ **Cannot do**: Get verified as `@alice`, change to `@bob`, claim fees as `@bob`
✅ **Must do**: Re-verify `@bob` Twitter account after username change

❌ **Cannot do**: Get verified with wallet A, change to wallet B, claim fees  
✅ **Must do**: Re-verify Twitter + deposit from wallet B to prove ownership

## User Requirements

### Verification Required
Only Twitter-verified users can enable self-claim:
- Must verify Twitter account via bot
- Verification prevents unauthorized fee claiming
- Unverified users default to community fee split

### Wallet Verification
- Must have registered wallet address
- Must have made at least one deposit (proves wallet ownership)
- Prevents others from claiming fees for someone else's tokens

## Implementation Benefits

### For Users
- **Choice**: Community support OR personal profit
- **Transparency**: See exactly what fees you're earning
- **Control**: Enable/disable anytime
- **Security**: Only verified accounts can claim

### For Platform
- **Backwards Compatible**: Existing system unchanged
- **Automated**: No manual intervention needed
- **Secure**: Multiple verification layers
- **Scalable**: Works with any number of users

## Technical Flow

1. **Token Deployed** → User deploys via Twitter
2. **Fees Generated** → Trading volume generates fees on Klik Factory
3. **Automated Detection** → `test_fee_detection.py` detects fees
4. **User Check** → System checks if deployer has self-claim enabled
5. **Smart Split**:
   - **If self-claim OFF**: Normal automated buybacks
   - **If self-claim ON**: Record as user claimable fees
6. **User Claims** → User withdraws accumulated fees via Telegram bot

## Key Features

- **Seamless Integration**: Works with existing automated systems
- **User Control**: Simple toggle in Telegram bot
- **Security**: Multiple verification layers
- **Transparency**: Users see exactly what they earn
- **Backwards Compatible**: No changes to existing functionality

## Database Schema

### user_fee_settings
- `username` - Twitter username
- `fee_capture_enabled` - Boolean preference
- `created_at` - When preference was set

### deployment_fees  
- `token_address` - Deployed token address
- `deployer_username` - Who deployed it
- `fee_potential` - Total fees this token could generate
- `claimed_amount` - How much user has claimed
- `claimable_amount` - Available to claim now

## Migration & Compatibility

- **Existing deployments**: Continue using community fee split
- **New deployments**: Use deployer's current preference
- **Settings changes**: Apply to future fees only
- **Database migration**: Adds new tables, preserves all existing data

The system is designed to be a natural extension of the existing automated fee detection, giving users choice while maintaining all the benefits of the community buyback system for those who prefer it. 