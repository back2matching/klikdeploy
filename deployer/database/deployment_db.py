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
                    spam_attempts INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Add spam_attempts column if it doesn't exist (for existing databases)
            try:
                conn.execute('ALTER TABLE deployment_cooldowns ADD COLUMN spam_attempts INTEGER DEFAULT 0')
            except sqlite3.OperationalError:
                pass  # Column already exists
            
            # NEW: User fee capture settings table
            conn.execute('''
                CREATE TABLE IF NOT EXISTS user_fee_settings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE,
                    fee_capture_enabled BOOLEAN DEFAULT FALSE,
                    last_modified TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (username) REFERENCES users(twitter_username)
                )
            ''')
            
            # NEW: Individual deployment fee tracking
            conn.execute('''
                CREATE TABLE IF NOT EXISTS deployment_fees (
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
                    status TEXT DEFAULT 'pending', -- 'pending', 'claimable', 'claimed'
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (deployment_id) REFERENCES deployments(id),
                    FOREIGN KEY (username) REFERENCES users(twitter_username)
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
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    "SELECT COALESCE(SUM(balance), 0) FROM users WHERE balance > 0"
                )
                total = cursor.fetchone()[0]
                return float(total)
        except Exception as e:
            self.logger.error(f"Error getting total user deposits: {e}")
            return 0.0
    
    def get_user_balance(self, username: str) -> float:
        """Get user's ETH balance from database"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    "SELECT balance FROM users WHERE LOWER(twitter_username) = LOWER(?)",
                    (username,)
                )
                result = cursor.fetchone()
                return result[0] if result else 0.0
        except Exception as e:
            self.logger.error(f"Error getting user balance for {username}: {e}")
            return 0.0
    
    def get_balance_by_source(self, source_type: str) -> float:
        """Get total balance from a specific source type"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    "SELECT COALESCE(SUM(amount), 0) FROM balance_sources WHERE source_type = ?",
                    (source_type,)
                )
                return float(cursor.fetchone()[0])
        except Exception as e:
            self.logger.error(f"Error getting balance by source {source_type}: {e}")
            return 0.0
    
    def check_holder_status(self, username: str) -> Tuple[bool, Optional[str]]:
        """Check if user is a verified holder
        
        Returns:
            Tuple of (is_holder, eth_address)
        """
        try:
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
        except Exception as e:
            self.logger.error(f"Error checking holder status for {username}: {e}")
            # Return safe defaults to prevent NoneType unpacking error
            return False, None
    
    def update_holder_status(self, username: str, is_holder: bool, balance: float) -> None:
        """Update user's holder status"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "UPDATE users SET is_holder = ?, holder_balance = ? WHERE LOWER(twitter_username) = LOWER(?)",
                (is_holder, balance, username)
            )
    
    def get_deployment_stats(self) -> Dict:
        """Get deployment statistics for the last 24 hours"""
        try:
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
                'total_requests_24h': stats[0] if stats else 0,
                'successful_deploys_24h': stats[1] if stats else 0,
                'unique_users_24h': stats[2] if stats else 0,
                'tokens_with_images_24h': stats[3] if stats else 0
            }
        except Exception as e:
            self.logger.error(f"Error getting deployment stats: {e}")
            # Return safe defaults
            return {
                'total_requests_24h': 0,
                'successful_deploys_24h': 0,
                'unique_users_24h': 0,
                'tokens_with_images_24h': 0
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
        try:
            now = datetime.now()
            seven_days_ago = now - timedelta(days=7)
            
            with sqlite3.connect(self.db_path, detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES) as conn:
                # Get or create cooldown record
                cursor = conn.execute('''
                    SELECT free_deploys_7d, last_free_deploy, cooldown_until, consecutive_days, total_free_deploys, spam_attempts
                    FROM deployment_cooldowns 
                    WHERE LOWER(username) = LOWER(?)
                ''', (username,))
                
                cooldown_data = cursor.fetchone()
                
                if not cooldown_data:
                    # First time user
                    conn.execute('''
                        INSERT INTO deployment_cooldowns (username, free_deploys_7d, last_free_deploy, spam_attempts, updated_at)
                        VALUES (?, 0, ?, 0, ?)
                    ''', (username.lower(), now, now))
                    return True, "First deployment allowed", 0
                
                free_deploys_7d, last_free_deploy, cooldown_until, consecutive_days, total_free_deploys, spam_attempts = cooldown_data
                
                # Check if currently in cooldown
                if cooldown_until and cooldown_until > now:
                    days_left = (cooldown_until - now).days + 1
                    
                    # NEW ESCALATION SYSTEM: Track spam attempts and escalate at 10
                    spam_attempts += 1
                    
                    if spam_attempts >= 10:
                        # 10th spam attempt = 30-day ban
                        escalated_end = now + timedelta(days=30)
                        conn.execute('''
                            UPDATE deployment_cooldowns 
                            SET cooldown_until = ?, spam_attempts = ?, updated_at = ?
                            WHERE LOWER(username) = LOWER(?)
                        ''', (escalated_end, spam_attempts, now, username))
                        return False, f"SPAM BAN: 10 attempts during cooldown. 30-day ban applied", 30
                    else:
                        # Update spam attempt count and show warning WITH DEPLOYMENTS
                        conn.execute('''
                            UPDATE deployment_cooldowns 
                            SET spam_attempts = ?, updated_at = ?
                            WHERE LOWER(username) = LOWER(?)
                        ''', (spam_attempts, now, username))
                        
                        # Get their deployments to show in the warning message  
                        cursor = conn.execute('''
                            SELECT token_symbol, token_address 
                            FROM deployments 
                            WHERE LOWER(username) = LOWER(?) 
                            AND requested_at > ? 
                            AND status = 'success' 
                            AND token_address IS NOT NULL
                            ORDER BY deployed_at DESC 
                            LIMIT 3
                        ''', (username, seven_days_ago))
                        
                        recent_deployments = cursor.fetchall()
                        
                        # Show escalating warnings with deployments
                        attempts_left = 10 - spam_attempts
                        reset_date = cooldown_until.strftime('%m/%d')
                        ban_date = (now + timedelta(days=30)).strftime('%m/%d')
                        
                        if recent_deployments:
                            deploy_list = []
                            for symbol, address in recent_deployments:
                                deploy_list.append(f"${symbol}: https://dexscreener.com/ethereum/{address}")
                            deployments_text = "\n".join(deploy_list)
                            
                            return False, f"Weekly limit exceeded! ({spam_attempts}/10 warnings)\n\n{deployments_text}\n\nReset: {reset_date} | {attempts_left} more = 30-day ban ({ban_date})", days_left
                        else:
                            return False, f"Weekly limit exceeded! ({spam_attempts}/10 warnings). Reset: {reset_date}. {attempts_left} more = 30-day ban ({ban_date})", days_left
                
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
                
                # SERIOUS SPAM: 5+ attempts in ONE DAY = immediate 30-day ban  
                if deploys_today >= 5:  # Already did 5+ today = serious spam
                    # Apply 30-day ban for serious spam
                    cooldown_end = now + timedelta(days=30)
                    conn.execute('''
                        UPDATE deployment_cooldowns 
                        SET cooldown_until = ?, spam_attempts = 0, consecutive_days = ?, updated_at = ?
                        WHERE LOWER(username) = LOWER(?)
                    ''', (cooldown_end, consecutive_days, now, username))
                    return False, "SPAM BAN: 5+ attempts in 24 hours. 30-day ban applied", 30
                
                # Weekly limit check: 4th deployment attempt gets 7-day cooldown + show deployments
                elif free_deploys_7d >= 3:  # Already did 3 this week, trying for 4th
                    # Apply 7-day cooldown for exceeding weekly allowance
                    cooldown_end = now + timedelta(days=7)
                    conn.execute('''
                        UPDATE deployment_cooldowns 
                        SET cooldown_until = ?, spam_attempts = 0, consecutive_days = ?, updated_at = ?
                        WHERE LOWER(username) = LOWER(?)
                    ''', (cooldown_end, consecutive_days, now, username))
                    
                    # Get their deployments to show in the message
                    cursor = conn.execute('''
                        SELECT token_symbol, token_address 
                        FROM deployments 
                        WHERE LOWER(username) = LOWER(?) 
                        AND requested_at > ? 
                        AND status = 'success' 
                        AND token_address IS NOT NULL
                        ORDER BY deployed_at DESC 
                        LIMIT 3
                    ''', (username, seven_days_ago))
                    
                    recent_deployments = cursor.fetchall()
                    if recent_deployments:
                        deploy_list = []
                        for symbol, address in recent_deployments:
                            deploy_list.append(f"${symbol}: https://dexscreener.com/ethereum/{address}")
                        deployments_text = "\n".join(deploy_list)
                        return False, f"Weekly limit reached! (3/3 used)\n\n{deployments_text}\n\nWait 7 days OR deposit: t.me/DeployOnKlik", 7
                    else:
                        return False, "Weekly limit: Used all 3 free deploys. 7-day cooldown applied", 7
                
                # Update last deployment time
                conn.execute('''
                    UPDATE deployment_cooldowns 
                    SET consecutive_days = ?, updated_at = ?
                    WHERE LOWER(username) = LOWER(?)
                ''', (consecutive_days, now, username))
                
                # More informative message about limits
                if deploys_today >= 4:
                    return True, f"⚠️ Deployment allowed (4 today - ONE MORE and you'll get 30-day ban!)", 0
                elif free_deploys_7d == 2:
                    return True, f"⚠️ Deployment allowed (2/3 free used this week - ONE MORE and next attempt gets 7-day cooldown!)", 0
                elif free_deploys_7d == 1:
                    return True, f"Deployment allowed (1/3 free used this week)", 0
                else:
                    return True, f"Deployment allowed (first free this week)", 0
        
        except Exception as e:
            self.logger.error(f"Error checking progressive cooldown for {username}: {e}")
            # Return safe defaults to prevent NoneType unpacking error
            # Allow deployment but log the error
            return True, "Error checking cooldown - allowing deployment", 0
    
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
        try:
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
                
        except Exception as e:
            self.logger.error(f"Error checking holder weekly deployments for {username}: {e}")
            # Return safe default to prevent errors
            return 0
    
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
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    "SELECT COUNT(*) FROM deployments WHERE status = 'success'"
                )
                return cursor.fetchone()[0]
        except Exception as e:
            self.logger.error(f"Error getting successful deploys count: {e}")
            return 0
    
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
        try:
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
                    conn.commit()
                    return (0, 0)
        except Exception as e:
            self.logger.error(f"Error getting daily deployment stats for {username}: {e}")
            # Return safe defaults to prevent NoneType unpacking error
            return (0, 0)
    
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
    
    # SELF-CLAIM FEES FUNCTIONALITY
    
    def set_user_fee_capture_preference(self, username: str, enabled: bool) -> bool:
        """Set user's fee capture preference
        
        Args:
            username: Twitter username
            enabled: True to enable fee capture, False for community split
            
        Returns:
            True if successful, False otherwise
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                # Ensure user exists and is verified
                cursor = conn.execute(
                    "SELECT twitter_verified FROM users WHERE LOWER(twitter_username) = LOWER(?)",
                    (username,)
                )
                user = cursor.fetchone()
                
                if not user or not user[0]:
                    # User doesn't exist or not verified
                    return False
                
                # Insert or update preference
                conn.execute('''
                    INSERT OR REPLACE INTO user_fee_settings (username, fee_capture_enabled, last_modified)
                    VALUES (?, ?, CURRENT_TIMESTAMP)
                ''', (username.lower(), enabled))
                
                conn.commit()
                return True
                
        except Exception as e:
            self.logger.error(f"Error setting fee capture preference for {username}: {e}")
            return False
    
    def get_user_fee_capture_preference(self, username: str) -> bool:
        """Get user's fee capture preference
        
        Args:
            username: Twitter username
            
        Returns:
            True if user has fee capture enabled, False for community split
        """
        with sqlite3.connect(self.db_path) as conn:
            # Check if user is verified first
            cursor = conn.execute(
                "SELECT twitter_verified FROM users WHERE LOWER(twitter_username) = LOWER(?)",
                (username,)
            )
            user = cursor.fetchone()
            
            if not user or not user[0]:
                # Unverified users always get community split
                return False
            
            # Get fee capture setting
            cursor = conn.execute(
                "SELECT fee_capture_enabled FROM user_fee_settings WHERE LOWER(username) = LOWER(?)",
                (username,)
            )
            result = cursor.fetchone()
            
            # Default to False (community split) if no setting found
            return result[0] if result else False
    
    def record_deployment_fee_potential(self, deployment_id: int, token_address: str, 
                                       token_symbol: str, username: str) -> None:
        """Record a deployment that can potentially generate fees
        
        Args:
            deployment_id: ID from deployments table
            token_address: Token contract address
            token_symbol: Token symbol
            username: Twitter username who deployed
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute('''
                    INSERT INTO deployment_fees 
                    (deployment_id, token_address, token_symbol, username, status)
                    VALUES (?, ?, ?, ?, 'pending')
                ''', (deployment_id, token_address, token_symbol, username.lower()))
                conn.commit()
                
        except Exception as e:
            self.logger.error(f"Error recording deployment fee potential: {e}")
    
    def process_fee_claim_for_user(self, token_address: str, total_fee_amount: float, 
                                  claim_tx_hash: str) -> Dict[str, float]:
        """Process fee claim and determine splits based on user preferences
        
        Args:
            token_address: Token that generated fees
            total_fee_amount: Total ETH amount claimed
            claim_tx_hash: Transaction hash of the fee claim
            
        Returns:
            Dict with fee distribution: {
                'user_claims': float,      # Total to be claimed by users
                'source_buyback': float,   # For source token buyback  
                'dok_buyback': float,      # For DOK buyback
                'treasury': float          # For treasury
            }
        """
        with sqlite3.connect(self.db_path) as conn:
            # Find all deployments for this token
            cursor = conn.execute('''
                SELECT df.id, df.username, df.deployment_id
                FROM deployment_fees df
                INNER JOIN deployments d ON df.deployment_id = d.id
                WHERE LOWER(df.token_address) = LOWER(?) AND df.status = 'pending'
            ''', (token_address,))
            
            deployments = cursor.fetchall()
            
            if not deployments:
                # No deployments found, use community split
                return {
                    'user_claims': 0.0,
                    'source_buyback': total_fee_amount * 0.25,
                    'dok_buyback': total_fee_amount * 0.25,
                    'treasury': total_fee_amount * 0.5
                }
            
            # Calculate splits
            total_user_claims = 0.0
            
            for fee_id, username, deployment_id in deployments:
                # Check if user wants fee capture
                wants_fee_capture = self.get_user_fee_capture_preference(username)
                
                if wants_fee_capture:
                    # User gets 50% of their deployment's fees (what would normally go to treasury)
                    user_claimable = total_fee_amount * 0.5 / len(deployments)
                    total_user_claims += user_claimable
                    
                    # Update deployment_fees record
                    conn.execute('''
                        UPDATE deployment_fees 
                        SET total_fees_generated = ?, 
                            user_claimable_amount = ?, 
                            status = 'claimable'
                        WHERE id = ?
                    ''', (total_fee_amount, user_claimable, fee_id))
            
            # Calculate remaining splits
            remaining_amount = total_fee_amount - total_user_claims
            source_buyback = remaining_amount * 0.5  # 25% of original becomes 50% of remaining
            dok_buyback = remaining_amount * 0.5     # 25% of original becomes 50% of remaining
            treasury = 0.0                           # What's left goes to users
            
            conn.commit()
            
            return {
                'user_claims': total_user_claims,
                'source_buyback': source_buyback,
                'dok_buyback': dok_buyback,
                'treasury': treasury
            }
    
    def get_user_claimable_fees(self, username: str) -> List[Dict]:
        """Get all claimable fees for a user
        
        Args:
            username: Twitter username
            
        Returns:
            List of claimable fee records
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute('''
                SELECT df.id, df.token_symbol, df.token_address, df.user_claimable_amount,
                       df.created_at, d.deployed_at
                FROM deployment_fees df
                INNER JOIN deployments d ON df.deployment_id = d.id
                WHERE LOWER(df.username) = LOWER(?) AND df.status = 'claimable'
                ORDER BY df.created_at DESC
            ''', (username,))
            
            results = []
            for row in cursor.fetchall():
                results.append({
                    'id': row[0],
                    'token_symbol': row[1],
                    'token_address': row[2],
                    'claimable_amount': row[3],
                    'fee_generated_at': row[4],
                    'token_deployed_at': row[5]
                })
            
            return results
    
    def claim_user_fees(self, username: str, fee_ids: List[int], claim_tx_hash: str) -> float:
        """Process user fee claim
        
        Args:
            username: Twitter username
            fee_ids: List of fee IDs to claim
            claim_tx_hash: Transaction hash of the claim
            
        Returns:
            Total amount claimed
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                total_claimed = 0.0
                
                for fee_id in fee_ids:
                    # Verify ownership and claimable status
                    cursor = conn.execute('''
                        SELECT user_claimable_amount 
                        FROM deployment_fees 
                        WHERE id = ? AND LOWER(username) = LOWER(?) AND status = 'claimable'
                    ''', (fee_id, username))
                    
                    result = cursor.fetchone()
                    if result:
                        amount = result[0]
                        total_claimed += amount
                        
                        # Mark as claimed
                        conn.execute('''
                            UPDATE deployment_fees 
                            SET claimed_amount = user_claimable_amount,
                                claim_tx_hash = ?,
                                claimed_at = CURRENT_TIMESTAMP,
                                status = 'claimed'
                            WHERE id = ?
                        ''', (claim_tx_hash, fee_id))
                
                conn.commit()
                return total_claimed
                
        except Exception as e:
            self.logger.error(f"Error claiming fees for {username}: {e}")
            return 0.0
    
    def get_user_fee_stats(self, username: str) -> Dict:
        """Get user's fee statistics
        
        Args:
            username: Twitter username
            
        Returns:
            Dict with fee stats
        """
        with sqlite3.connect(self.db_path) as conn:
            # Get claimable amount
            cursor = conn.execute('''
                SELECT COALESCE(SUM(user_claimable_amount), 0)
                FROM deployment_fees 
                WHERE LOWER(username) = LOWER(?) AND status = 'claimable'
            ''', (username,))
            claimable = cursor.fetchone()[0]
            
            # Get total claimed
            cursor = conn.execute('''
                SELECT COALESCE(SUM(claimed_amount), 0)
                FROM deployment_fees 
                WHERE LOWER(username) = LOWER(?) AND status = 'claimed'
            ''', (username,))
            total_claimed = cursor.fetchone()[0]
            
            # Get number of deployments with fees
            cursor = conn.execute('''
                SELECT COUNT(DISTINCT token_address)
                FROM deployment_fees 
                WHERE LOWER(username) = LOWER(?) AND total_fees_generated > 0
            ''', (username,))
            tokens_with_fees = cursor.fetchone()[0]
            
            return {
                'claimable_amount': claimable,
                'total_claimed': total_claimed,
                'tokens_with_fees': tokens_with_fees
            } 