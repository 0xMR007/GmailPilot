# src/context_classifier.py

"""
Classifier that takes context (thread, history) into account to improve classification
"""

import json
import os
import time

class ContextClassifier:
    """
    Classifier that takes context (thread, history) into account to improve classification
    """
    def __init__(self, email_manager):
        self.email_manager = email_manager
        self.cache_path = './data/context_cache.json'
        self.thread_cache = self._load_cache()
        self.max_thread_size = 10
        
    def _load_cache(self):
        """Load context cache from JSON file"""
        try:
            if os.path.exists(self.cache_path):
                with open(self.cache_path, 'r') as f:
                    return json.load(f)
            return {}
        except Exception as e:
            print(f"Error loading context cache: {e}")
            return {}
            
    def _save_cache(self):
        """Save context cache to JSON file"""
        try:
            # Ensure directory exists
            os.makedirs(os.path.dirname(self.cache_path), exist_ok=True)
            
            # Limit cache size (keep the 100 most recent threads)
            if len(self.thread_cache) > 100:
                # Sort by last access timestamp
                sorted_threads = sorted(
                    self.thread_cache.items(),
                    key=lambda x: x[1].get('last_accessed', 0),
                    reverse=True
                )
                
                # Keep only the 100 most recent
                self.thread_cache = dict(sorted_threads[:100])
            
            with open(self.cache_path, 'w') as f:
                json.dump(self.thread_cache, f, indent=2)
                
        except Exception as e:
            print(f"Error saving context cache: {e}")
            
    def analyze_thread(self, thread_id):
        """
        Analyze a thread to determine context and improve classification
        
        Args:
            thread_id (str): Thread ID to analyze
            
        Returns:
            dict: Thread information (participants, importance, etc.)
        """
        # If we've already analyzed this thread recently, use cache
        current_time = time.time()
        cache_ttl = 24 * 60 * 60  # 24 hours
        
        if thread_id in self.thread_cache:
            # Update last access timestamp
            self.thread_cache[thread_id]['last_accessed'] = current_time
            
            # Check if cache is still valid
            if current_time - self.thread_cache[thread_id].get('timestamp', 0) < cache_ttl:
                return self.thread_cache[thread_id]
        
        try:
            # Retrieve thread messages from Gmail API
            thread_messages = self.email_manager.get_thread_messages(thread_id, max_results=self.max_thread_size)
            
            if not thread_messages:
                return {'is_important': False, 'context_score': 0, 'reasons': ["Thread empty or unavailable"]}
            
            # Extract unique participants
            participants = set()
            user_address = self.email_manager.user_address.lower()
            
            for message in thread_messages:
                # Add sender (if not the user)
                sender = message.get('sender', '').lower()
                if sender and sender != user_address and '@' in sender:
                    participants.add(sender)
                    
                # Add recipients (if not the user)
                for recipient in message.get('to', '').split(','):
                    recipient = recipient.strip().lower()
                    if recipient and recipient != user_address and '@' in recipient:
                        participants.add(recipient)
            
            # Count number of exchanged messages
            message_count = len(thread_messages)
            
            # Determine if thread is primarily initiated by user
            user_initiated = any(msg.get('sender', '').lower() == user_address for msg in thread_messages[:1])
            
            # Calculate context score based on these factors
            context_score = 0
            reasons = []
            
            # More participants = more important
            if len(participants) >= 3:
                context_score += min(len(participants) * 0.8, 3)
                reasons.append(f"Multiple participants ({len(participants)})")
                
            # More exchanges = more important
            if message_count >= 3:
                context_score += min(message_count * 0.5, 2.5)
                reasons.append(f"Active thread ({message_count} messages)")
                
            # If user initiated, it's probably important
            if user_initiated:
                context_score += 1.5
                reasons.append("User initiated thread")
                
            # Determine thread importance
            is_important = context_score >= 3.0
            
            # Prepare data to cache
            thread_data = {
                'is_important': is_important,
                'context_score': context_score,
                'participants': list(participants),
                'message_count': message_count,
                'user_initiated': user_initiated,
                'reasons': reasons,
                'timestamp': current_time,
                'last_accessed': current_time
            }
            
            # Update cache
            self.thread_cache[thread_id] = thread_data
            self._save_cache()
            
            return thread_data
            
        except Exception as e:
            print(f"Error analyzing thread {thread_id}: {e}")
            return {'is_important': False, 'context_score': 0, 'reasons': [f"Error: {str(e)}"]}