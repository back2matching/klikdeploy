"""
Database operations for deployment tracking and user management
"""

import sqlite3
import logging
from datetime import datetime, timedelta
from typing import Optional, Tuple, Dict, List
import os

# Configure SQLite to handle datetime properly for Python 3.12+
sqlite3.register_adapter(datetime, lambda dt: dt.isoformat())
sqlite3.register_converter("timestamp", lambda b: datetime.fromisoformat(b.decode()))


class DeploymentDatabase:
    """Handles all database operations for the deployment system"""
    
    def __init__(self, db_path: str = 'deployments.db'):
        """Initialize database connection"""
        self.db_path = db_path
        self.logger = logging.getLogger('klik_deployer')
        self._setup_database()
    
    def _setup_database(self):
        """Setup SQLite database for tracking deployments"""
        with sqlite3.connect(self.db_path, detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES) as conn:
            # Original deployments table
            conn.execute('''
                CREATE TABLE IF NOT EXISTS deployments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tweet_id TEXT UNIQUE,
                    username TEXT,
                    token_name TEXT,
                    token_symbol TEXT,
                    requested_at TIMESTAMP,
                    deployed_at TIMESTAMP,
                    tx_hash TEXT,
                    token_address TEXT,
                    status TEXT DEFAULT 'pending',
                    tweet_url TEXT,
                    parent_tweet_id TEXT,
                    image_url TEXT,
                    image_ipfs TEXT,
                    salt TEXT,
                    predicted_address TEXT
                )
            ''')
            
            # New user accounts table
            conn.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    twitter_username TEXT UNIQUE,
                    eth_address TEXT,
                    telegram_id INTEGER,
                    balance REAL DEFAULT 0,
                    is_holder BOOLEAN DEFAULT FALSE,
                    holder_balance REAL DEFAULT 0,
                    twitter_verified BOOLEAN DEFAULT FALSE,
                    verification_code TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Deposits tracking
            conn.execute('''
                CREATE TABLE IF NOT EXISTS deposits (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    twitter_username TEXT,
                    amount REAL,
                    tx_hash TEXT UNIQUE,
                    from_address TEXT,
                    confirmed BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Daily limits tracking
            conn.execute('''
                CREATE TABLE IF NOT EXISTS daily_limits (
                    username TEXT,
                    date DATE,
                    free_deploys INTEGER DEFAULT 0,
                    holder_deploys INTEGER DEFAULT 0,
                    PRIMARY KEY (username, date)
                )
            ''')
            
            # Add balance_sources table for tracking different balance types
            conn.execute('''
                CREATE TABLE IF NOT EXISTS balance_sources (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source_type TEXT, -- 'deposit', 'fee_detection', 'pay_per_deploy', 'dev_protected', 'gas_expenses'
                    amount REAL,
                    tx_hash TEXT,
                    description TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Progressive cooldown tracking table
            conn.execute('''
                CREATE TABLE IF NOT EXISTS deployment_cooldowns (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE,
                    free_deploys_7d INTEGER DEFAULT 0,
                    last_free_deploy TIMESTAMP,
                    cooldown_until TIMESTAMP,
                    consecutive_days INTEGER DEFAULT 0,
                    total_free_deploys INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_username_date 
                ON deployments(username, requested_at)
            ''')
            
            # Add new columns if they don't exist (for existing databases)
            try:
                conn.execute('ALTER TABLE deployments ADD COLUMN salt TEXT')
            except sqlite3.OperationalError:
                pass  # Column already exists
            
            try:
                conn.execute('ALTER TABLE deployments ADD COLUMN predicted_address TEXT')
            except sqlite3.OperationalError:
                pass  # Column already exists
        
        self.logger.info("Database initialized with user accounts")
    
    def save_deployment(self, request) -> None:
        """Save deployment request to database"""
        with sqlite3.connect(self.db_path, detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES) as conn:
            conn.execute('''
                INSERT OR REPLACE INTO deployments 
                (tweet_id, username, token_name, token_symbol, requested_at, 
                 deployed_at, tx_hash, token_address, status, tweet_url, 
                 parent_tweet_id, image_url, salt, predicted_address)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                request.tweet_id, request.username.lower(), request.token_name, request.token_symbol,
                request.requested_at, request.deployed_at, request.tx_hash, request.token_address, 
                request.status, request.tweet_url, request.parent_tweet_id, request.image_url,
                request.salt, request.predicted_address
            ))
    
    def update_deployment(self, request) -> None:
        """Update deployment in database"""
        with sqlite3.connect(self.db_path, detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES) as conn:
            conn.execute('''
                UPDATE deployments 
                SET deployed_at=?, tx_hash=?, token_address=?, status=?
                WHERE tweet_id=?
            ''', (request.deployed_at, request.tx_hash, request.token_address, request.status, request.tweet_id))
    
    def get_total_user_deposits(self) -> float:
        """Get total balance of all user deposits"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT COALESCE(SUM(balance), 0) FROM users WHERE balance > 0"
            )
            total = cursor.fetchone()[0]
            return float(total)
    
    def get_user_balance(self, username: str) -> float:
        """Get user's ETH balance from database"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT balance FROM users WHERE LOWER(twitter_username) = LOWER(?)",
                (username,)
            )
            result = cursor.fetchone()
            return result[0] if result else 0.0
    
    def get_balance_by_source(self, source_type: str) -> float:
        """Get total balance from a specific source type"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT COALESCE(SUM(amount), 0) FROM balance_sources WHERE source_type = ?",
                (source_type,)
            )
            return float(cursor.fetchone()[0])
    
    def check_holder_status(self, username: str) -> Tuple[bool, Optional[str]]:
        """Check if user is a verified holder
        
        Returns:
            Tuple of (is_holder, eth_address)
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT is_holder, eth_address FROM users WHERE LOWER(twitter_username) = LOWER(?)",
                (username,)
            )
            result = cursor.fetchone()
            
            if not result:
                return False, None
            
            is_holder, wallet = result
            
            # SECURITY: Check if user has ever deposited from this wallet
            # This proves they own the wallet
            cursor = conn.execute(
                "SELECT COUNT(*) FROM deposits WHERE LOWER(twitter_username) = LOWER(?) AND LOWER(from_address) = LOWER(?) AND confirmed = 1",
                (username, wallet)
            )
            deposit_count = cursor.fetchone()[0]
            
            if deposit_count == 0:
                # No deposits from this wallet = not verified
                self.logger.info(f"@{username} has not deposited from wallet {wallet[:6]}...{wallet[-4:]} - holder benefits disabled")
                return False, None
            
            return bool(is_holder), wallet
    
    def update_holder_status(self, username: str, is_holder: bool, balance: float) -> None:
        """Update user's holder status"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "UPDATE users SET is_holder = ?, holder_balance = ? WHERE LOWER(twitter_username) = LOWER(?)",
                (is_holder, balance, username)
            )
    
    def get_deployment_stats(self) -> Dict:
        """Get deployment statistics for the last 24 hours"""
        with sqlite3.connect(self.db_path, detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES) as conn:
            cursor = conn.execute('''
                SELECT 
                    COUNT(*) as total,
                    SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) as successful,
                    COUNT(DISTINCT username) as unique_users,
                    SUM(CASE WHEN image_ipfs IS NOT NULL THEN 1 ELSE 0 END) as with_images
                FROM deployments
                WHERE requested_at > datetime('now', '-24 hours')
            ''')
            stats = cursor.fetchone()
        
        return {
            'total_requests_24h': stats[0],
            'successful_deploys_24h': stats[1],
            'unique_users_24h': stats[2],
            'tokens_with_images_24h': stats[3]
        }
    
    def update_image_ipfs(self, tweet_id: str, image_ipfs: str) -> None:
        """Update the image IPFS hash for a deployment"""
        with sqlite3.connect(self.db_path, detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES) as conn:
            conn.execute(
                "UPDATE deployments SET image_ipfs = ? WHERE tweet_id = ?",
                (image_ipfs, tweet_id)
            )
    
    def check_progressive_cooldown(self, username: str) -> tuple[bool, str, int]:
        """Check progressive cooldown for free deployments
        
        Returns:
            tuple: (can_deploy, message, days_until_cooldown_ends)
        """
        now = datetime.now()
        seven_days_ago = now - timedelta(days=7)
        
        with sqlite3.connect(self.db_path, detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES) as conn:
            # Get or create cooldown record
            cursor = conn.execute('''
                SELECT free_deploys_7d, last_free_deploy, cooldown_until, consecutive_days, total_free_deploys
                FROM deployment_cooldowns 
                WHERE LOWER(username) = LOWER(?)
            ''', (username,))
            
            cooldown_data = cursor.fetchone()
            
            if not cooldown_data:
                # First time user
                conn.execute('''
                    INSERT INTO deployment_cooldowns (username, free_deploys_7d, last_free_deploy, updated_at)
                    VALUES (?, 0, ?, ?)
                ''', (username.lower(), now, now))
                return True, "First deployment allowed", 0
            
            free_deploys_7d, last_free_deploy, cooldown_until, consecutive_days, total_free_deploys = cooldown_data
            
            # Check if currently in cooldown
            if cooldown_until and cooldown_until > now:
                days_left = (cooldown_until - now).days + 1
                return False, f"Progressive cooldown active. {days_left} days remaining", days_left
            
            # Count free deployments in last 7 days (more accurate)
            cursor = conn.execute('''
                SELECT COUNT(*) FROM deployments 
                WHERE LOWER(username) = LOWER(?) 
                AND requested_at > ? 
                AND status = 'success'
            ''', (username, seven_days_ago))
            
            actual_free_deploys_7d = cursor.fetchone()[0]
            
            # Get list of recent deployments for debugging
            cursor = conn.execute('''
                SELECT token_symbol, deployed_at 
                FROM deployments 
                WHERE LOWER(username) = LOWER(?) 
                AND requested_at > ? 
                AND status = 'success'
                ORDER BY deployed_at DESC
                LIMIT 5
            ''', (username, seven_days_ago))
            
            recent_deploys = cursor.fetchall()
            if recent_deploys:
                deploy_list = ", ".join([f"${symbol}" for symbol, _ in recent_deploys])
                self.logger.info(f"@{username} has {actual_free_deploys_7d} deploys in 7d: {deploy_list}")
            
            # Update the count if different
            if actual_free_deploys_7d != free_deploys_7d:
                free_deploys_7d = actual_free_deploys_7d
                conn.execute('''
                    UPDATE deployment_cooldowns 
                    SET free_deploys_7d = ?, updated_at = ?
                    WHERE LOWER(username) = LOWER(?)
                ''', (free_deploys_7d, now, username))
            
            # Check if they deployed yesterday (for consecutive days tracking)
            yesterday = now.date() - timedelta(days=1)
            if last_free_deploy and last_free_deploy.date() == yesterday:
                # Consecutive day deployment
                consecutive_days += 1
            elif last_free_deploy and last_free_deploy.date() < yesterday:
                # Reset consecutive days
                consecutive_days = 0
            
            # Progressive cooldown logic - RELAXED FOR NEW SYSTEM
            # Free users get 3 per week, so only apply cooldown after exceeding that
            
            # Count deployments today
            today_start = datetime.combine(now.date(), datetime.min.time())
            cursor = conn.execute('''
                SELECT COUNT(*) FROM deployments 
                WHERE LOWER(username) = LOWER(?) 
                AND requested_at >= ? 
                AND status = 'success'
            ''', (username, today_start))
            
            deploys_today = cursor.fetchone()[0]
            
            # Debug logging
            self.logger.info(f"@{username} deployment check: {deploys_today} today, {actual_free_deploys_7d} this week")
            
            # ANTI-SPAM: 4+ deploys in ONE DAY = spam = 5 day cooldown
            if deploys_today >= 3:  # Already did 3 today, trying for 4th
                # Apply 5-day cooldown for daily spam
                cooldown_end = now + timedelta(days=5)
                conn.execute('''
                    UPDATE deployment_cooldowns 
                    SET cooldown_until = ?, consecutive_days = ?, updated_at = ?
                    WHERE LOWER(username) = LOWER(?)
                ''', (cooldown_end, consecutive_days, now, username))
                return False, "DAILY LIMIT: 3+ deploys in 24 hours. 5-day cooldown applied", 5
            
            # Weekly limit check (more severe for repeated abuse)
            elif free_deploys_7d >= 4:  # 4+ deploys in 7 days = exceeded weekly allowance
                # Apply 14-day cooldown for exceeding weekly limit
                cooldown_end = now + timedelta(days=14)
                conn.execute('''
                    UPDATE deployment_cooldowns 
                    SET cooldown_until = ?, consecutive_days = ?, updated_at = ?
                    WHERE LOWER(username) = LOWER(?)
                ''', (cooldown_end, consecutive_days, now, username))
                return False, "Weekly limit exceeded (4+ free/week). 14-day cooldown applied", 14
            
            # Update last deployment time
            conn.execute('''
                UPDATE deployment_cooldowns 
                SET consecutive_days = ?, updated_at = ?
                WHERE LOWER(username) = LOWER(?)
            ''', (consecutive_days, now, username))
            
            # More informative message about limits
            if deploys_today >= 2:
                return True, f"⚠️ Deployment allowed (2/3 today - ONE MORE and you'll get 5-day timeout!)", 0
            elif free_deploys_7d == 3:
                return True, f"Deployment allowed (3/3 free used this week - ONE MORE and you'll get 14-day timeout!)", 0
            elif free_deploys_7d == 2:
                return True, f"Deployment allowed (2/3 free used this week)", 0
            elif free_deploys_7d == 1:
                return True, f"Deployment allowed (1/3 free used this week)", 0
            else:
                return True, f"Deployment allowed (first free this week)", 0
    
    def update_cooldown_after_deployment(self, username: str, deployment_type: str) -> None:
        """Update cooldown tracking after a successful deployment"""
        now = datetime.now()
        
        with sqlite3.connect(self.db_path, detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES) as conn:
            if deployment_type == 'free':
                # Update progressive cooldown tracking
                conn.execute('''
                    UPDATE deployment_cooldowns 
                    SET free_deploys_7d = free_deploys_7d + 1,
                        last_free_deploy = ?,
                        total_free_deploys = total_free_deploys + 1,
                        updated_at = ?
                    WHERE LOWER(username) = LOWER(?)
                ''', (now, now, username))
                
                # Insert if doesn't exist
                conn.execute('''
                    INSERT OR IGNORE INTO deployment_cooldowns 
                    (username, free_deploys_7d, last_free_deploy, total_free_deploys, updated_at)
                    VALUES (?, 1, ?, 1, ?)
                ''', (username.lower(), now, now))
    
    def check_holder_weekly_deployments(self, username: str) -> int:
        """Check how many holder deployments user has made this week
        
        Returns:
            int: Number of holder deployments in the last 7 days
        """
        seven_days_ago = datetime.now() - timedelta(days=7)
        
        with sqlite3.connect(self.db_path, detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES) as conn:
            # Count holder deployments in last 7 days from deployments table
            cursor = conn.execute('''
                SELECT COUNT(*) FROM deployments 
                WHERE LOWER(username) = LOWER(?) 
                AND requested_at > ? 
                AND status = 'success'
                AND tx_hash IN (
                    SELECT tx_hash FROM deployments d
                    INNER JOIN users u ON LOWER(d.username) = LOWER(u.twitter_username)
                    WHERE u.is_holder = 1
                )
            ''', (username, seven_days_ago))
            
            holder_deploys_7d = cursor.fetchone()[0]
            
            # Also check from daily_limits for more accurate count
            cursor = conn.execute('''
                SELECT COALESCE(SUM(holder_deploys), 0) 
                FROM daily_limits 
                WHERE LOWER(username) = LOWER(?) AND date >= date(?)
            ''', (username, seven_days_ago))
            
            daily_limits_count = cursor.fetchone()[0]
            
            # Return the maximum of both counts (in case of discrepancy)
            return max(holder_deploys_7d, daily_limits_count)
    
    def update_daily_limits(self, username: str, deployment_type: str) -> None:
        """Update daily deployment limits"""
        today = datetime.now().date()
        
        with sqlite3.connect(self.db_path) as conn:
            # Ensure daily_limits row exists before updating
            conn.execute('''
                INSERT OR IGNORE INTO daily_limits (username, date, free_deploys, holder_deploys)
                VALUES (?, ?, 0, 0)
            ''', (username.lower(), today))
            
            if deployment_type == 'free':
                conn.execute('''
                    UPDATE daily_limits 
                    SET free_deploys = free_deploys + 1
                    WHERE username = ? AND date = ?
                ''', (username.lower(), today))
            elif deployment_type == 'holder':
                conn.execute('''
                    UPDATE daily_limits 
                    SET holder_deploys = holder_deploys + 1
                    WHERE username = ? AND date = ?
                ''', (username.lower(), today))
    
    def update_user_balance_after_deployment(self, username: str, gas_cost: float, fee: float, tx_hash: str, token_symbol: str) -> Optional[float]:
        """Update user balance after pay-per-deploy deployment
        
        Returns:
            New balance if successful, None if insufficient balance
        """
        total_deducted = gas_cost + fee
        
        with sqlite3.connect(self.db_path) as conn:
            # Use atomic balance update to prevent race conditions
            cursor = conn.execute('''
                UPDATE users 
                SET balance = balance - ?
                WHERE LOWER(twitter_username) = LOWER(?) AND balance >= ?
                RETURNING balance
            ''', (total_deducted, username, total_deducted))
            
            result = cursor.fetchone()
            if result is None:
                # Balance was insufficient (race condition)
                self.logger.error(f"Race condition: User @{username} balance insufficient after deployment")
                return None
            
            new_balance = result[0]
            
            # Track platform fee as separate balance source
            if fee > 0:
                conn.execute('''
                    INSERT INTO balance_sources (source_type, amount, tx_hash, description)
                    VALUES ('pay_per_deploy', ?, ?, ?)
                ''', (fee, tx_hash, f"Platform fee from @{username}'s ${token_symbol}"))
            
            return new_balance
    
    def get_successful_deploys_count(self) -> int:
        """Get total count of successful deployments"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT COUNT(*) FROM deployments WHERE status = 'success'"
            )
            return cursor.fetchone()[0]
    
    def record_free_deployment_gas_cost(self, gas_cost: float, tx_hash: str, description: str):
        """Record gas cost for free deployment (deduct from treasury, track as expense)"""
        with sqlite3.connect(self.db_path) as conn:
            # Deduct from fee detection treasury
            conn.execute('''
                INSERT INTO balance_sources (source_type, amount, tx_hash, description)
                VALUES ('fee_detection', ?, ?, ?)
            ''', (-gas_cost, tx_hash, f"Gas expense: {description}"))
            
            # Track as gas expense for transparency
            conn.execute('''
                INSERT INTO balance_sources (source_type, amount, tx_hash, description)
                VALUES ('gas_expenses', ?, ?, ?)
            ''', (gas_cost, tx_hash, description))
            
            conn.commit()
            self.logger.info(f"Recorded gas expense: {gas_cost:.4f} ETH for {description}")
    
    def get_daily_deployment_stats(self, username: str, date) -> Tuple[int, int]:
        """Get daily deployment stats for a user
        
        Returns:
            Tuple of (free_deploys_today, holder_deploys_today)
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute('''
                SELECT free_deploys, holder_deploys 
                FROM daily_limits 
                WHERE username = ? AND date = ?
            ''', (username.lower(), date))
            
            daily_stats = cursor.fetchone()
            if daily_stats:
                return daily_stats
            else:
                # Create record if it doesn't exist
                conn.execute('''
                    INSERT INTO daily_limits (username, date, free_deploys, holder_deploys)
                    VALUES (?, ?, 0, 0)
                ''', (username.lower(), date))
                return 0, 0
    
    def get_last_successful_deployment(self, username: str) -> Optional[Tuple[str, str]]:
        """Get the user's last successful deployment
        
        Returns:
            Tuple of (token_symbol, token_address) if found, None otherwise
        """
        with sqlite3.connect(self.db_path, detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES) as conn:
            cursor = conn.execute('''
                SELECT token_symbol, token_address 
                FROM deployments 
                WHERE LOWER(username) = LOWER(?) 
                AND status = 'success' 
                AND token_address IS NOT NULL
                ORDER BY deployed_at DESC 
                LIMIT 1
            ''', (username,))
            
            result = cursor.fetchone()
            return result if result else None
    
    def get_recent_deployments(self, username: str, days: int = 7) -> List[Tuple[str, datetime]]:
        """Get user's recent successful deployments
        
        Returns:
            List of (token_symbol, deployed_at) tuples
        """
        since = datetime.now() - timedelta(days=days)
        
        with sqlite3.connect(self.db_path, detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES) as conn:
            cursor = conn.execute('''
                SELECT token_symbol, deployed_at 
                FROM deployments 
                WHERE LOWER(username) = LOWER(?) 
                AND requested_at > ? 
                AND status = 'success' 
                AND token_address IS NOT NULL
                ORDER BY deployed_at DESC 
                LIMIT 10
            ''', (username, since))
            
            return cursor.fetchall()
    
    def get_recent_deployments_with_addresses(self, username: str, days: int = 7) -> List[Tuple[str, str, datetime]]:
        """Get user's recent successful deployments with addresses
        
        Returns:
            List of (token_symbol, token_address, deployed_at) tuples
        """
        since = datetime.now() - timedelta(days=days)
        
        with sqlite3.connect(self.db_path, detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES) as conn:
            cursor = conn.execute('''
                SELECT token_symbol, token_address, deployed_at 
                FROM deployments 
                WHERE LOWER(username) = LOWER(?) 
                AND requested_at > ? 
                AND status = 'success' 
                AND token_address IS NOT NULL
                ORDER BY deployed_at DESC 
                LIMIT 10
            ''', (username, since))
            
            return cursor.fetchall()
    
    def cleanup_expired_cooldowns(self) -> int:
        """Clean up expired cooldowns and fix any incorrect cooldown periods
        
        Returns:
            Number of cooldowns cleaned up
        """
        now = datetime.now()
        
        with sqlite3.connect(self.db_path) as conn:
            # First, clear any expired cooldowns
            cursor = conn.execute('''
                UPDATE deployment_cooldowns 
                SET cooldown_until = NULL, consecutive_days = 0
                WHERE cooldown_until < ?
            ''', (now,))
            
            expired_count = cursor.rowcount
            
            # Fix any cooldowns longer than 30 days (old system max)
            thirty_days_from_now = now + timedelta(days=30)
            cursor = conn.execute('''
                UPDATE deployment_cooldowns 
                SET cooldown_until = ?
                WHERE cooldown_until > ?
            ''', (thirty_days_from_now, thirty_days_from_now))
            
            fixed_count = cursor.rowcount
            
            if expired_count + fixed_count > 0:
                self.logger.info(f"Cleaned up {expired_count} expired cooldowns, fixed {fixed_count} excessive cooldowns")
            
            return expired_count + fixed_count
    
    # SECURITY: Twitter Account Verification Methods
    
    def generate_verification_code(self, username: str) -> str:
        """Generate a unique verification code for Twitter account verification"""
        import secrets
        import string
        
        # Generate 8-character alphanumeric code
        code = ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(8))
        
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                UPDATE users 
                SET verification_code = ?, twitter_verified = FALSE
                WHERE LOWER(twitter_username) = LOWER(?)
            ''', (code, username))
            
        return code
    
    def check_verification_status(self, username: str) -> Tuple[bool, Optional[str]]:
        """Check if Twitter account is verified and get verification code if needed
        
        Returns:
            Tuple of (is_verified, verification_code_if_unverified)
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT twitter_verified, verification_code FROM users WHERE LOWER(twitter_username) = LOWER(?)",
                (username,)
            )
            result = cursor.fetchone()
            
            if not result:
                return False, None
                
            is_verified, code = result
            return bool(is_verified), code if not is_verified else None
    
    def verify_twitter_account(self, username: str, code: str) -> bool:
        """Verify Twitter account with provided code
        
        Returns:
            True if verification successful, False otherwise
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute('''
                UPDATE users 
                SET twitter_verified = TRUE, verification_code = NULL
                WHERE LOWER(twitter_username) = LOWER(?) AND verification_code = ?
                RETURNING twitter_username
            ''', (username, code))
            
            result = cursor.fetchone()
            return result is not None
    
    def can_claim_fees(self, username: str) -> bool:
        """Check if user can claim fees (verified account)
        
        Returns:
            True if user can claim fees, False otherwise
        """
        is_verified, _ = self.check_verification_status(username)
        return is_verified
    
    def get_unverified_accounts_with_balance(self) -> List[Tuple[str, float]]:
        """Get list of unverified accounts that have deposited funds
        
        Returns:
            List of (username, balance) tuples for unverified accounts with balance > 0
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute('''
                SELECT twitter_username, balance 
                FROM users 
                WHERE twitter_verified = FALSE AND balance > 0
                ORDER BY balance DESC
            ''')
            return cursor.fetchall() 