# Deposit System Update Documentation

## Overview
Updated the deposit monitoring system to be more robust and reliable using the Alchemy Transfers API.

## Key Changes

### 1. Automatic Deposit Monitoring
- The `monitor_deposits()` function now actively checks for deposits every 30 seconds
- On startup, checks the last 300 blocks (~1 hour) for any missed deposits
- Continuously monitors from the last checked block to avoid missing transactions
- Automatically credits users when valid deposits are detected

### 2. Manual Check Button Improvements
- The "Check Deposits" button now checks the ENTIRE transaction history from the user's wallet
- This ensures users can claim ANY valid historical deposits, no matter how old
- Still validates that deposits haven't already been credited to prevent duplicates
- Shows summary of total transfers found, already credited, and invalid amounts

### 3. Deposit Processing Logic
- Valid deposits must be between 0.03 - 1 ETH
- Must be sent TO the bot wallet address
- Must be FROM the user's registered wallet address
- Requires 3+ block confirmations for security
- Sends automatic Telegram notification when deposit is credited

### 4. Support Tools
- Added `/credit_tx <tx_hash>` command for bot owner to manually credit specific transactions
- Useful for edge cases where automatic detection might fail
- Validates transaction details before crediting

## How It Works

### For Users:
1. Register wallet with the bot
2. Send 0.03-1 ETH from that wallet to the bot wallet
3. Within 30 seconds, the deposit is automatically detected and credited
4. If not auto-detected, click "Check Deposits" button to check ALL historical transfers
5. Receive notification when deposit is credited

### For Support:
1. If a user reports an uncredited deposit, verify the transaction on Etherscan
2. Use `/credit_tx <transaction_hash>` to manually credit it
3. System will validate and credit the deposit if valid

## Security Features
- Only deposits from registered wallets are credited to users
- Deposits from unregistered wallets are recorded but marked as "UNREGISTERED"
- Transaction hash tracking prevents double-crediting
- 3 block confirmation requirement prevents issues with chain reorganizations

## Database Schema
The system uses these key tables:
- `users`: Stores user info including balance and registered wallet
- `deposits`: Records all deposits with tx_hash as unique identifier
- `balance_sources`: Tracks where balance came from (deposits, fee claims, etc.)

## Error Handling
- If Alchemy API fails, monitoring continues and retries
- Failed notifications don't block deposit processing
- All errors are logged for debugging

## Example Transaction Flow
1. User sends 0.03 ETH from registered wallet `0x2fE33b2BE0ebb19a12f17c487534e7B5Dd45A294`
2. Monitor detects transfer to bot wallet `0xb3Bc6906F91181122F6499A32A0D04390ec87273`
3. Verifies 3+ confirmations
4. Credits user balance in database
5. Sends Telegram notification to user
6. User can now deploy tokens with their balance 