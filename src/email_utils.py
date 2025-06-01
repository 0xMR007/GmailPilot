# src/email_utils.py

"""
Email-specific utility functions for analysis and processing.
"""

import re
import time

from typing import List, Dict, Any, Optional
from src.config import config
from src.email_manager import EmailManager
from src.hybrid_classifier import HybridClassifier
from src.logger import ReportLogger
from src.context_classifier import ContextClassifier
from bs4 import BeautifulSoup
from rich.console import Console

# Create a console instance
console = Console()

class EmailUtils:
    """
    Email-specific utility functions for analysis and processing.
    """

    @staticmethod
    def extract_attachments(message: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Extract attachment information from a Gmail message.
        
        Args:
            message: Gmail message dict from API
            
        Returns:
            List of attachment information dictionaries
        """
        attachments = []
        payload = message.get('payload', {})
        parts = payload.get('parts', [])

        for part in parts:
            filename = part.get('filename')
            body = part.get('body', {})
            attachment_id = body.get('attachmentId')

            if filename and attachment_id:
                attachments.append({
                    'filename': filename,
                    'attachment_id': attachment_id,
                    'mimeType': part.get('mimeType', ''),
                    'size': body.get('size', 0)
                })

        return attachments

    @staticmethod
    def extract_headers_dict(headers: List[Dict[str, str]]) -> Dict[str, str]:
        """
        Convert Gmail headers list to a dictionary for easier access.
        
        Args:
            headers: List of header dictionaries from Gmail API
            
        Returns:
            Dictionary with header names as keys (lowercase)
        """
        header_dict = {}
        for header in headers:
            name = header.get("name", "").lower()
            value = header.get("value", "")
            header_dict[name] = value
        return header_dict

    @staticmethod
    def parse_email_addresses(email_field: str) -> List[str]:
        """
        Parse email addresses from a field that might contain multiple addresses.
        
        Args:
            email_field: Email field that might contain multiple addresses
            
        Returns:
            List of individual email addresses
        """
        if not email_field:
            return []
        
        # Common patterns for multiple emails
        # Split by comma, semicolon, or newline
        addresses = re.split(r'[,;\n]', email_field)
        
        parsed_addresses = []
        for addr in addresses:
            addr = addr.strip()
            if addr:
                # Extract email from "Name <email@domain.com>" format
                match = re.search(r'<([^>]+)>', addr)
                if match:
                    parsed_addresses.append(match.group(1).strip())
                elif '@' in addr:
                    parsed_addresses.append(addr)
        
        return parsed_addresses

    @staticmethod
    def is_auto_generated_email(headers: Dict[str, str], sender: str, subject: str) -> bool:
        """
        Detect if an email is auto-generated (notifications, alerts, etc.).
        
        Args:
            headers: Email headers dictionary
            sender: Sender email address
            subject: Email subject
            
        Returns:
            True if the email appears to be auto-generated
        """
        # Check for auto-generated indicators in headers
        auto_headers = [
            'auto-submitted', 'x-auto-response-suppress', 'precedence',
            'x-autoreply', 'x-autorespond'
        ]
        
        for header in auto_headers:
            if header in headers:
                value = headers[header].lower()
                if 'auto' in value or 'generated' in value:
                    return True
        
        # Check sender patterns
        auto_sender_patterns = [
            r'no-?reply', r'noreply', r'donotreply', r'auto', r'system',
            r'notification', r'alert', r'daemon', r'mailer'
        ]
        
        for pattern in auto_sender_patterns:
            if re.search(pattern, sender, re.IGNORECASE):
                return True
        
        # Check subject patterns
        auto_subject_patterns = [
            r'automatic', r'auto-?generated', r'system notification',
            r'delivery status', r'out of office', r'vacation reply'
        ]
        
        for pattern in auto_subject_patterns:
            if re.search(pattern, subject, re.IGNORECASE):
                return True
        
        return False

    @staticmethod
    def calculate_text_to_html_ratio(html_content: str) -> float:
        """
        Calculate the ratio of text content to HTML markup.
        High ratios suggest content-heavy emails, low ratios suggest design-heavy emails.
        
        Args:
            html_content: HTML content of the email
            
        Returns:
            Ratio of text length to HTML length (0.0 to 1.0)
        """
        if not html_content:
            return 0.0
        
        # Extract text content
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            text_content = soup.get_text()
            
            text_length = len(text_content.strip())
            html_length = len(html_content)
            
            if html_length == 0:
                return 0.0
            
            return min(1.0, text_length / html_length)
            
        except Exception:
            # Fallback: simple text extraction
            text_without_tags = re.sub(r'<[^>]+>', '', html_content)
            text_length = len(text_without_tags.strip())
            html_length = len(html_content)
            
            return min(1.0, text_length / html_length) if html_length > 0 else 0.0

    @staticmethod
    def extract_urls(html_content: str) -> List[str]:
        """
        Extract all URLs from HTML content.
        
        Args:
            html_content: HTML content to analyze
            
        Returns:
            List of unique URLs found in the content
        """
        if not html_content:
            return []
        
        urls = set()
        
        # Extract URLs from href attributes
        href_pattern = r'href=["\']([^"\']+)["\']'
        href_matches = re.findall(href_pattern, html_content, re.IGNORECASE)
        urls.update(href_matches)
        
        # Extract URLs from src attributes (images, etc.)
        src_pattern = r'src=["\']([^"\']+)["\']'
        src_matches = re.findall(src_pattern, html_content, re.IGNORECASE)
        urls.update(src_matches)
        
        # Extract plain URLs in text
        url_pattern = r'https?://[^\s<>"\']+'
        text_urls = re.findall(url_pattern, html_content)
        urls.update(text_urls)
        
        # Filter out obviously invalid URLs
        valid_urls = []
        for url in urls:
            if url and not url.startswith('#') and len(url) > 4:
                valid_urls.append(url)
        
        return list(valid_urls)

    @staticmethod
    def is_likely_newsletter(sender: str, subject: str, html_content: str) -> bool:
        """
        Detect if an email is likely a newsletter.
        
        Args:
            sender: Email sender
            subject: Email subject
            html_content: HTML content
            
        Returns:
            True if the email appears to be a newsletter
        """
        # Newsletter indicators in subject
        newsletter_subject_patterns = [
            r'newsletter', r'digest', r'weekly', r'monthly', r'daily',
            r'bulletin', r'update', r'recap', r'roundup', r'edition'
        ]
        
        for pattern in newsletter_subject_patterns:
            if re.search(pattern, subject, re.IGNORECASE):
                return True
        
        # Newsletter indicators in sender
        newsletter_sender_patterns = [
            r'newsletter', r'digest', r'updates', r'news'
        ]
        
        for pattern in newsletter_sender_patterns:
            if re.search(pattern, sender, re.IGNORECASE):
                return True
        
        # Newsletter indicators in content
        if html_content:
            newsletter_content_indicators = [
                'unsubscribe', 'newsletter', 'mailing list', 'update preferences',
                'view in browser', 'forward to a friend'
            ]
            
            content_lower = html_content.lower()
            indicator_count = sum(1 for indicator in newsletter_content_indicators 
                                if indicator in content_lower)
            
            # If 2 or more newsletter indicators are present
            if indicator_count >= 2:
                return True
        
        return False

    @staticmethod
    def count_promotional_elements(html_content: str) -> Dict[str, int]:
        """
        Count various promotional elements in HTML content.
        
        Args:
            html_content: HTML content to analyze
            
        Returns:
            Dictionary with counts of different promotional elements
        """
        if not html_content:
            return {'images': 0, 'links': 0, 'buttons': 0, 'promotional_words': 0}
        
        content_lower = html_content.lower()
        
        # Count images
        image_count = content_lower.count('<img')
        
        # Count links
        link_count = content_lower.count('href=')
        
        # Count button-like elements
        button_patterns = [
            r'<button[^>]*>', r'<input[^>]*type=["\']button["\'][^>]*>',
            r'<a[^>]*class=["\'][^"\']*button[^"\']*["\'][^>]*>',
            r'<div[^>]*class=["\'][^"\']*button[^"\']*["\'][^>]*>'
        ]
        button_count = 0
        for pattern in button_patterns:
            button_count += len(re.findall(pattern, html_content, re.IGNORECASE))
        
        # Count promotional words
        promotional_words = [
            'sale', 'discount', 'offer', 'deal', 'promo', 'save', 'free',
            'limited', 'exclusive', 'special', 'urgent', 'hurry', 'now',
            'buy', 'shop', 'order', 'click', 'subscribe', 'unsubscribe'
        ]
        
        promotional_word_count = 0
        for word in promotional_words:
            promotional_word_count += content_lower.count(word)
        
        return {
            'images': image_count,
            'links': link_count,
            'buttons': button_count,
            'promotional_words': promotional_word_count
        }

    @staticmethod
    def get_email_priority(headers: Dict[str, str]) -> str:
        """
        Extract email priority from headers.
        
        Args:
            headers: Email headers dictionary
            
        Returns:
            Priority level: 'high', 'normal', 'low', or 'unknown'
        """
        # Check various priority headers
        priority_headers = ['priority', 'x-priority', 'importance', 'x-msmail-priority']
        
        for header in priority_headers:
            if header in headers:
                value = headers[header].lower()
                
                # High priority indicators
                if any(indicator in value for indicator in ['high', 'urgent', '1', 'important']):
                    return 'high'
                
                # Low priority indicators
                if any(indicator in value for indicator in ['low', '5', 'non-urgent']):
                    return 'low'
                
                # Normal priority indicators
                if any(indicator in value for indicator in ['normal', '3', 'medium']):
                    return 'normal'
        
        # Default to normal if no priority header found
        return 'unknown'

class EmailProcessingResult:
    """Data class to hold email processing results."""
    
    def __init__(self):
        self.total_retrieved = 0
        self.total_analyzed = 0
        self.promotional_count = 0
        self.important_count = 0
        self.skipped_count = 0
        self.error_count = 0
        self.promotional_ids = []
        self.processing_time = 0
        self.results = []
        self.report_paths = {}

class EmailProcessor:
    """
    Orchestrates the complete email processing workflow.
    Optimized with lazy loading and fast mode support.
    """
    
    def __init__(self, email_manager: EmailManager, fast_mode=None):
        self.email_manager = email_manager
        self._classifier = None
        self._context_analyzer = None
        self.logger = None
        
        # Performance mode - use config default if not specified
        if fast_mode is None:
            self.fast_mode = getattr(config, 'FAST_MODE', False)
        else:
            self.fast_mode = fast_mode
        
        # Initialize statistics
        self.stats = {
            'total_processed': 0,
            'classification_time': 0,
            'metadata_time': 0
        }

    @property
    def classifier(self):
        """Lazy loading for classifier"""
        if self._classifier is None:
            self._classifier = HybridClassifier(fast_mode=self.fast_mode)
        return self._classifier
    
    @property
    def context_analyzer(self):
        """Lazy loading for context analyzer"""
        if self._context_analyzer is None and not self.fast_mode:
            # Only load if not disabled in config and not in fast mode
            if not getattr(config, 'SKIP_CONTEXT_ANALYSIS', False):
                self._context_analyzer = ContextClassifier(self.email_manager)
        return self._context_analyzer
    
    def process_emails(self, 
                      dry_run: bool = False,
                      progress_callback: Optional[callable] = None,
                      max_emails: Optional[int] = None) -> EmailProcessingResult:
        """
        Process emails with classification and optional labeling.
        
        Args:
            dry_run: If True, don't apply labels, just analyze
            progress_callback: Optional callback for progress updates
            max_emails: Maximum number of emails to process (None for all)
            
        Returns:
            EmailProcessingResult: Complete processing results
        """
        start_time = time.time()
        result = EmailProcessingResult()
        
        # Initialize logger
        self.logger = ReportLogger()
        
        try:
            # Step 1: Retrieve email IDs
            if progress_callback:
                progress_callback("Retrieving emails...", 0, 0)
            
            messages = self.email_manager.get_emails_ids(max_results=max_emails)
            if not messages:
                return result
            
            result.total_retrieved = len(messages)
            console.print(f"\n[bold green]✓[/bold green] Found {result.total_retrieved} emails to process")
            
            # Fast mode optimization: increase batch size for better efficiency
            effective_batch_size = config.BATCH_SIZE
            if self.fast_mode:
                # In fast mode, use larger batches for better API efficiency
                effective_batch_size = min(config.BATCH_SIZE * 2, 50)
                console.print(f"[cyan]🚀 Fast mode enabled - using optimized batch size: {effective_batch_size}[/cyan]")
            else:
                effective_batch_size = config.BATCH_SIZE
            
            message_ids = [m["id"] for m in messages]
            
            # Step 2: Retrieve metadata with optimized batching
            metadata_start = time.time()
            if progress_callback:
                progress_callback("Retrieving metadata...", 0, len(messages))
            
            all_metadata = self.email_manager.batch_get_email_metadata(
                message_ids,
                batch_size=effective_batch_size,
                progress_callback=progress_callback
            )
            self.stats['metadata_time'] = time.time() - metadata_start
            
            # Step 3: Analyze emails with performance tracking
            classification_start = time.time()
            if progress_callback:
                progress_callback("Analyzing emails...", 0, len(messages))
            
            analysis_results = []
            for i, msg_id in enumerate(message_ids):
                try:
                    single_result = self._process_single_email(msg_id, all_metadata.get(msg_id, {}))
                    analysis_results.append(single_result)
                    
                    if progress_callback:
                        progress_callback("Analyzing emails...", i + 1, len(messages))
                        
                except Exception as e:
                    # Create error result
                    error_result = self._create_error_result(msg_id, str(e), all_metadata.get(msg_id, {}))
                    analysis_results.append(error_result)
                    result.error_count += 1
                    
                    if progress_callback:
                        progress_callback("Analyzing emails...", i + 1, len(messages))
            
            self.stats['classification_time'] = time.time() - classification_start
            self.stats['total_processed'] = len(analysis_results)
            
            # Step 4: Process results and collect statistics
            self._process_analysis_results(analysis_results, result)
            
            # Step 5: Apply labels if not dry run
            if not dry_run and result.promotional_ids:
                if progress_callback:
                    progress_callback("Applying labels...", 0, len(result.promotional_ids))
                
                success = self.email_manager.batch_apply_label(
                    result.promotional_ids, 
                    config.TARGET_FOLDER,
                    progress_callback=progress_callback
                )
                
                if not success:
                    # Verify partial success
                    success = self.email_manager.verify_labels_applied(
                        result.promotional_ids, 
                        self.email_manager.get_label_id()
                    )
            
            # Step 6: Generate reports
            result.processing_time = time.time() - start_time
            
            # Add performance statistics
            if getattr(config, 'VERBOSE_LOGGING', False):
                console.print(f"[dim]Performance: Metadata {self.stats['metadata_time']:.1f}s, Classification {self.stats['classification_time']:.1f}s[/dim]")
            
            if config.ENABLE_REPORTING:
                result.report_paths = self.logger.generate_report(
                    total_scanned=result.total_analyzed,
                    total_labelled=result.promotional_count,
                    processing_time=f"{result.processing_time:.2f}s",
                    dry_run=dry_run
                )
            
            result.results = analysis_results
            
        except Exception as e:
            # Log the error but don't crash
            print(f"Error in email processing: {e}")
            result.processing_time = time.time() - start_time
        
        return result
    
    def _process_single_email(self, message_id: str, meta: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a single email through the classification pipeline.
        
        Args:
            message_id: Email message ID
            meta: Email metadata
            
        Returns:
            Dictionary with processing results
        """
        # Check for skip conditions
        labels = meta.get("labelIds", [])
        if "CATEGORY_UPDATES" in labels:
            return {
                "message_id": message_id,
                "is_promo": False,
                "promo_score": 0,
                "sbert_promo_score": 0,
                "sbert_importance_score": 0,
                "combined_promo_score": 0,
                "is_important": False,
                "importance_score": 0,
                "importance_reasons": [],
                "reasons": ["Skipped: Email has CATEGORY_UPDATES label"],
                "action": "Skipped - CATEGORY_UPDATES",
                "meta": meta
            }
        
        # Analyze thread context if available
        self._analyze_thread_context(meta)
        
        # Classify the email
        classified_results = self.classifier.classify_email(meta)
        
        # Extract classification results
        is_promo = classified_results["is_promotional"]
        promo_score = classified_results["promo_score"]
        sbert_promo_score = classified_results["sbert_promo_score"]
        sbert_importance_score = classified_results.get("sbert_importance_score", 0)
        combined_promo_score = classified_results["combined_promo_score"]
        reasons = classified_results["reasons"]
        is_important = classified_results.get("is_important", False)
        importance_score = classified_results.get("importance_score", 0)
        importance_reasons = classified_results.get("importance_reasons", [])
        
        # Apply context override if applicable
        is_promo = self._apply_context_override(meta, is_promo, combined_promo_score, reasons)
        
        action = "Labelled as Promotion" if is_promo else "Kept"
        
        return {
            "message_id": message_id,
            "is_promo": is_promo,
            "promo_score": promo_score,
            "sbert_promo_score": sbert_promo_score,
            "sbert_importance_score": sbert_importance_score,
            "combined_promo_score": combined_promo_score,
            "is_important": is_important,
            "importance_score": importance_score,
            "importance_reasons": importance_reasons,
            "reasons": reasons,
            "action": action,
            "meta": meta
        }
    
    def _analyze_thread_context(self, meta: Dict[str, Any]) -> None:
        """
        Analyze thread context for an email if context analyzer is available.
        
        Args:
            meta: Email metadata to enhance with context information
        """
        if not self.context_analyzer or not meta.get("threadId"):
            return
        
        try:
            thread_analysis = self.context_analyzer.analyze_thread(meta.get("threadId"))
            if thread_analysis.get("is_important"):
                meta["thread_important"] = True
                meta["user_replied"] = thread_analysis.get("user_replied", False)
        except Exception as e:
            # Log error but continue without thread analysis
            print(f"Error analyzing thread for {meta.get('id', 'unknown')}: {e}")
    
    def _apply_context_override(self, 
                               meta: Dict[str, Any], 
                               is_promo: bool, 
                               combined_promo_score: float, 
                               reasons: List[str]) -> bool:
        """
        Apply context-based override to promotional classification.
        
        Args:
            meta: Email metadata
            is_promo: Current promotional classification
            combined_promo_score: Combined promotional score
            reasons: List of classification reasons
            
        Returns:
            Updated promotional classification
        """
        # If context indicates importance but classifier thinks it's promotional
        # and the score is close to the threshold, prioritize context
        if (meta.get("context_important") or meta.get("thread_important")) and is_promo:
            if combined_promo_score < (self.classifier.promo_threshold + 0.1):
                reasons.append("Overridden by context: You interact with this sender regularly")
                return False
        
        return is_promo
    
    def _create_error_result(self, message_id: str, error_msg: str, meta: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a result structure for failed email processing.
        
        Args:
            message_id: Email message ID
            error_msg: Error message
            meta: Email metadata
            
        Returns:
            Error result dictionary
        """
        return {
            "message_id": message_id,
            "is_promo": False,
            "promo_score": 0,
            "sbert_promo_score": 0,
            "sbert_importance_score": 0,
            "combined_promo_score": 0,
            "is_important": False,
            "importance_score": 0,
            "importance_reasons": [],
            "reasons": [f"Classification error: {error_msg}"],
            "action": "Error - Kept",
            "meta": meta
        }
    
    def _process_analysis_results(self, analysis_results: List[Dict[str, Any]], result: EmailProcessingResult) -> None:
        """
        Process analysis results and update the result object with statistics.
        
        Args:
            analysis_results: List of individual email analysis results
            result: Result object to update
        """
        for email_result in analysis_results:
            message_id = email_result.get("message_id", "")
            is_promo = email_result.get("is_promo", False)
            is_important = email_result.get("is_important", False)
            action = email_result.get("action", "")
            
            # Log the action
            self.logger.log_action(
                message_id=message_id,
                action=action,
                email_meta=email_result.get("meta", {}),
                promo_score=email_result.get("promo_score", 0),
                sbert_promo_score=email_result.get("sbert_promo_score", 0),
                sbert_importance_score=email_result.get("sbert_importance_score", 0),
                combined_promo_score=email_result.get("combined_promo_score", 0),
                reasons=email_result.get("reasons", []),
                importance_score=email_result.get("importance_score", 0),
                is_important=is_important,
                importance_reasons=email_result.get("importance_reasons", [])
            )
            
            # Update statistics
            if "CATEGORY_UPDATES" in action:
                result.skipped_count += 1
            elif "Error" in action:
                result.error_count += 1
                result.total_analyzed += 1  # Still count as analyzed
            else:
                result.total_analyzed += 1
                if is_promo:
                    result.promotional_count += 1
                    result.promotional_ids.append(message_id)
                if is_important:
                    result.important_count += 1
    
    def get_processing_summary(self, result: EmailProcessingResult) -> Dict[str, Any]:
        """
        Generate a summary of processing results.
        
        Args:
            result: Processing result object
            
        Returns:
            Dictionary with summary statistics
        """
        summary = {
            "total_retrieved": result.total_retrieved,
            "total_analyzed": result.total_analyzed,
            "promotional_count": result.promotional_count,
            "important_count": result.important_count,
            "skipped_count": result.skipped_count,
            "error_count": result.error_count,
            "processing_time": f"{result.processing_time:.2f}s",
            "promotional_rate": (result.promotional_count / max(result.total_analyzed, 1)) * 100,
            "important_rate": (result.important_count / max(result.total_analyzed, 1)) * 100,
        }        
        # Calculate conflicts (important emails marked as promotional)
        important_as_promo = sum(1 for r in result.results 
                               if r.get("is_important", False) and r.get("is_promo", False))
        summary["important_conflicts"] = important_as_promo
        
        return summary 
