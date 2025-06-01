# src/temporal_analyzer.py

"""
Temporal analyzer for GmailPilot.
Analyzes temporal patterns in email sending to detect promotional emails.
"""

import json
import os
import time
from datetime import datetime
import statistics
from src.config import config
from src.utils import Utils

class TemporalAnalyzer:
    """
    Class for analyzing temporal patterns in emails.
    Allows detection of regular sending patterns that often characterize newsletters
    and automated promotional emails.
    """
    
    def __init__(self, data_file="./data/temporal_data.json"):
        self.data_file = data_file
        self.sender_data = self._load_data()
        self.window_days = config.TEMPORAL_WINDOW_DAYS
        self.min_emails = config.TEMPORAL_MIN_EMAILS
        self.regularity_threshold = config.TEMPORAL_REGULARITY_THRESHOLD
    
    def _load_data(self):
        """Load temporal data from JSON file"""
        try:
            if os.path.exists(self.data_file):
                with open(self.data_file, 'r') as f:
                    return json.load(f)
            return {}
        except Exception as e:
            print(f"Error loading temporal data: {e}")
            return {}
    
    def _save_data(self):
        """Save temporal data to JSON file"""
        try:
            # Create parent directory if necessary
            os.makedirs(os.path.dirname(self.data_file), exist_ok=True)
            
            with open(self.data_file, 'w') as f:
                json.dump(self.sender_data, f, indent=2)
        except Exception as e:
            print(f"Error saving temporal data: {e}")
    
    def record_email(self, sender, timestamp_str, is_promo=None):
        """
        Record an email for temporal analysis
        
        Args:
            sender (str): Email sender
            timestamp_str (str): Email timestamp as string
            is_promo (bool): Whether email is promotional (optional)
        """
        try:
            # Normalize sender address using centralized method
            normalized_sender = Utils.normalize_sender(sender)
            
            # Convert timestamp to int
            if isinstance(timestamp_str, str):
                timestamp = int(timestamp_str)
            else:
                timestamp = timestamp_str
            
            # Initialize data for this sender if necessary
            if normalized_sender not in self.sender_data:
                self.sender_data[normalized_sender] = {
                    "emails": [],
                    "total_count": 0,
                    "promo_count": 0,
                    "last_analysis": 0
                }
            
            # Add email to data
            email_data = {
                "timestamp": timestamp,
                "is_promo": is_promo
            }
            
            # Update counters
            self.sender_data[normalized_sender]["emails"].append(email_data)
            self.sender_data[normalized_sender]["total_count"] += 1
            if is_promo:
                self.sender_data[normalized_sender]["promo_count"] += 1
            
            # Limit data size (keep last 20 emails)
            if len(self.sender_data[normalized_sender]["emails"]) > 20:
                self.sender_data[normalized_sender]["emails"] = self.sender_data[normalized_sender]["emails"][-20:]
            
            # Save data
            self._save_data()
            
        except Exception as e:
            print(f"Error recording email: {e}")
    
    def analyze_frequency(self, sender):
        """
        Analyze sending frequency for a sender
        
        Args:
            sender (str): Email sender to analyze
            
        Returns:
            tuple: (regularity_score, is_promo_pattern)
        """
        try:
            normalized_sender = Utils.normalize_sender(sender)
            
            # Check if we have data for this sender
            if normalized_sender not in self.sender_data:
                return None, False
            
            # Check if we have enough emails for meaningful analysis
            sender_data = self.sender_data[normalized_sender]
            if sender_data["total_count"] < self.min_emails:
                return None, False
            
            # Create sorted timestamp list
            emails = sender_data["emails"]
            timestamps = [email["timestamp"] for email in emails]
            timestamps.sort()
            
            # Filter emails within temporal window
            current_time = time.time() * 1000  # Convert to milliseconds
            window_start = current_time - (self.window_days * 24 * 60 * 60 * 1000)
            recent_timestamps = [ts for ts in timestamps if ts >= window_start]
            
            # Check again if we have enough recent emails
            if len(recent_timestamps) < self.min_emails:
                return None, False
            
            # Calculate intervals between emails
            intervals = []
            for i in range(1, len(recent_timestamps)):
                interval = recent_timestamps[i] - recent_timestamps[i-1]
                intervals.append(interval)
            
            if not intervals:
                return None, False
            
            # Calculate average interval
            avg_interval = sum(intervals) / len(intervals)
            
            # Calculate standard deviation
            if len(intervals) > 1:
                variance = sum((x - avg_interval) ** 2 for x in intervals) / len(intervals)
                std_dev = variance ** 0.5
            else:
                # If we don't have enough data to calculate standard deviation
                return None, False
            
            # Calculate coefficient of variation (CV) as regularity measure
            # Lower CV means more regular sending
            if avg_interval > 0:
                cv = std_dev / avg_interval
            else:
                # To avoid division by zero
                return None, False
            
            # Calculate regularity score (inverse of CV, normalized between 0 and 1)
            # Value close to 1 indicates high regularity
            regularity_score = 1 / (1 + cv)
            
            # Determine if it's a promotional pattern based on regularity and % of promo emails
            promo_ratio = sender_data["promo_count"] / sender_data["total_count"]
            
            # A promotional pattern is characterized by high regularity and high proportion of promotional emails
            is_promo_pattern = (regularity_score >= self.regularity_threshold and promo_ratio >= 0.5)
            
            # If majority of emails were classified as promotional, it's probably a promo pattern
            if promo_ratio >= 0.7:
                is_promo_pattern = True
            
            # Update last analysis date
            self.sender_data[normalized_sender]["last_analysis"] = current_time
            self._save_data()
            
            return regularity_score, is_promo_pattern
            
        except Exception as e:
            print(f"Error analyzing frequency for {sender}: {e}")
            return None, False
    
    def get_sender_profile(self, sender):
        """
        Get a complete profile of a sender including sending patterns and classification.
        
        Args:
            sender (str): Email address of the sender
            
        Returns:
            dict: Comprehensive sender profile
        """
        try:
            sender = Utils.normalize_sender(sender)
            
            if sender not in self.sender_data:
                return {
                    "total_count": 0,
                    "promo_count": 0,
                    "promo_ratio": 0.0,
                    "pattern_type": "unknown",
                    "is_regular": False,
                    "frequency_days": 0
                }
            
            data = self.sender_data[sender]
            
            # Get frequency analysis
            regularity_score, is_promo_pattern = self.analyze_frequency(sender)
            
            # Determine pattern classification
            pattern_type = "unknown"
            if data["total_count"] >= 3:
                if data["promo_count"] / data["total_count"] >= 0.8:
                    pattern_type = "promotional"
                elif data["promo_count"] / max(data["total_count"], 1) >= 0.5:
                    pattern_type = "mixed"
                else:
                    pattern_type = "normal"
            
            # Check if sender has regular patterns
            if regularity_score is not None and regularity_score > 0.5 and len(data["emails"]) >= 3:
                is_regular = True
                emails_sorted = sorted(data["emails"], key=lambda x: x["timestamp"])
                intervals = [(emails_sorted[i]["timestamp"] - emails_sorted[i-1]["timestamp"]) / (24 * 60 * 60 * 1000) 
                           for i in range(1, len(emails_sorted))]
                avg_interval = statistics.mean(intervals)
                frequency_days = round(avg_interval, 1)
            else:
                is_regular = False
                frequency_days = 0
            
            return {
                "total_count": data["total_count"],
                "promo_count": data["promo_count"],
                "promo_ratio": data["promo_count"] / max(data["total_count"], 1),
                "pattern_type": pattern_type,
                "is_regular": is_regular,
                "frequency_days": frequency_days,
                "regularity_score": regularity_score
            }
            
        except Exception as e:
            print(f"Error getting sender profile: {e}")
            return {
                "total_count": 0,
                "promo_count": 0,
                "promo_ratio": 0.0,
                "pattern_type": "unknown",
                "is_regular": False,
                "frequency_days": 0
            } 