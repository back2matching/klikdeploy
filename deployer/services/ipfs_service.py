"""
IPFS service for uploading images and metadata
"""

import os
import logging
from typing import Optional, Dict
from io import BytesIO
import aiohttp
import requests


class IPFSService:
    """Service for handling IPFS uploads"""
    
    def __init__(self):
        """Initialize IPFS service with API keys"""
        self.pinata_api_key = os.getenv('PINATA_API_KEY')
        self.pinata_secret_key = os.getenv('PINATA_SECRET_KEY')
        self.web3_storage_token = os.getenv('WEB3_STORAGE_TOKEN')
        self.logger = logging.getLogger('klik_deployer')
    
    async def upload_image_to_ipfs(self, image_url: str) -> Optional[str]:
        """Download image from URL and upload to IPFS"""
        try:
            # Download the image
            async with aiohttp.ClientSession() as session:
                async with session.get(image_url) as response:
                    if response.status != 200:
                        self.logger.error(f"Failed to download image: {response.status}")
                        return None
                    
                    image_data = await response.read()
                    content_type = response.headers.get('Content-Type', 'image/jpeg')
            
            # Upload to IPFS
            if self.pinata_api_key and self.pinata_secret_key:
                # Use Pinata
                url = "https://api.pinata.cloud/pinning/pinFileToIPFS"
                headers = {
                    "pinata_api_key": self.pinata_api_key,
                    "pinata_secret_api_key": self.pinata_secret_key
                }
                
                # Prepare multipart form data
                files = {
                    'file': ('image', BytesIO(image_data), content_type)
                }
                
                response = requests.post(url, files=files, headers=headers)
                if response.status_code == 200:
                    ipfs_hash = response.json()['IpfsHash']
                    self.logger.info(f"Image uploaded to IPFS: {ipfs_hash}")
                    return ipfs_hash
                else:
                    self.logger.error(f"Pinata upload failed: {response.text}")
            
            elif self.web3_storage_token:
                # Use web3.storage
                url = "https://api.web3.storage/upload"
                headers = {
                    "Authorization": f"Bearer {self.web3_storage_token}",
                    "X-NAME": "token-image"
                }
                
                response = requests.post(url, data=image_data, headers=headers)
                if response.status_code == 200:
                    cid = response.json()['cid']
                    self.logger.info(f"Image uploaded to IPFS: {cid}")
                    return cid
                else:
                    self.logger.error(f"Web3.storage upload failed: {response.text}")
            
            self.logger.warning("No IPFS service configured for image upload")
            return None
            
        except Exception as e:
            self.logger.error(f"Error uploading image to IPFS: {e}")
            return None
    
    def upload_metadata_to_ipfs(self, metadata: Dict) -> Optional[str]:
        """Upload metadata JSON to IPFS"""
        try:
            if self.pinata_api_key and self.pinata_secret_key:
                url = "https://api.pinata.cloud/pinning/pinJSONToIPFS"
                headers = {
                    "pinata_api_key": self.pinata_api_key,
                    "pinata_secret_api_key": self.pinata_secret_key
                }
                
                response = requests.post(url, json=metadata, headers=headers)
                if response.status_code == 200:
                    return response.json()['IpfsHash']
            
            elif self.web3_storage_token:
                url = "https://api.web3.storage/upload"
                headers = {
                    "Authorization": f"Bearer {self.web3_storage_token}",
                    "Content-Type": "application/json"
                }
                
                response = requests.post(url, json=metadata, headers=headers)
                if response.status_code == 200:
                    return response.json()['cid']
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error uploading metadata to IPFS: {e}")
            return None 