# src/gmail_client.py

"""
Gmail API client for email retrieval and metadata operations.
Handles communication with Gmail API and data fetching.
"""

import time
import random
import os
import json
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from src.config import config
from src.utils import Utils


class GmailClient:
    """
    Handles Gmail API communication and email data retrieval.
    Focused on reading emails and extracting metadata.
    """

    BATCH_SIZE = config.BATCH_SIZE
    MAX_RESULTS = config.MAX_RESULTS

    def __init__(self, creds):
        self.creds = creds
        self.service = build("gmail", "v1", credentials=creds)
        self.user_address = self.get_user_address()

    def get_user_address(self):
        """Get the user's email address."""
        return self.service.users().getProfile(userId="me").execute()["emailAddress"]

    def get_emails_ids(self, query, max_results=None):
        """
        Retrieve email IDs based on a query.
        
        Args:
            query (str): Gmail search query
            max_results (int): Maximum number of results
            
        Returns:
            list: List of message IDs
        """
        if max_results is None:
            max_results = self.MAX_RESULTS
            
        try:
            results = self.service.users().messages().list(
                userId="me", 
                maxResults=max_results,
                q=query,
            ).execute()
            return results.get("messages", [])
        except HttpError as error:
            print(f"An HTTP error occurred while getting emails: {error}")
            return []

    def get_thread_messages(self, thread_id, max_results=10):
        """
        Retrieves messages from a specific thread.
        
        Args:
            thread_id (str): Gmail thread ID to retrieve
            max_results (int): Maximum number of messages to retrieve
            
        Returns:
            list: List of thread messages with their metadata
        """
        try:
            # Get the complete thread
            thread = self.service.users().threads().get(
                userId="me",
                id=thread_id,
                format="metadata"
            ).execute()
            
            if not thread or "messages" not in thread:
                return []
                
            # Limit the number of messages processed
            messages = thread.get("messages", [])[:max_results]
            
            # Extract important information from each message
            result = []
            for message in messages:
                msg_data = {
                    "id": message.get("id", ""),
                    "threadId": thread_id,
                    "labelIds": message.get("labelIds", []),
                    "internalDate": message.get("internalDate", ""),
                    "sender": "",
                    "to": "",
                    "subject": ""
                }
                
                # Extract headers
                headers = message.get("payload", {}).get("headers", [])
                for header in headers:
                    header_name = header.get("name", "").lower()
                    header_value = header.get("value", "")
                    
                    if header_name == "from":
                        msg_data["sender"] = header_value
                    elif header_name == "to":
                        msg_data["to"] = header_value
                    elif header_name == "subject":
                        msg_data["subject"] = header_value
                        
                result.append(msg_data)
                
            return result
            
        except HttpError as error:
            print(f"HTTP error occurred while getting thread messages: {error}")
            return []
        except Exception as e:
            print(f"Unexpected error in get_thread_messages: {e}")
            return []

    def get_email_metadata(self, message_id, format="metadata"):
        """
        Get the metadata of a specific email.
        
        Args:
            message_id (str): Email message ID
            format (str): Gmail API format parameter
            
        Returns:
            dict: Email metadata
        """
        try:
            response = self.service.users().messages().get(
                userId="me",
                id=message_id,
                format=format
            ).execute()
            return response
        except HttpError as error:
            print(f"Error retrieving email metadata: {error}")
            return None

    def batch_get_email_metadata(self, message_ids, progress_callback=None, max_retries=5, batch_size=None):
        """
        Retrieves metadata in batches with enriched data for better detection.
        
        Args:
            message_ids: List of message IDs
            progress_callback: Optional callback for progress updates (step_name, current, total)
            max_retries: Maximum number of attempts
            batch_size: Batch size (uses self.BATCH_SIZE if None)
            
        Returns:
            Dictionary of message IDs and their metadata
        """
        if batch_size is None:
            batch_size = self.BATCH_SIZE
            
        results = {}
        total_messages = len(message_ids)
        
        # Check if caching is enabled
        use_cache = getattr(config, 'USE_METADATA_CACHE', True)
        cache_file = "./data/metadata_cache.json"
        cache = {}
        
        if use_cache:
            try:
                if os.path.exists(cache_file):
                    with open(cache_file, 'r') as f:
                        cache = json.load(f)
                    print(f"Loaded metadata cache with {len(cache)} entries")
            except Exception as e:
                print(f"Error loading metadata cache: {e}")
                
            # Filter IDs already in cache (and recent enough)
            current_time = time.time()
            cache_ttl_hours = getattr(config, 'CACHE_TTL_HOURS', 24)
            cache_ttl = cache_ttl_hours * 60 * 60  # Convert hours to seconds
            
            to_fetch = []
            cache_hits = 0
            
            for msg_id in message_ids:
                if msg_id in cache:
                    cache_entry = cache[msg_id]
                    # Check if cache entry is still valid
                    timestamp = cache_entry.get("_cache_timestamp", 0)
                    if current_time - timestamp < cache_ttl:
                        results[msg_id] = cache_entry
                        cache_hits += 1
                        continue
                to_fetch.append(msg_id)
                
            # Update progress if items were retrieved from cache
            if progress_callback and cache_hits > 0:
                progress_callback("Retrieving metadata...", cache_hits, total_messages)
                print(f"Cache hit: {cache_hits}/{total_messages} emails retrieved from cache")
        else:
            to_fetch = message_ids
        
        # Fetch remaining metadata using the callback
        if to_fetch:
            fetch_results = self._batch_fetch_metadata(to_fetch, progress_callback, max_retries, batch_size, len(results), total_messages)
            results.update(fetch_results)
        
        # Save updated cache if enabled
        if use_cache and to_fetch:
            try:
                os.makedirs("./data", exist_ok=True)
                # Add cache timestamps to new entries only if we fetched new data
                current_time = time.time()
                for msg_id, metadata in results.items():
                    if msg_id in to_fetch:  # Only update timestamps for newly fetched data
                        metadata["_cache_timestamp"] = current_time
                        cache[msg_id] = metadata
                
                # Clean old cache entries to prevent unlimited growth
                cutoff_time = current_time - (cache_ttl_hours * 2 * 60 * 60)  # Keep entries for 2x TTL
                cache = {k: v for k, v in cache.items() 
                        if v.get("_cache_timestamp", 0) > cutoff_time}
                
                with open(cache_file, 'w') as f:
                    json.dump(cache, f, indent=2)
                print(f"Updated cache with {len(to_fetch)} new entries")
            except Exception as e:
                print(f"Error saving metadata cache: {e}")
        
        return results

    def _batch_fetch_metadata(self, message_ids, progress_callback, max_retries, batch_size, current_count, total_count):
        """
        Internal method for batch metadata retrieval.
        
        Args:
            message_ids: List of message IDs to fetch
            progress_callback: Progress callback for progress updates
            max_retries: Maximum retry attempts
            batch_size: Size of each batch
            current_count: Current count of processed messages
            total_count: Total count of messages to process
            
        Returns:
            dict: Results dictionary
        """
        results = {}
        if not message_ids:
            return results
            
        # Optimize batch size based on the number of messages
        adaptive_batch_size = min(batch_size, max(5, len(message_ids) // 10))
        
        # Process in batches
        for i in range(0, len(message_ids), adaptive_batch_size):
            chunk = message_ids[i:i + adaptive_batch_size]
            
            # Execute the batch request with retries
            chunk_results = self.execute_batch_with_retry(chunk, max_retries)
            results.update(chunk_results)
            
            # Update the progress bar
            if progress_callback:
                progress_callback("Retrieving metadata...", current_count + i + len(chunk), total_count)
                
        return results

    def execute_batch_with_retry(self, chunk, max_retries=5):
        """
        Execute a batch request with retry logic.
        Enhanced version that fetches additional metadata including headers and HTML content.
        
        Args:
            chunk: List of message IDs to process
            max_retries: Maximum number of retry attempts
            
        Returns:
            dict: Batch results with message metadata
        """
        batch_results = {}

        # Dynamically reduce batch size on error
        current_chunk = chunk

        def callback(request_id, response, exception):
            if exception:
                print(f"An error occurred while getting email metadata for {request_id}: {exception}")
            else:
                try:
                    message_id = response["id"]
                    headers = response.get("payload", {}).get("headers", [])
                    labels = response.get("labelIds", [])
                    internal_date = response.get("internalDate")
                    thread_id = response.get("threadId", "")  # Get the thread ID

                    # Extract email headers
                    sender = ""
                    subject = ""
                    to_address = ""
                    cc_addresses = []
                    header_dict = {}

                    for header in headers:
                        name = header.get("name", "").lower()
                        value = header.get("value", "")
                        header_dict[name] = value

                        if name == "from":
                            sender = value
                        elif name == "subject":
                            subject = value
                        elif name == "to":
                            to_address = value
                        elif name == "cc":
                            cc_addresses = [addr.strip() for addr in value.split(",")]

                    # Extract HTML content and check for attachments
                    payload = response.get("payload", {})

                    # Check for attachments using centralized function
                    has_attachments = Utils.has_attachments(payload)

                    # Extract HTML content using centralized function
                    html_content = Utils.extract_content_from_payload(payload)

                    batch_results[message_id] = {
                        "id": message_id,
                        "sender": sender,
                        "subject": subject,
                        "labels": labels,
                        "internalDate": internal_date,
                        "headers": header_dict,
                        "html_content": html_content,
                        "to": to_address,
                        "cc": cc_addresses,
                        "has_attachments": has_attachments,
                        "threadId": thread_id
                    }
                except Exception as e:
                    print(f"Error in callback for {request_id}: {e}")
                    
        # Enhanced function to execute batch with improved error handling
        def execute_request():
            nonlocal current_chunk
            
            retry_count = 0
            success = False
            
            while retry_count < max_retries and not success:
                try:
                    batch = self.service.new_batch_http_request()
                    
                    for msg in current_chunk:
                        if isinstance(msg, dict) and "id" in msg:
                            msg_id = msg["id"]
                        else:
                            msg_id = msg
                            
                        batch.add(self.service.users().messages().get(
                            userId="me", id=msg_id, format="full"
                        ), callback=callback)
                    
                    batch.execute()
                    success = True
                    
                except HttpError as e:
                    retry_count += 1
                    if e.resp.status == 429:  # Rate limit exceeded
                        # Reduce batch size if encountering 429 errors
                        if len(current_chunk) > 1:
                            split_point = len(current_chunk) // 2
                            first_half = current_chunk[:split_point]
                            second_half = current_chunk[split_point:]
                            
                            print(f"Rate limit exceeded. Reducing batch size from {len(current_chunk)} to {len(first_half)}")
                            
                            # Process first half
                            try:
                                smaller_batch = self.service.new_batch_http_request()
                                for msg_id in first_half:
                                    if isinstance(msg_id, dict) and "id" in msg_id:
                                        msg_id = msg_id["id"]
                                    smaller_batch.add(self.service.users().messages().get(
                                        userId="me", id=msg_id, format="full"
                                    ), callback=callback)
                                    
                                # Wait longer before retrying
                                wait_time = min(30, 5 * (2 ** retry_count)) + random.uniform(0, 3)
                                print(f"Waiting {wait_time:.2f} seconds before retrying...")
                                time.sleep(wait_time)
                                
                                smaller_batch.execute()
                                
                                # Wait more between sub-batches
                                time.sleep(wait_time * 1.5)
                                
                                # Now second half
                                smaller_batch = self.service.new_batch_http_request()
                                for msg_id in second_half:
                                    if isinstance(msg_id, dict) and "id" in msg_id:
                                        msg_id = msg_id["id"]
                                    smaller_batch.add(self.service.users().messages().get(
                                        userId="me", id=msg_id, format="full"
                                    ), callback=callback)
                                
                                time.sleep(wait_time)
                                smaller_batch.execute()
                                success = True
                                
                            except Exception as sub_e:
                                print(f"Error in sub-batch processing: {sub_e}")
                                if retry_count >= max_retries:
                                    break
                                time.sleep(min(60, 10 * (2 ** retry_count)))
                        else:
                            # Single message, wait and retry
                            wait_time = min(60, 10 * (2 ** retry_count)) + random.uniform(0, 5)
                            print(f"Single message rate limit. Waiting {wait_time:.2f} seconds...")
                            time.sleep(wait_time)
                    else:
                        # Other HTTP errors
                        wait_time = min(30, 5 * (2 ** retry_count))
                        print(f"HTTP error {e.resp.status}. Waiting {wait_time} seconds before retry {retry_count + 1}/{max_retries}")
                        time.sleep(wait_time)
                        
                except Exception as e:
                    retry_count += 1
                    wait_time = min(30, 5 * (2 ** retry_count))
                    print(f"Unexpected error: {e}. Waiting {wait_time} seconds before retry {retry_count + 1}/{max_retries}")
                    time.sleep(wait_time)
        
        execute_request()
        
        # Check for missing messages and retry individually
        processed_ids = set(batch_results.keys())
        original_ids = set([msg["id"] if isinstance(msg, dict) else msg for msg in chunk if msg])
        
        missing_ids = original_ids - processed_ids
        if missing_ids and len(missing_ids) < len(original_ids):
            print(f"Found {len(missing_ids)} messages that weren't processed. Retrying individually...")
            
            for msg_id in missing_ids:
                try:
                    # Wait between individual requests
                    time.sleep(random.uniform(1, 3))
                    
                    # Individual request with minimal format
                    response = self.service.users().messages().get(
                        userId="me", id=msg_id, format="metadata"
                    ).execute()
                    
                    # Extract minimal information
                    headers = response.get("payload", {}).get("headers", [])
                    labels = response.get("labelIds", [])
                    thread_id = response.get("threadId", "")
                    
                    sender = ""
                    subject = ""
                    to_address = ""
                    cc_addresses = []
                    header_dict = {}
                    
                    for header in headers:
                        name = header.get("name", "").lower()
                        value = header.get("value", "")
                        header_dict[name] = value
                        
                        if name == "from":
                            sender = value
                        elif name == "subject":
                            subject = value
                        elif name == "to":
                            to_address = value
                        elif name == "cc":
                            cc_addresses = [addr.strip() for addr in value.split(",")]
                    
                    batch_results[msg_id] = {
                        "id": msg_id,
                        "sender": sender,
                        "subject": subject,
                        "labels": labels,
                        "internalDate": response.get("internalDate"),
                        "headers": header_dict,
                        "html_content": "",  # No HTML content in metadata mode
                        "to": to_address,
                        "cc": cc_addresses,
                        "has_attachments": False,  # No attachments info in metadata mode
                        "threadId": thread_id
                    }
                    
                except Exception as e:
                    print(f"Failed to retrieve individual message {msg_id}: {e}")
        
        return batch_results

    def parse_email_metadata(self, response):
        """
        Analyze the metadata of an email to extract important information.
        
        Args:
            response: Gmail API response for a message
            
        Returns:
            dict: Parsed metadata dictionary
        """
        if not response or not isinstance(response, dict):
            return None
            
        try:
            # Initialize the metadata dictionary
            metadata = {
                "id": response.get("id", ""),
                "threadId": response.get("threadId", ""),
                "labelIds": response.get("labelIds", []),
                "internalDate": response.get("internalDate", 0),
                "sizeEstimate": response.get("sizeEstimate", 0),
                "headers": {},
                "sender": "",
                "subject": "",
                "to": "",
                "cc": [],
                "has_attachments": False,
                "html_content": ""
            }
            
            # Extract email headers
            if "payload" in response and "headers" in response["payload"]:
                headers = response["payload"]["headers"]
                
                # Build a dictionary of headers for easier access
                header_dict = {}
                for header in headers:
                    header_name = header.get("name", "").lower()
                    header_value = header.get("value", "")
                    header_dict[header_name] = header_value
                    
                # Store all headers
                metadata["headers"] = header_dict
                
                # Extract key information
                metadata["sender"] = header_dict.get("from", "")
                metadata["subject"] = header_dict.get("subject", "")
                metadata["to"] = header_dict.get("to", "")
                
                # Extract CC recipients
                if "cc" in header_dict:
                    metadata["cc"] = [addr.strip() for addr in header_dict["cc"].split(',')]
                    
                # Extract HTML content if available
                if "payload" in response:
                    payload = response["payload"]
                    
                # Check for attachments
                metadata["has_attachments"] = Utils.has_attachments(payload)
                
                # Extract HTML content
                metadata["html_content"] = Utils.extract_content_from_payload(payload)
                
            return metadata
            
        except Exception as e:
            print(f"Error parsing email metadata: {e}")
            return None

    @staticmethod
    def api_request_with_retry(request_func, max_retries=5, base_delay=1):
        """
        Execute an API request with exponential backoff retry logic.
        
        Args:
            request_func: A function that executes the actual API request
            max_retries: Maximum number of retry attempts
            base_delay: Base delay for exponential backoff in seconds
        
        Returns:
            The result of the API request if successful
        """
        last_exception = None
        
        for retry in range(max_retries):
            try:
                return request_func()
            except HttpError as e:
                last_exception = e
                status_code = e.resp.status
                
                # Handle different types of HTTP errors
                if status_code in [429, 500, 502, 503, 504] and retry < max_retries - 1:
                    # Exponential backoff with aggressive delay for 429 rate limit errors
                    if status_code == 429:
                        # For rate limit errors, wait much longer
                        wait_time = min(120, base_delay * (3 ** retry)) + random.uniform(0, retry * 2)
                        print(f"Rate limited (429). Retrying in {wait_time:.2f} seconds...")
                    else:
                        # For other server errors
                        wait_time = base_delay * (2 ** retry) + random.uniform(0, 1)
                        print(f"Server error ({status_code}). Retrying in {wait_time:.2f} seconds...")
                        
                    time.sleep(wait_time)
                else:
                    # Other error codes or last attempt
                    print(f"HTTP error {status_code}: {e}")
                    raise
            except Exception as e:
                # Other non-HTTP errors
                last_exception = e
                if retry < max_retries - 1:
                    wait_time = base_delay * (2 ** retry) + random.uniform(0, 1)
                    print(f"Error: {e}. Retrying in {wait_time:.2f} seconds...")
                    time.sleep(wait_time)
                else:
                    print(f"Failed after {max_retries} attempts: {e}")
                    raise
        
        # If we get here, all attempts have failed
        if last_exception:
            raise last_exception
        else:
            raise Exception(f"Request failed after {max_retries} attempts for unknown reasons") 