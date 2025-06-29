# 💰 Self-Claim Fees System

## 🎯 Overview

The Self-Claim Fees system allows verified users to choose between:

1. **🌍 Community Fee Split** (Default): Fees fund community token buybacks
2. **💰 Self-Claim Fees**: Users claim 50% of their deployment fees directly

## 🔧 System Architecture

### Database Schema

#### New Tables Added:

**`user_fee_settings`**
```sql
CREATE TABLE user_fee_settings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE,
    fee_capture_enabled BOOLEAN DEFAULT FALSE,
    last_modified TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**`deployment_fees`**
```sql
CREATE TABLE deployment_fees (
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
    status TEXT DEFAULT 'pending'
);
```

### Fee Distribution Logic

#### Community Split (Default):
- **25%** → Source token buyback (pump chart)
- **25%** → $DOK buyback (pump chart)  
- **50%** → Platform treasury

#### Self-Claim Mode:
- **25%** → Source token buyback (pump chart)
- **25%** → $DOK buyback (pump chart)
- **50%** → User's claimable balance

## 🚀 User Experience

### Telegram Bot Interface

#### Dashboard Changes:
```
🎯 **@username** (Regular User)
🔐 Account: ✅ Verified
💰 Balance: 0.0500 ETH

💰 **Self-Claim Fees: ENABLED**
• Claimable: 0.0045 ETH
• Total claimed: 0.0123 ETH

[✅ Verified Account] [💰 Fee Settings]
```

#### Fee Settings Menu:
```
**Fee Capture Settings 💰**
Account: @username
Current Mode: 💰 SELF-CLAIM FEES

**How It Works:**
🌍 Community Split:
• 25% → Source token buyback (pump chart)
• 25% → $DOK buyback (pump chart)  
• 50% → Platform treasury
• You get: Chart pumps for your tokens

💰 Self-Claim:
• 25% → Source token buyback (pump chart)
• 25% → $DOK buyback (pump chart)
• 50% → Your wallet (claimable)
• You get: ETH + chart pumps

[🌍 Switch to Community Split]
[💰 View Claimable Fees]
[🏠 Main Menu]
```

### Security Requirements

✅ **Only verified users** can enable self-claim fees
✅ **Twitter verification** required via unique code tweet
✅ **Wallet verification** required via 0.03+ ETH deposit
✅ **Preference tracking** per user in database

## 🔄 Implementation Flow

### 1. New Deployment Process

```python
# When deployment succeeds
deployment_id = save_deployment(request)
db.record_deployment_fee_potential(
    deployment_id, token_address, token_symbol, username
)
```

### 2. Fee Detection & Processing

```python
# When fees are detected from Klik Factory
fee_splits = db.process_fee_claim_for_user(token_address, total_fee_amount, tx_hash)

# fee_splits contains:
# - user_claims: Amount going to users
# - source_buyback: For token buyback
# - dok_buyback: For DOK buyback  
# - treasury: Remaining for platform
```

### 3. User Preference Management

```python
# Enable self-claim for verified user
db.set_user_fee_capture_preference(username, True)

# Check user's preference
enabled = db.get_user_fee_capture_preference(username)

# Get user's claimable fees
claimable_fees = db.get_user_claimable_fees(username)
```

## 🛡️ Security & Verification

### Twitter Verification Flow:
1. User clicks "🔐 Verify Twitter" in Telegram
2. System generates unique 8-character code
3. User tweets: `@DeployOnKlik !verify user [CODE] in order to use start claiming fees from @username`
4. System detects tweet and verifies account automatically
5. Fee capture options unlock

### Wallet Verification:
- User must deposit 0.03+ ETH from their registered wallet
- Proves ownership of the wallet address
- Required for all advanced features

## 📊 Database Methods

### Core Functions:

```python
# Set user preference
set_user_fee_capture_preference(username: str, enabled: bool) -> bool

# Get user preference  
get_user_fee_capture_preference(username: str) -> bool

# Record deployment for fee tracking
record_deployment_fee_potential(deployment_id: int, token_address: str, 
                               token_symbol: str, username: str) -> None

# Process fee claim with user preferences
process_fee_claim_for_user(token_address: str, total_fee_amount: float, 
                         claim_tx_hash: str) -> Dict[str, float]

# Get user's claimable fees
get_user_claimable_fees(username: str) -> List[Dict]

# Get user fee statistics
get_user_fee_stats(username: str) -> Dict
```

## 🔧 Migration & Deployment

### Database Migration:
```bash
python migrate_self_claim_fees.py
```

This script:
- ✅ Creates backup of existing database
- ✅ Adds new tables and indexes
- ✅ Backfills existing deployments for fee tracking
- ✅ Maintains backward compatibility

### Integration Points:

1. **`deployer/database/deployment_db.py`**: Core database functionality
2. **`telegram_deposit_bot.py`**: User interface and preferences
3. **`test_fee_detection.py`**: Updated fee processing logic
4. **`klik_token_deployer.py`**: Records new deployments for tracking

## 📈 Expected Impact

### User Benefits:
- **Choice**: Users can choose between community benefit and personal profit
- **Transparency**: Clear tracking of fees generated by their deployments  
- **Incentive**: Direct financial reward for successful token deployments

### Platform Benefits:
- **Retention**: Users more likely to deploy multiple tokens
- **Verification**: Encourages Twitter verification for fee capture
- **Balance**: Community still benefits from 50% going to buybacks

### Security Benefits:
- **Verified Only**: Only verified accounts can claim fees
- **Prevents Exploitation**: Unverified users default to community split
- **Maintained Buybacks**: Token ecosystems still get buying pressure

## 🚧 Future Enhancements

### Phase 2 Features:
1. **Smart Contract Claiming**: Direct on-chain fee claiming
2. **Batch Claims**: Claim fees from multiple tokens at once  
3. **Auto-Claim**: Automatic claiming above threshold amounts
4. **Fee Analytics**: Detailed fee generation analytics per token

### Phase 3 Features:
1. **Fee Sharing**: Split fees between multiple deployers
2. **Community Pools**: Pool fees for specific purposes
3. **Governance**: Community voting on fee distribution
4. **Advanced Analytics**: ROI tracking for deployments

## 🎯 Success Metrics

### Key Performance Indicators:
- **Verification Rate**: % of users who verify accounts
- **Self-Claim Adoption**: % of verified users enabling self-claim
- **Fee Generation**: Total fees generated by self-claim users
- **User Retention**: Deployment frequency after enabling self-claim

### Expected Outcomes:
- ✅ Increased user verification rates
- ✅ Higher user engagement and retention  
- ✅ More frequent token deployments
- ✅ Balanced ecosystem growth (users + community)

---

## 🚀 Ready for Launch

The Self-Claim Fees system is now fully implemented and ready for production deployment. The system maintains backward compatibility while providing new value for verified users.

**Next Steps:**
1. Run migration script on production database
2. Deploy updated code to production servers
3. Announce feature to existing users
4. Monitor adoption and user feedback

🎉 **Self-Claim Fees feature is complete and ready!** 