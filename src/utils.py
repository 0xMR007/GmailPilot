# src/utils.py

"""
Centralized utility functions for GmailPilot.
Contains common functions used across multiple modules to avoid code duplication.
"""

import re
import base64
import html
from datetime import datetime

class Utils:
    """
    Static utility class containing helper functions.
    """

    @staticmethod
    def extract_email_data(meta):
        """Extract email data from metadata in standardized format."""
        # Ensure internal_date is always an integer
        internal_date = meta.get("internalDate", 0)
        if isinstance(internal_date, str):
            try:
                internal_date = int(internal_date)
            except (ValueError, TypeError):
                internal_date = 0
        
        return {
            "sender": meta.get("sender", ""),
            "subject": meta.get("subject", ""),
            "html_content": meta.get("html_content", ""),
            "headers": meta.get("headers", {}),
            "labels": meta.get("labelIds", []),
            "internal_date": internal_date,
            "to": meta.get("to", ""),
            "cc": meta.get("cc", []),
            "has_attachments": meta.get("has_attachments", False),
            "thread_id": meta.get("threadId", ""),
            "domain": Utils.extract_domain(meta.get("sender", "")),
            "normalized_sender": Utils.normalize_sender(meta.get("sender", ""))
        }

    @staticmethod
    def extract_domain(email):
        """
        Extract domain from email address.
        
        Args:
            email (str): Email address
            
        Returns:
            str: Domain part of the email
        """
        if not email or '@' not in email:
            return ""
        
        try:
            # Handle email format "Name <email@domain.com>"
            if '<' in email and '>' in email:
                email = email.split('<')[1].split('>')[0]
            
            domain = email.split('@')[1].lower().strip()
            return domain
        except (IndexError, AttributeError):
            return ""

    @staticmethod
    def decode_html_content(data):
        """
        Decode HTML content from base64 if necessary.
        
        Args:
            data (str): HTML content, possibly base64 encoded
            
        Returns:
            str: Decoded HTML content
        """
        if not data:
            return ""
        
        try:
            # Try to decode base64 content
            decoded_bytes = base64.urlsafe_b64decode(data + '==')
            content = decoded_bytes.decode('utf-8')
            return content
        except Exception:
            # If decoding fails, return original data
            return data

    @staticmethod
    def check_attachments_recursive(parts):
        """
        Recursively check for attachments in email parts.
        
        Args:
            parts (list): List of email parts
            
        Returns:
            bool: True if attachments found
        """
        for part in parts:
            if part.get('filename'):
                return True
            if part.get('parts'):
                if Utils.check_attachments_recursive(part['parts']):
                    return True
        return False

    @staticmethod
    def extract_html_recursive(parts):
        """
        Recursively extract HTML content from email parts.
        
        Args:
            parts (list): List of email parts
            
        Returns:
            str: Extracted HTML content
        """
        content = ""
        for part in parts:
            mime_type = part.get('mimeType', '')
            if mime_type == 'text/html':
                body = part.get('body', {})
                data = body.get('data', '')
                if data:
                    content += Utils.decode_html_content(data)
            elif part.get('parts'):
                content += Utils.extract_html_recursive(part['parts'])
        return content

    @staticmethod
    def extract_content_from_payload(payload):
        """
        Extract HTML content from email payload.
        
        Args:
            payload (dict): Email payload from Gmail API
            
        Returns:
            str: Extracted HTML content
        """
        content = ""
        
        if not payload:
            return content
        
        # Check if this is a multipart message
        if payload.get('parts'):
            content = Utils.extract_html_recursive(payload['parts'])
        else:
            # Single part message
            mime_type = payload.get('mimeType', '')
            if mime_type == 'text/html':
                body = payload.get('body', {})
                data = body.get('data', '')
                if data:
                    content = Utils.decode_html_content(data)
        
        return content

    @staticmethod
    def has_attachments(payload):
        """
        Check if email has attachments.
        
        Args:
            payload (dict): Email payload from Gmail API
            
        Returns:
            bool: True if email has attachments
        """
        if not payload:
            return False
        
        # Check if this is a multipart message
        if payload.get('parts'):
            return Utils.check_attachments_recursive(payload['parts'])
        else:
            # Single part message - check if it has a filename
            return bool(payload.get('filename'))

    @staticmethod
    def normalize_sender(sender):
        """
        Normalize sender address for consistent comparison.
        
        Args:
            sender (str): Sender email address
            
        Returns:
            str: Normalized sender address
        """
        if not sender:
            return ""
        
        # Extract email from "Name <email@domain.com>" format
        if '<' in sender and '>' in sender:
            sender = sender.split('<')[1].split('>')[0]
        
        return sender.lower().strip()