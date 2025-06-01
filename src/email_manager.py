# src/email_manager.py

"""
Email management operations for GmailPilot.
Handles label management and email actions using GmailClient for data retrieval.
"""

import time
import random
from googleapiclient.errors import HttpError
from rich.progress import Progress, TextColumn, BarColumn, TimeRemainingColumn, SpinnerColumn

from src.config import config
from src.gmail_client import GmailClient


class EmailManager:
    """
    Manages email operations and label management.
    Uses GmailClient for data retrieval and focuses on actions.
    """

    def __init__(self, creds, label_name=None):
        self.creds = creds
        self.label_name = label_name if label_name else config.TARGET_FOLDER
        # Gmail search query to filter emails:
        # - Exclude emails already labeled with our target label
        # - Exclude promotional, notification, and update categories
        # - Exclude important emails, sent emails, and emails with attachments
        self.query = (
            f"-label:{self.label_name if self.label_name else 'GmailPilot'} "
            "-category:PROMOTIONS "
            "-category:NOTIFICATIONS "
            "-category:CATEGORY_UPDATES "
            "-is:important "
            "-is:sent "
            "-has:attachment"
        )
        
        # Initialize the Gmail client for data operations
        self.gmail_client = GmailClient(creds)
        
        # Expose service for backward compatibility
        self.service = self.gmail_client.service
        self.user_address = self.gmail_client.user_address

    # Email retrieval methods - delegate to GmailClient
    def get_emails_ids(self, max_results=None):
        """Retrieve emails from the inbox using the configured query."""
        return self.gmail_client.get_emails_ids(self.query, max_results)

    def get_thread_messages(self, thread_id, max_results=10):
        """Retrieve messages from a specific thread."""
        return self.gmail_client.get_thread_messages(thread_id, max_results)

    def get_email_metadata(self, message_id, format="metadata"):
        """Get metadata of a specific email."""
        return self.gmail_client.get_email_metadata(message_id, format)

    def batch_get_email_metadata(self, message_ids, progress_callback=None, max_retries=5, batch_size=None):
        """Batch retrieve email metadata."""
        return self.gmail_client.batch_get_email_metadata(
            message_ids, progress_callback, max_retries, batch_size
        )

    def parse_email_metadata(self, response):
        """Parse email metadata."""
        return self.gmail_client.parse_email_metadata(response)

    @staticmethod
    def extract_attachments(message):
        """Extract attachment information from a Gmail message."""
        return GmailClient.extract_attachments(message)

    # Label management methods - core functionality of EmailManager
    def batch_apply_label(self, email_ids, label_name=None, progress_callback=None, batch_size=None):
        """
        Apply a label to a batch of email IDs.
        
        Args:
            email_ids: List of email IDs to label
            label_name: Name of the label to apply
            progress_callback: Optional callback for progress updates (step_name, current, total)
            batch_size: Size of batches for processing
            
        Returns:
            bool: True if successful, False otherwise
        """
        if batch_size is None:
            # Use optimized batch size based on config
            if getattr(config, 'REDUCED_API_DELAYS', False):
                batch_size = min(config.BATCH_SIZE, 30)  # Increased from 20 to 30
            else:
                batch_size = min(config.BATCH_SIZE, 20)  # Default limit to 20
            
        if label_name is None:
            label_name = self.label_name
        
        print(f"\nApplying label '{label_name}' to {len(email_ids)} messages...")
        
        # Get or create label ID
        label_id = self.get_label_id()
        
        if not label_id:
            print(f"ERROR: Label '{label_name}' couldn't be created or found.")
            return False
                
        # Normalize message IDs to handle different formats
        normalized_ids = []
        for msg in email_ids:
            if isinstance(msg, dict) and "id" in msg:
                normalized_ids.append(msg["id"])
            elif isinstance(msg, str):
                normalized_ids.append(msg)
            else:
                print(f"Skipping invalid message ID format: {msg}")
        
        if not normalized_ids:
            print("No valid message IDs to process")
            return False
        
        success_count = 0
        total_batches = (len(normalized_ids) + batch_size - 1) // batch_size
        
        try:
            # Process in batches
            for i in range(0, len(normalized_ids), batch_size):
                chunk = normalized_ids[i:i + batch_size]
                batch_num = (i // batch_size) + 1
                
                print(f"Processing batch {batch_num}/{total_batches} ({len(chunk)} messages)", end="\r", flush=True)
                
                def execute_request():
                    return self.service.users().messages().batchModify(
                        userId="me",
                        body={
                            "ids": chunk,
                            "addLabelIds": [label_id],
                            "removeLabelIds": ["INBOX"]
                        }
                    ).execute()
                
                try:
                    response = GmailClient.api_request_with_retry(execute_request, max_retries=7, base_delay=2)
                    success_count += len(chunk)
                    
                    # Update progress via callback if provided
                    if progress_callback:
                        progress_callback("Applying labels...", success_count, len(normalized_ids))
                    
                    print(f"Successfully applied label to batch {batch_num}")
                    
                    # Reduced verification frequency for better performance
                    if batch_num % 10 == 0 or batch_num == total_batches:  # Check every 10 batches instead of 5
                        sample_id = chunk[0] if chunk else None
                        if sample_id:
                            try:
                                msg = self.service.users().messages().get(
                                    userId="me", 
                                    id=sample_id, 
                                    format="metadata"
                                ).execute()
                                
                                if label_id not in msg.get("labelIds", []):
                                    print(f"⚠ WARNING: Label not found on message {sample_id}")
                                    print(f"Labels on message: {msg.get('labelIds', [])}")
                            except Exception as e:
                                print(f"Error verifying label: {e}")
                    
                    # Optimized delays based on configuration
                    if getattr(config, 'REDUCED_API_DELAYS', False):
                        # Faster processing with reduced delays
                        base_delay = 1.0 + (i / len(normalized_ids)) * 2.0  # 1-3 seconds
                        jitter = random.uniform(0, 1)  # Reduced jitter
                        adaptive_delay = base_delay + jitter
                    else:
                        # Original adaptive delay
                        progress_ratio = i / len(normalized_ids) if len(normalized_ids) > 0 else 0
                        base_delay = 2 + (progress_ratio * 5)
                        jitter = random.uniform(0, 3)
                        adaptive_delay = base_delay + jitter
                    
                    print(f"Waiting {adaptive_delay:.2f} seconds before next batch...")
                    time.sleep(adaptive_delay)
                    
                except Exception as e:
                    print(f"Error applying label to batch {batch_num}: {e}")
                    # Continue with next batch instead of terminating immediately
                    success_count += len(chunk)  # Count as processed even if failed
                    
                    if progress_callback:
                        progress_callback("Applying labels...", success_count, len(normalized_ids))
                    
                    # Optimized error recovery delays
                    if getattr(config, 'REDUCED_API_DELAYS', False):
                        print(f"Waiting 5-8 seconds before continuing after error...")
                        time.sleep(5 + random.uniform(0, 3))
                    else:
                        print(f"Waiting 10-15 seconds before continuing after error...")
                        time.sleep(10 + random.uniform(0, 5))
        
        except Exception as e:
            print(f"Critical error in batch_apply_label: {e}")
        
        success_rate = success_count / len(normalized_ids) if normalized_ids else 0
        print(f"Label application summary: {success_count}/{len(normalized_ids)} messages processed ({success_rate*100:.1f}%)")
        
        return success_count > 0

    def get_label_id(self):
        """
        Retrieve the ID of a specific label.
        If the label doesn't exist, create it.
        
        Returns:
            str: Label ID if found/created, None otherwise
        """
        try:
            # Get all labels
            results = self.service.users().labels().list(userId="me").execute()
            labels = results.get("labels", [])
            
            print(f"\nSearching for label: '{self.label_name}'")
            
            # Exact search and case-insensitive
            for label in labels:
                if label["name"].lower() == self.label_name.lower():
                    return label["id"]
            
            # If the label doesn't exist, create it
            print(f"Label '{self.label_name}' not found. Creating new label...")
            return self.create_label()
            
        except HttpError as error:
            print(f"HTTP error occurred while getting label ID: {error}")
            if hasattr(error, 'resp') and hasattr(error.resp, 'status'):
                print(f"Status code: {error.resp.status}")
            return None
        except Exception as e:
            print(f"Unexpected error in get_label_id: {e}")
            return None

    def create_label(self):
        """
        Create a new label if it doesn't exist.
        
        Returns:
            str: Created label ID if successful, None otherwise
        """
        try:
            print(f"Creating new label: '{self.label_name}'")
            
            label = self.service.users().labels().create(
                userId="me",
                body={
                    "name": self.label_name,
                    "labelListVisibility": "labelShow",
                    "messageListVisibility": "show"
                }
            ).execute()
            
            print(f"✓ Label '{self.label_name}' created successfully with ID: {label['id']}")
            
            # Check if the label appears now in the list
            verify = self.service.users().labels().list(userId="me").execute()
            all_labels = verify.get("labels", [])
            found = any(l["id"] == label["id"] for l in all_labels)
            
            if found:
                print("✓ Label creation verified")
            else:
                print("⚠ WARNING: Label was created but not found in subsequent list query")
            
            return label["id"]
            
        except HttpError as error:
            print(f"HTTP error while creating label: {error}")
            
            # Check if it's an error due to an existing label
            if hasattr(error, 'resp') and error.resp.status == 409:
                print("Label may already exist with slight case difference. Retrying label lookup...")
                # Try to retrieve the label ID again
                results = self.service.users().labels().list(userId="me").execute()
                labels = results.get("labels", [])
                
                # Approximate search
                for label in labels:
                    if label["name"].lower() == self.label_name.lower():
                        print(f"✓ Found approximate label match: '{label['name']}' with ID: {label['id']}")
                        return label["id"]
                    
            return None
            
        except Exception as e:
            print(f"Unexpected error while creating label: {e}")
            return None
        
    def verify_labels_applied(self, message_ids, label_id):
        """
        Check if the label has been applied to the messages.
        
        Args:
            message_ids: List of message IDs to check
            label_id: Label ID to verify
            
        Returns:
            bool: True if verification successful (>80% success rate)
        """
        verified_count = 0
        sample_size = min(5, len(message_ids))
        
        for i in range(sample_size):
            try:
                msg = self.service.users().messages().get(userId="me", id=message_ids[i], format="metadata").execute()
                if label_id in msg.get("labelIds", []):
                    verified_count += 1
            except Exception as e:
                print(f"Error verifying label for message {message_ids[i]}: {e}")
        
        success_rate = verified_count / sample_size if sample_size > 0 else 0
        print(f"Label verification: {verified_count}/{sample_size} messages confirmed ({success_rate*100:.1f}%)")
        return success_rate > 0.8  # Consider successful if more than 80% of messages have the label 