# $DOK Holder System

## Overview
The holder system provides benefits to users who hold 0.5% or more of the $DOK token supply.

## Token Details
- **Token**: Deploy On Klik (DOK)
- **Contract**: `0x69ca61398eCa94D880393522C1Ef5c3D8c058837`
- **Total Supply**: 1,000,000,000 DOK
- **Holder Requirement**: 5,000,000 DOK (0.5% of supply)

## Holder Benefits
1. **2 FREE deployments per day** (instead of 1)
2. **Higher gas limit**: Deploy when gas ≤ 15 gwei
3. **NO platform fees**: Save 0.01 ETH per deployment
4. **Priority support**

## How It Works

### Wallet Verification Required
To prevent wallet theft, holders must **prove ownership** by:
1. Registering their wallet in Telegram bot
2. **Depositing 0.03+ ETH once** from that wallet
3. Having 5M+ DOK in the verified wallet

This prevents users from claiming someone else's whale wallet!

### Automatic Verification
- When users deploy tokens, system checks:
  - ✅ Do they have 5M+ DOK?
  - ✅ Have they deposited from this wallet?
- Both required for holder benefits
- Status updates in real-time

### Manual Verification
Users can check their holder status anytime:

1. **Via Telegram Bot**:
   - Open @DeployOnKlikBot
   - Click "🎯 Check $DOK Holder"
   - Shows current balance and status

2. **Via Command Line**:
   ```bash
   python holder_verification.py username
   ```

### Batch Updates
To update all users' holder statuses:
```bash
# One-time update
python holder_verification.py update

# Or run periodic updates
python run_holder_updates.py
```

## Setup Requirements

### Database Schema
The system uses these fields in the `users` table:
- `is_holder`: Boolean flag for holder status
- `holder_balance`: Current DOK balance

### Environment Variables
```bash
# In .env
DOK_TOKEN_ADDRESS=0x69ca61398eCa94D880393522C1Ef5c3D8c058837
DOK_MIN_BALANCE=5000000  # 5M DOK
```

## Buy $DOK
- [DexScreener](https://dexscreener.com/ethereum/0x69ca61398eca94d880393522c1ef5c3d8c058837)
- [Uniswap](https://app.uniswap.org/#/swap?outputCurrency=0x69ca61398eca94d880393522c1ef5c3d8c058837)

## Technical Implementation

### Check Holder Status
```python
from holder_verification import check_holder_status

# Returns: (is_holder, balance, percentage)
is_holder, balance, percentage = check_holder_status(wallet_address)
```

### Update User Status
```python
# Updates database with current holder status
verify_specific_user("username")
```

### Periodic Updates
Run as a cron job:
```bash
# Every 30 minutes
*/30 * * * * cd /path/to/project && python run_holder_updates.py --once
```

Or as a service:
```bash
# Continuous monitoring
python run_holder_updates.py
```

## FAQ

**Q: How often is holder status updated?**
A: Automatically when you deploy, or manually via Telegram bot. Batch updates run every 30 minutes.

**Q: What if I move my DOK to a different wallet?**
A: Update your registered wallet in the Telegram bot, then check holder status.

**Q: Do I need exactly 5M DOK?**
A: You need at least 5,000,000 DOK. More is fine!

**Q: Can I still deploy if I'm not a holder?**
A: Yes! You can use the free tier (1/day at low gas) or pay-per-deploy.

**Q: Why do I need to deposit to verify my wallet?**
A: This prevents wallet theft. Without verification, anyone could claim Vitalik's wallet and get holder benefits! One deposit proves you control the private keys.

**Q: I have 10M DOK but no holder benefits?**
A: You need to deposit 0.03+ ETH once from your registered wallet to verify ownership. This is a one-time security requirement. 