# src/promo_classifier.py

"""
Specialized class for promotional email detection
"""

import time
import re
from src.config import config
from src.importance_classifier import ImportantClassifier
from src.utils import Utils

class PromoClassifier:
    """
    Specialized class for promotional email detection
    """
    
    def __init__(self, importance_classifier=None):
        # Use shared instance if provided, otherwise create new one
        if importance_classifier is not None:
            self.importance_classifier = importance_classifier
        else:
            self.importance_classifier = ImportantClassifier()
        self.important_keywords = config.CRITICAL_KEYWORDS
        self.critical_senders = config.CRITICAL_SENDERS
        self.whitelist = config.WHITELIST
        self.promotional_senders = config.PROMOTIONAL_SENDERS
        self.promotional_subjects = config.PROMOTIONAL_SUBJECTS
        self.promotional_patterns = config.PROMOTIONAL_PATTERNS
        self.transactional_patterns = config.TRANSACTIONAL_PATTERNS
        self.no_reply_patterns = config.NO_REPLY_PATTERNS
        
    def is_promo_email(self, meta):
        """
        Check if an email is promotional using advanced scoring with a
        balanced analysis between importance and promotional characteristics.
        """
        try:
            if not isinstance(meta, dict):
                print(f"Warning: meta is not a dictionary: {meta}")
                return False, 0, []
            
            # Extract email data
            extracted_data = self._extract_email_data(meta)
            
            # Check email importance level
            is_important, importance_score, importance_reasons = self.importance_classifier.is_important_email(meta)
            
            # Calculate promotional score
            promo_score, promo_reasons = self._calculate_promo_score(extracted_data)
            
            # Determine dynamic threshold for promotional score
            promo_threshold = self._determine_threshold(promo_reasons)
            
            # Round scores for clarity
            rounded_promo_score = round(promo_score, 1)
            rounded_importance_score = round(importance_score, 1)
            
            # Decision based on comparison of both scores
            reasons = []
            reasons.extend([f"Importance score : {rounded_importance_score}"])
            reasons.extend([f"Promo score : {rounded_promo_score}"])
            
            # 1. If importance is high, ignore promotional score
            if importance_score >= 6:
                is_promotional = False
                reasons.append("High importance score overrides promotional detection")
            # 2. If moderate but significant importance (>=3) and personal information present
            # Added condition on promotional score to avoid false positives
            elif importance_score >= 3 and any("personal" in reason.lower() for reason in importance_reasons) and promo_score < 8:
                is_promotional = False
                reasons.append("Contains personal information (likely important)")
            # 3. Check for replies to previous emails (non-promotional)
            elif self._is_reply_to_previous_email(extracted_data) and promo_score < 7.5:
                is_promotional = False
                reasons.append("Reply to previous email (likely important)")
            # 4. Check for senders with recent user interaction
            elif self._has_recent_interaction(extracted_data)[0] and promo_score < 7.0:
                is_promotional = False
                reasons.append("Recent interaction with sender")  
            # 5. If moderate importance but very high promotional score
            elif importance_score >= 3 and promo_score >= promo_threshold + 3:
                is_promotional = True
                reasons.append("Strong promotional indicators despite moderate importance")
            # 6. Enhanced detection of transactional emails (invoices, confirmations)
            elif self._is_likely_transactional(extracted_data)[0] and promo_score < 7:
                is_promotional = False
                reasons.append("Transactional email detected")
            # 7. Direct comparison based on ratio (with higher threshold)
            elif importance_score > 0:
                # Calculate ratio between scores with stricter threshold
                ratio = promo_score / importance_score
                is_promotional = ratio >= 2.0 and promo_score >= promo_threshold
                reasons.append(f"Promo/importance ratio: {round(ratio, 1)}")
            # 8. Standard decision based only on promotional score
            else:
                is_promotional = rounded_promo_score >= promo_threshold
                reasons.append(f"Score {rounded_promo_score} {'≥' if is_promotional else '<'} threshold {promo_threshold}")
            
            # Add some importance and promotional reasons for context
            if importance_reasons:
                reasons.append(f"Importance factors : {', '.join(importance_reasons[:2])}")
            if promo_reasons:
                reasons.append(f"Promo factors : {', '.join(promo_reasons[:2])}")
            
            return is_promotional, rounded_promo_score, reasons
                
        except Exception as e:
            print(f"Error in promotional email detection: {e}")
            return False, 0, [f"Error: {str(e)}"]

    def _extract_email_data(self, meta):
        """Extract and prepare email data for analysis."""
        # Get the basic data from Utils
        data = Utils.extract_email_data(meta)
        
        # Convert headers list to dictionary for easier access
        if isinstance(data["headers"], list):
            data["headers"] = self._extract_headers_dict(data["headers"])
        
        return data

    def _check_important_email(self, data):
        """Check if email is important and should never be marked as promotional."""
        # Check for critical senders
        for critical in self.critical_senders:
            if critical in data["sender"]:
                return True
        return False

    def _calculate_promo_score(self, data):
        """Calculate promotional score based on different factors."""
        score = 0
        reasons = []
        
        # Check for auto-generated emails
        if self._is_auto_generated_email(data["headers"], data["sender"], data["subject"]):
            score -= 2.0  # Strong penalty : auto-generated emails are rarely promotional
            reasons.append("Auto-generated email detected")
        
        # Check for transactional emails (high priority)
        is_transactional, transactional_reasons = self._is_likely_transactional(data)
        if is_transactional:
            score -= 2.0  # Score reduction for transactional emails
            reasons.extend(transactional_reasons)
        
        # Check if it's a reply to a previous email
        if self._is_reply_to_previous_email(data):
            score -= 2.5  # Strong penalty: replies are rarely promotional
            reasons.append("Reply to previous email")
        
        # Check for recent interactions
        has_interaction, interaction_reason = self._has_recent_interaction(data)
        if has_interaction:
            score -= 1.5
            reasons.append(interaction_reason)
        
        # Basic analysis with weighting
        basic_score, basic_reasons = self._analyze_basic_factors(data)
        score += basic_score
        reasons.extend(basic_reasons)

        # Headers analysis
        headers_score, headers_reasons = self._analyze_headers(data)
        score += headers_score
        reasons.extend(headers_reasons)
        
        # Regular expression analysis
        regex_score, regex_reasons = self._analyze_regular_expressions(data, self.promotional_patterns)
        score += regex_score
        reasons.extend(regex_reasons)
        
        # Semantic analysis
        semantic_score, semantic_reasons = self._analyze_semantic_content(data)
        score += semantic_score
        reasons.extend(semantic_reasons)
        
        # Emoji detection
        emoji_score, emoji_reasons = self._analyze_emojis(data)
        if emoji_score > 0:
            score += emoji_score
            reasons.extend(emoji_reasons)
        
        # Frequency and interaction analysis (with less weight since already checked)
        interaction_score, interaction_reasons = self._analyze_interaction(data)
        score += interaction_score * 0.7  # Reduce influence since we already checked interactions
        reasons.extend(interaction_reasons)
        
        # HTML analysis with improved metrics
        html_score, html_reasons = self._analyze_html_content(data["html_content"])
        score += min(3, html_score)  # Cap HTML score at 3 points
        reasons.extend(html_reasons[:2])  # Limit to 2 HTML reasons
        
        # Additional checks for common false positives
        # 1. Check for terms related to critical service emails
        critical_service_terms = self.critical_senders
        
        if any(term in data["subject"] or term in data["html_content"] for term in critical_service_terms):
            score -= 1.0
            reasons.append("Contains critical service terms")
        
        # Additional context check to avoid false negatives
        if score < 3 and any(promo_word in data["subject"] for promo_word in ["sale", "offer", "discount", "promo", "deal"]):
            score += 1.5
            reasons.append("Strong promotional terms in subject despite low score")
        
        # 2. Detection of employment or professional emails
        professional_terms = [
            "job", "career", "employment", "interview", "position", "application",
            "resume", "cv", "hiring", "recruitment", "salary", "benefits"
        ]
        
        if any(term in data["subject"] or term in data["html_content"] for term in professional_terms):
            score -= 1.5
            reasons.append("Professional/employment related content")
            
        # Check email priority
        email_priority = self._get_email_priority(data["headers"])
        if email_priority == "high":
            score -= 2.0
            reasons.append("High priority email")
        elif email_priority == "low":
            score += 0.5
            reasons.append("Low priority email")
        
        return score, reasons

    def _analyze_basic_factors(self, data):
        """Analyze basic factors to determine if an email is promotional."""
        score = 0
        reasons = []
        
        # Check sender for promotional indicators
        sender_score = 0
        for promo_sender in self.promotional_senders:
            if promo_sender in data["sender"]:
                sender_score += 2
                reasons.append(f"Promotional sender: {promo_sender}")
                break
        
        # Check for no-reply addresses (common in promotional emails)
        if any(pattern in data["sender"] for pattern in self.no_reply_patterns):
            sender_score += 1.5
            reasons.append("No-reply sender address")
        
        score += sender_score
        
        # Check subject for promotional keywords
        subject_score = 0
        found_keywords = []
        for keyword in self.promotional_subjects:
            if keyword in data["subject"]:
                subject_score += 1.5
                found_keywords.append(keyword)
                if len(found_keywords) >= 3:  # Limit to avoid excessive scoring
                    break
        
        if found_keywords:
            reasons.append(f"Promotional keywords in subject: {', '.join(found_keywords[:3])}")
        
        score += min(subject_score, 4.5)  # Cap subject score
        
        # Check for promotional patterns in subject
        pattern_score = 0
        for pattern in self.promotional_patterns:
            if re.search(pattern, data["subject"], re.IGNORECASE):
                pattern_score += 1
                reasons.append("Promotional pattern in subject")
                break
        
        score += pattern_score
        
        # Check for unsubscribe links (strong promotional indicator)
        if "unsubscribe" in data["html_content"] or "désabonner" in data["html_content"]:
            score += 2
            reasons.append("Unsubscribe link detected")
        
        # Check for marketing tracking
        tracking_patterns = [
            r"utm_source", r"utm_medium", r"utm_campaign",
            r"mailchimp", r"sendgrid", r"mailjet", r"constant.contact"
        ]
        
        for pattern in tracking_patterns:
            if re.search(pattern, data["html_content"], re.IGNORECASE):
                score += 1.5
                reasons.append("Email tracking detected")
                break
        
        return score, reasons

    def _analyze_regular_expressions(self, data, promo_patterns):
        """Analyze content with regular expressions to detect promotional patterns."""
        score = 0
        reasons = []
        pattern_matches = 0
        
        # Combine subject and content for analysis
        combined_text = data["subject"] + " " + data["html_content"]
        
        for pattern in promo_patterns:
            try:
                if re.search(pattern, combined_text, re.IGNORECASE):
                    pattern_matches += 1
                    if pattern_matches <= 3:  # Limit reasons to avoid spam
                        reasons.append(f"Promotional pattern detected")
            except re.error:
                continue
        
        # Score based on number of pattern matches
        if pattern_matches >= 3:
            score += 3
        elif pattern_matches >= 2:
            score += 2
        elif pattern_matches >= 1:
            score += 1
        
        if pattern_matches > 0:
            reasons.append(f"{pattern_matches} promotional patterns found")
        
        return score, reasons

    def _analyze_semantic_content(self, data):
        """Semantic analysis of email content to detect promotional keywords."""
        score = 0
        reasons = []
        
        # Combine subject and content
        combined_text = data["subject"] + " " + data["html_content"]
        
        # Count promotional keywords
        promo_keyword_count = 0
        found_keywords = []
        
        for keyword in self.promotional_subjects:
            if keyword in combined_text:
                promo_keyword_count += 1
                found_keywords.append(keyword)
                if len(found_keywords) >= 5:  # Limit collection
                    break
        
        # Score based on keyword density
        if promo_keyword_count >= 5:
            score += 3
            reasons.append(f"High promotional keyword density: {promo_keyword_count} keywords")
        elif promo_keyword_count >= 3:
            score += 2
            reasons.append(f"Moderate promotional keyword density: {promo_keyword_count} keywords")
        elif promo_keyword_count >= 1:
            score += 1
            reasons.append(f"Some promotional keywords found: {promo_keyword_count} keywords")
        
        # Check for call-to-action phrases
        cta_phrases = [
            "click here", "cliquez ici", "buy now", "achetez maintenant",
            "shop now", "order now", "commandez maintenant", "learn more",
            "en savoir plus", "sign up", "inscrivez-vous", "subscribe",
            "abonnez-vous", "download", "télécharger"
        ]
        
        cta_count = 0
        for phrase in cta_phrases:
            if phrase in combined_text:
                cta_count += 1
        
        if cta_count >= 2:
            score += 2
            reasons.append(f"Multiple call-to-action phrases: {cta_count}")
        elif cta_count >= 1:
            score += 1
            reasons.append("Call-to-action phrases detected")
        
        # Check for urgency/scarcity language
        urgency_phrases = [
            "limited time", "temps limité", "hurry", "dépêchez-vous",
            "expires", "expire", "last chance", "dernière chance",
            "only", "seulement", "today only", "aujourd'hui seulement"
        ]
        
        urgency_count = 0
        for phrase in urgency_phrases:
            if phrase in combined_text:
                urgency_count += 1
        
        if urgency_count >= 2:
            score += 1.5
            reasons.append("Multiple urgency indicators")
        elif urgency_count >= 1:
            score += 1
            reasons.append("Urgency language detected")
        
        # Check for discount/price mentions
        price_patterns = [
            r'\d+%\s*off', r'\d+%\s*de\s*remise',
            r'save\s+\$?\d+', r'économisez\s+\d+',
            r'free\s+shipping', r'livraison\s+gratuite',
            r'\$\d+', r'\d+\s*€', r'price', r'prix'
        ]
        
        price_mentions = 0
        for pattern in price_patterns:
            if re.search(pattern, combined_text, re.IGNORECASE):
                price_mentions += 1
        
        if price_mentions >= 2:
            score += 2
            reasons.append("Multiple price/discount mentions")
        elif price_mentions >= 1:
            score += 1
            reasons.append("Price/discount mentions detected")
        
        return score, reasons

    def _contains_emoji(self, text):
        """Detect emojis in text."""
        # Common Unicode ranges for emojis
        emoji_ranges = [
            (0x1F600, 0x1F64F),  # Emoticons
            (0x1F300, 0x1F5FF),  # Symbols & pictographs
            (0x1F680, 0x1F6FF),  # Transport & symbols
            (0x1F700, 0x1F77F),  # Alchemical Symbols
            (0x1F780, 0x1F7FF),  # Geometric Shapes
            (0x1F800, 0x1F8FF),  # Supplemental Arrows-C
            (0x1F900, 0x1F9FF),  # Supplemental Symbols and Pictographs
            (0x1FA00, 0x1FA6F),  # Chess Symbols
            (0x1FA70, 0x1FAFF),  # Symbols and Pictographs Extended-A
            (0x2600, 0x26FF),    # Miscellaneous Symbols
            (0x2700, 0x27BF),    # Dingbats
        ]
        
        emoji_count = 0
        for char in text:
            for start, end in emoji_ranges:
                if start <= ord(char) <= end:
                    emoji_count += 1
                    break
        
        return emoji_count

    def _analyze_emojis(self, data):
        """Analyze emoji presence in email."""
        score = 0
        reasons = []
        
        # Check emojis in subject
        subject_emojis = self._contains_emoji(data["subject"])
        
        # Check emojis in content (first 1000 chars)
        content_sample = data["html_content"][:1000] if data["html_content"] else ""
        content_emojis = self._contains_emoji(content_sample)
        
        total_emojis = subject_emojis + content_emojis
        
        if total_emojis >= 3:
            score += 2
            reasons.append(f"Multiple emojis detected: {total_emojis}")
        elif total_emojis >= 1:
            score += 1
            reasons.append(f"Emojis detected: {total_emojis}")
        
        return score, reasons

    def _analyze_headers(self, data):
        """Analyze email headers for promotional indicators."""
        score = 0
        reasons = []
        
        headers = data["headers"]
        
        # Check for marketing headers
        marketing_headers = [
            "list-unsubscribe", "list-id", "precedence", "x-mailer",
            "x-campaign", "x-mailgun", "x-sendgrid", "x-mailchimp"
        ]
        
        found_headers = []
        for header in marketing_headers:
            if header in headers:
                found_headers.append(header)
        
        if len(found_headers) >= 2:
            score += 2
            reasons.append(f"Multiple marketing headers: {len(found_headers)}")
        elif len(found_headers) >= 1:
            score += 1
            reasons.append("Marketing headers detected")
        
        # Check for bulk mail indicators
        if headers.get("precedence") == "bulk":
            score += 1.5
            reasons.append("Bulk mail precedence")
        
        return score, reasons

    def _analyze_interaction(self, data):
        """Analyze interactions with email (reading, age)."""
        score = 0
        reasons = []
        
        # Check if email is in UNREAD state (promotional emails often remain unread)
        if "UNREAD" in data["labels"]:
            score += 0.5
            reasons.append("Email is unread")
        
        # Check email age (older emails are less likely to be promotional if still in inbox)
        try:
            current_time = int(time.time() * 1000)
            internal_date = data["internal_date"]
            
            # Ensure internal_date is an integer
            if isinstance(internal_date, str):
                try:
                    internal_date = int(internal_date)
                except (ValueError, TypeError):
                    internal_date = current_time  # Default to current time if conversion fails
            
            email_age_hours = (current_time - internal_date) / (60 * 60 * 1000)
            
            if email_age_hours > 168:  # More than a week old
                score -= 0.5
                reasons.append("Email is more than a week old")
        except:
            pass
        
        return score, reasons

    def _analyze_html_content(self, html_content):
        """Analyze HTML content for promotional characteristics."""
        score = 0
        reasons = []
        
        if not html_content:
            return score, reasons
        
        # Count images (promotional emails often have many images)
        img_count = html_content.count("<img")
        if img_count >= 5:
            score += 2
            reasons.append(f"Many images: {img_count}")
        elif img_count >= 2:
            score += 1
            reasons.append(f"Multiple images: {img_count}")
        
        # Count links (promotional emails often have many links)
        link_count = html_content.count("href=")
        if link_count >= 10:
            score += 2
            reasons.append(f"Many links: {link_count}")
        elif link_count >= 5:
            score += 1
            reasons.append(f"Multiple links: {link_count}")
        
        # Check for tables (often used in promotional email layouts)
        table_count = html_content.count("<table")
        if table_count >= 3:
            score += 1.5
            reasons.append("Complex table layout")
        elif table_count >= 1:
            score += 0.5
            reasons.append("Table layout detected")
        
        # Check for CSS styles (promotional emails often heavily styled)
        style_indicators = ["style=", "<style", "background-color", "font-family", "text-align"]
        style_count = sum(html_content.count(indicator) for indicator in style_indicators)
        
        if style_count >= 10:
            score += 1.5
            reasons.append("Heavy styling detected")
        elif style_count >= 5:
            score += 1
            reasons.append("Moderate styling detected")
        
        # Check for tracking pixels
        tracking_patterns = [
            r'width="1".*height="1"', r'height="1".*width="1"',
            r'1x1\.gif', r'pixel\.gif', r'tracking\.gif'
        ]
        
        for pattern in tracking_patterns:
            if re.search(pattern, html_content, re.IGNORECASE):
                score += 1.5
                reasons.append("Tracking pixel detected")
                break
        
        # Check for social media buttons
        social_patterns = [
            "facebook", "twitter", "instagram", "linkedin", "youtube",
            "social", "follow us", "suivez-nous"
        ]
        
        social_count = sum(1 for pattern in social_patterns if pattern in html_content.lower())
        if social_count >= 3:
            score += 1
            reasons.append("Social media integration")
        
        return score, reasons

    def _analyze_html_content(self, html_content):
        """HTML content analysis for promotional characteristics."""
        score = 0
        reasons = []
        
        if not html_content:
            return score, reasons
        
        # Text-to-HTML ratio (promotional emails have low ratios)
        text_ratio = self._calculate_text_to_html_ratio(html_content)
        if text_ratio < 0.3:  # Very low ratio = heavily formatted
            score += 2.5
            reasons.append(f"Low text-to-HTML ratio ({text_ratio:.2f}) - heavily formatted")
        elif text_ratio < 0.5:  # Low ratio
            score += 1.5
            reasons.append(f"Low text-to-HTML ratio ({text_ratio:.2f})")
        elif text_ratio > 0.8:  # High ratio = mostly text
            score -= 1.0
            reasons.append(f"High text-to-HTML ratio ({text_ratio:.2f}) - mostly text")
        
        # Count promotional elements
        promo_elements = self._count_promotional_elements(html_content)
        
        # Analyze promotional words
        if promo_elements['promotional_words'] >= 10:
            score += 2.0
            reasons.append(f"Many promotional words ({promo_elements['promotional_words']})")
        elif promo_elements['promotional_words'] >= 5:
            score += 1.0
            reasons.append(f"Multiple promotional words ({promo_elements['promotional_words']})")
        
        # Analyze buttons (buy now, shop now, etc.)
        if promo_elements['buttons'] >= 3:
            score += 2.0
            reasons.append(f"Multiple promotional buttons ({promo_elements['buttons']})")
        elif promo_elements['buttons'] >= 1:
            score += 1.0
            reasons.append(f"Promotional buttons detected ({promo_elements['buttons']})")
        
        # Count images (promotional emails often have many images)
        img_count = promo_elements['images']
        if img_count >= 5:
            score += 2
            reasons.append(f"Many images: {img_count}")
        elif img_count >= 2:
            score += 1
            reasons.append(f"Multiple images: {img_count}")
        
        # Count links (promotional emails often have many links)
        link_count = promo_elements['links']
        if link_count >= 10:
            score += 2
            reasons.append(f"Many links: {link_count}")
        elif link_count >= 5:
            score += 1
            reasons.append(f"Multiple links: {link_count}")
        
        # Check for tables (often used in promotional email layouts)
        table_count = html_content.count("<table")
        if table_count >= 3:
            score += 1.5
            reasons.append("Complex table layout")
        elif table_count >= 1:
            score += 0.5
            reasons.append("Table layout detected")
        
        # Check for CSS styles (promotional emails often heavily styled)
        style_indicators = ["style=", "<style", "background-color", "font-family", "text-align"]
        style_count = sum(html_content.count(indicator) for indicator in style_indicators)
        
        if style_count >= 10:
            score += 1.5
            reasons.append("Heavy styling detected")
        elif style_count >= 5:
            score += 1
            reasons.append("Moderate styling detected")
        
        # Check for tracking pixels
        tracking_patterns = [
            r'width="1".*height="1"', r'height="1".*width="1"',
            r'1x1\.gif', r'pixel\.gif', r'tracking\.gif'
        ]
        
        for pattern in tracking_patterns:
            if re.search(pattern, html_content, re.IGNORECASE):
                score += 1.5
                reasons.append("Tracking pixel detected")
                break
        
        # Check for social media buttons
        social_patterns = [
            "facebook", "twitter", "instagram", "linkedin", "youtube",
            "social", "follow us", "suivez-nous"
        ]
        
        social_count = sum(1 for pattern in social_patterns if pattern in html_content.lower())
        if social_count >= 3:
            score += 1
            reasons.append("Social media integration")
        
        return score, reasons

    def _determine_threshold(self, reasons):
        """Determine dynamic threshold for promotional classification."""
        # Base threshold
        base_threshold = 6.0
        
        # Adjust based on number of different reason types (diversity of indicators)
        reason_types = len(set(reasons))
        threshold_adjustment = min(1.0, reason_types * 0.2)
        
        # Adjust based on strong indicators
        strong_indicators = [
            "Unsubscribe link detected",
            "Email tracking detected", 
            "Promotional sender",
            "Newsletter/digest detected",
            "Gmail promotional label detected"
        ]
        
        strong_count = sum(1 for indicator in strong_indicators if any(indicator in r for r in reasons))
        
        # Lower threshold if strong indicators are present
        if strong_count >= 2:
            threshold_adjustment += 1.0
        elif strong_count == 1:
            threshold_adjustment += 0.5
        
        # Calculate final threshold
        final_threshold = max(3.0, base_threshold - threshold_adjustment)
        
        return final_threshold

    def _is_reply_to_previous_email(self, data):
        """Determine if email is a reply to a previous email."""
        # Check subject for reply indicators
        reply_patterns = ["re:", "fwd:", "fw:", "tr:", "réf:", "rép:"]
        subject_lower = data["subject"].lower()
        
        for pattern in reply_patterns:
            if subject_lower.startswith(pattern):
                return True
        
        # Check headers for reply indicators
        headers = data["headers"]
        if headers.get("in-reply-to") or headers.get("references"):
            return True
        
        return False
        
    def _has_recent_interaction(self, data):
        """
        Check if the sender has had recent interactions.
        This function is a simplification and could be improved
        with a real interaction history.
        """
        # Simplification: check certain keywords that indicate an ongoing conversation
        conversation_indicators = ["as discussed", "as mentioned", "as requested", "following up", 
                                  "thank you for", "thanks for", "in response to", 
                                  "comme convenu", "comme mentionné", "suite à notre", 
                                  "merci pour", "en réponse à"]
                                  
        if "html_content" in data and data["html_content"]:
            content = data["html_content"].lower()
            for indicator in conversation_indicators:
                if indicator in content:
                    return True, f"Conversation indicator in content: {indicator}"
                
        if "subject" in data and data["subject"]:
            for indicator in conversation_indicators:
                if indicator in data["subject"].lower():
                    return True, f"Conversation indicator in subject: {indicator}"
                
        return False, ""
        
    def _is_likely_transactional(self, data):
        """
        Detect if the email is likely a transactional email
        (order confirmation, invoice, shipping, etc.)
        """
        reasons = []
        
        # Extract subject and sender for analysis
        subject = data["subject"].lower()
        sender = data["sender"].lower()
        
        # Check if sender contains a protected service
        for service in config.PROTECTED_SERVICES:
            if service in sender:
                reasons.append(f"Protected service detected in sender: {service}")
                break
        
        # Detect confirmation patterns
        transactional_patterns = config.TRANSACTIONAL_PATTERNS
        
        # Analysis of confirmation patterns
        for pattern in transactional_patterns:
            try:
                if re.search(pattern, subject, re.IGNORECASE):
                    reasons.append("Transactional email pattern detected in subject")
                    break
            except Exception as e:
                print(f"Error in transactional pattern {pattern}: {e}")
        
        # If we have html_content, also check for transactional keywords
        if "html_content" in data and data["html_content"]:
            html_content = data["html_content"].lower()[:5000]  # Limit for performance
            
            # Keywords specific to transactional emails
            transactional_keywords = [
                "confirmation", "confirmed", "receipt", "invoice", "order #",
                "shipping", "delivery", "delivered", "tracking", "payment",
                "transaction", "receipt", "facture", "reçu", "livraison",
                "votre commande", "your order", "order status", "payment received",
                "reservation", "booking", "appointment", "rendez-vous",
                "authorized", "authentication", "verified", "security",
                "account status", "subscription", "service", "update"
            ]
            
            for keyword in transactional_keywords:
                if keyword in html_content:
                    reasons.append(f"Transactional keyword detected in content: {keyword}")
                    break
        
        # Check popular service names as well
        popular_services = self.promotional_senders
        
        # Special check for critical emails (high priority)
        critical_indicators = self.critical_senders
        
        for indicator in critical_indicators:
            if indicator in subject or (data.get("html_content") and indicator in data["html_content"][:1000]):
                reasons.append(f"Critical content detected : {indicator}")
                break
        
        # Check service providers
        for provider in popular_services:
            if provider in sender:
                reasons.append(f"Promotional service: {provider}")
                break
        
        # Check if it's a confirmation with order/reference number
        order_number_pattern = r"(order|commande|ref|reference|référence|transaction|invoice|facture|ticket|billet)[-\s]*(#|n[o°]|:|\s)[-\s]*[a-zA-Z0-9]{3,}"
        if re.search(order_number_pattern, subject, re.IGNORECASE) or (
            "html_content" in data and data["html_content"] and 
            re.search(order_number_pattern, data["html_content"][:1000], re.IGNORECASE)
        ):
            reasons.append("Order/reference number detected")
        
        # Return result with reasons
        is_transactional = len(reasons) > 0
        
        return is_transactional, reasons

    def _is_auto_generated_email(self, headers, sender, subject):
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

    def _get_email_priority(self, headers):
        """
        Determine the priority of an email based on headers.
        
        Args:
            headers: Email headers dictionary
            
        Returns:
            str: 'high', 'normal', or 'low'
        """
        # Check priority-related headers
        priority_headers = [
            'x-priority', 'priority', 'importance', 'x-msmail-priority'
        ]
        
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
        
        return 'normal'  # Default priority
    
    def _calculate_text_to_html_ratio(self, html_content):
        """
        Calculate the ratio of text content to HTML markup.
        High ratios suggest content-heavy emails, low ratios suggest design-heavy emails.
        
        Args:
            html_content: HTML content of the email
            
        Returns:
            float: Ratio of text length to HTML length (0.0 to 1.0)
        """
        if not html_content:
            return 0.0
        
        # Extract text content
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html_content, 'html.parser')
            text_content = soup.get_text()
            
            text_length = len(text_content.strip())
            html_length = len(html_content)
            
            if html_length == 0:
                return 0.0
            
            return min(1.0, text_length / html_length)
            
        except Exception:
            # Fallback: simple text extraction
            import re
            text_without_tags = re.sub(r'<[^>]+>', '', html_content)
            text_length = len(text_without_tags.strip())
            html_length = len(html_content)
            
            return min(1.0, text_length / html_length) if html_length > 0 else 0.0
    
    def _count_promotional_elements(self, html_content):
        """
        Count promotional elements in HTML content.
        
        Args:
            html_content: HTML content to analyze
            
        Returns:
            dict: Dictionary with counts of promotional elements
        """
        if not html_content:
            return {'images': 0, 'links': 0, 'buttons': 0, 'promotional_words': 0}
        
        content_lower = html_content.lower()
        
        # Count images
        image_count = content_lower.count('<img')
        
        # Count links
        link_count = content_lower.count('href=')
        
        # Count promotional buttons
        button_patterns = [
            r'<(?:button|input)[^>]*(?:type=["\']?(?:button|submit)["\']?)[^>]*>',
            r'<a[^>]*class=["\'][^"\']*(?:button|btn)[^"\']*["\'][^>]*>',
            r'<[^>]*(?:shop|buy|purchase|order)\s+now[^>]*>',
        ]
        
        button_count = 0
        for pattern in button_patterns:
            button_count += len(re.findall(pattern, html_content, re.IGNORECASE))
        
        # Count promotional words
        promotional_words = [
            'sale', 'discount', 'offer', 'deal', 'promotion', 'special',
            'limited', 'exclusive', 'free', 'save', 'buy now', 'shop now'
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
        
    def _extract_headers_dict(self, headers):
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