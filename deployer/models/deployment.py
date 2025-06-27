"""
Deployment request model for token deployments
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class DeploymentRequest:
    """Represents a token deployment request"""
    tweet_id: str
    username: str
    token_name: str
    token_symbol: str
    requested_at: datetime
    tweet_url: str  # URL of the tweet that triggered deployment
    parent_tweet_id: Optional[str] = None  # If this is a reply
    image_url: Optional[str] = None  # Image from parent tweet
    deployed_at: Optional[datetime] = None
    tx_hash: Optional[str] = None
    token_address: Optional[str] = None
    status: str = "pending"  # pending, deploying, success, failed
    follower_count: int = 0  # Track follower count for rate limits
    salt: Optional[str] = None  # Pre-generated salt for CREATE2
    predicted_address: Optional[str] = None  # Predicted contract address 