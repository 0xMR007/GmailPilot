# src/importance_classifier.py

"""
Specialized class for important email detection with scoring system
"""

import time
import re
from src.config import config
from src.sbert_classifier import SBertClassifier
from src.utils import Utils

class ImportantClassifier:
    """
    Specialized class for important email detection with scoring system
    """
    
    def __init__(self, sbert_classifier=None):
        self.critical_keywords = config.CRITICAL_KEYWORDS
        self.critical_senders = config.CRITICAL_SENDERS
        self.response_patterns = config.RESPONSE_PATTERNS
        self.no_reply_patterns = config.NO_REPLY_PATTERNS
        self.whitelist = config.WHITELIST
        # Get promotional indicators to check against
        self.promotional_subjects = config.PROMOTIONAL_SUBJECTS
        self.promotional_senders = config.PROMOTIONAL_SENDERS
        self.promotional_patterns = config.PROMOTIONAL_PATTERNS
        self.promotional_penalty = config.PROMOTIONAL_PENALTY
        # Use threshold from config
        self.importance_threshold = config.IMPORTANCE_THRESHOLD
        # Initialize SBERT classifier for importance predictions - use shared instance if provided
        if sbert_classifier is not None:
            self.sbert_classifier = sbert_classifier
        else:
            self.sbert_classifier = SBertClassifier()
        # Weight for SBERT importance prediction (can be adjusted in config)
        self.sbert_weight = config.SBERT_WEIGHT

    def is_important_email(self, meta):
        """
        Determines if an email is important using weighted scoring.
        """
        try:
            if not isinstance(meta, dict):
                print(f"Warning: meta is not a dictionary: {meta}")
                return False, 0, []
            
            # Extract email data using centralized method
            extracted_data = Utils.extract_email_data(meta)
            
            # Check whitelist (priority)
            whitelist_check_result, whitelist_reason = self._check_whitelist(extracted_data)
            if whitelist_check_result:
                return True, 10, [whitelist_reason]
            
            # Early skip for very obvious important emails
            sender = extracted_data["sender"]
            subject = extracted_data["subject"]
            
            # Check for critical security/banking senders
            if any(domain in sender for domain in self.critical_senders):
                if any(keyword in subject for keyword in self.critical_keywords):
                    return True, 9.5, ["Critical security email - early skip"]
            
            # Calculate importance score
            score, reasons = self._calculate_importance_score(extracted_data)
            
            # Add SBERT score if available
            sbert_score, sbert_reasons = self._get_sbert_importance_score(meta)
            if sbert_score is not None:
                # Adjust SBERT weight based on confidence
                score = (score * (1 - self.sbert_weight)) + (sbert_score * self.sbert_weight * 10)  # Multiply by 10 since SBERT score is between 0-1
                reasons.extend(sbert_reasons)
            
            # Check if email is potentially promotional
            promo_indicators, promo_reasons = self._check_promotional_indicators(extracted_data)
            
            # Apply penalty to importance score if promotional indicators are detected
            if promo_indicators > 0:
                penalty = min(promo_indicators * self.promotional_penalty, 5.0)  # Cap at 5 points penalty
                score -= penalty
                reasons.append(f"Promotional indicators detected: -{penalty:.1f} points")
                reasons.extend(promo_reasons[:2])  # Add main reasons
            
            # Determine threshold - now only as reference
            dynamic_threshold = self._determine_threshold(reasons)
            
            rounded_score = round(score, 1)
            is_important = rounded_score >= dynamic_threshold
            
            if is_important:
                reasons.append(f"Score {rounded_score} >= threshold {dynamic_threshold}")
            else:
                reasons.append(f"Score {rounded_score} < threshold {dynamic_threshold}")
            
            return is_important, rounded_score, reasons
            
        except Exception as e:
            print(f"Error in importance classification: {e}")
            return False, 0, [f"Error: {str(e)}"]
        
    def _check_whitelist(self, data):
        """Check if sender is in whitelist."""
        if any(w in data["sender"] for w in self.whitelist):
            return True, "Whitelisted sender"
        
        return False, ""

    def _calculate_importance_score(self, data):
        """Calculate importance score based on different factors."""
        score = 0
        reasons = []
        
        # 1. Sender analysis (max 3 points)
        sender_score, sender_reasons = self._analyze_sender(data)
        score += sender_score
        reasons.extend(sender_reasons)
        
        # 2. Subject analysis (max 3 points)
        subject_score, subject_reasons = self._analyze_subject(data)
        score += subject_score
        reasons.extend(subject_reasons)
        
        # 3. Recipients analysis (max 2 points)
        recipients_score, recipients_reasons = self._analyze_recipients(data)
        score += recipients_score
        reasons.extend(recipients_reasons)
        
        # 4. Attachment analysis (max 3 points)
        if data["has_attachments"]:
            score += 3
            reasons.append("Email has attachments")
        
        # 5. Gmail labels analysis (max 5 points)
        if "IMPORTANT" in data["labels"]:
            score += 5
            reasons.append("Gmail labeled as IMPORTANT")
        
        # 6. Headers analysis (max 2 points)
        header_score, header_reasons = self._analyze_headers(data)
        score += header_score
        reasons.extend(header_reasons)
        
        # 7. Content analysis
        if data["html_content"]:
            semantic_score, semantic_reasons = self._analyze_semantic_relation(data)
            score += semantic_score

            content_score, content_reasons = self._analyze_content(data["html_content"])
            score += content_score
            
            reasons.extend(semantic_reasons)
            reasons.extend(content_reasons)
        
        # 8. Temporal analysis
        time_score, time_reasons = self._analyze_time_factors(data)
        score += time_score
        reasons.extend(time_reasons)
        
        # 9. Read status analysis
        read_score, read_reasons = self._analyze_read_status(data)
        score += read_score
        reasons.extend(read_reasons)
        
        return score, reasons

    def _analyze_sender(self, data):
        """Analyze sender to determine importance."""
        score = 0
        reasons = []
        
        # Check for critical senders
        for critical in self.critical_senders:
            if critical in data["sender"]:
                score += 3
                reasons.append(f"Critical sender: {critical}")
                return score, reasons  # Immediate return if critical sender found
        
        # Check if sender has full name
        if ">" in data["sender"] and data["sender"].split("<")[0].strip():
            score += 0.5
            
        return score, reasons

    def _analyze_subject(self, data):
        """Analyze subject to determine importance."""
        score = 0
        reasons = []
        
        # Check for critical keywords in subject
        subject_keywords = []
        for keyword in self.critical_keywords:
            if keyword in data["subject"]:
                subject_keywords.append(keyword)
                score += 3.5
                # Limit to maximum 3 different keywords to avoid excessive scores
                if len(set(subject_keywords)) >= 3:
                    break
        
        if subject_keywords:
            reasons.append(f"Critical keywords in subject : {', '.join(subject_keywords[:2])}")
        
        # Check if subject is a reply
        if any(pattern in data["subject"].lower() for pattern in self.response_patterns):
            score += 2
            reasons.append("Reply/Forward subject")
        
        # Detect importance terms in short messages
        if len(data["subject"]) < 50 and any(term in data["subject"].lower() for term in self.critical_keywords):
            # Check that there are no promotional terms as well
            if not any(term in data["subject"].lower() for term in self.promotional_subjects):
                score += 2.0
                reasons.append("Short subject with importance indicators")
            else:
                # Penalty for marketing subjects disguised as important messages
                score -= 1.0
                reasons.append("Marketing subject disguised as important message")

        # Detect false urgencies (urgency terms + promotional indications)
        marketing_alerts = [
            ("action required", ["confirm", "marketing", "preferences", "subscription", "newsletter"]),
            ("urgent", ["offer", "discount", "promo", "deal", "sale"]),
            ("important", ["offer", "news", "information", "update", "newsletter"]),
            ("last chance", []),
            ("ne manquez pas", []),
            ("limited time", []),
            ("expires", ["offer", "promotion", "discount"])
        ]
        
        subject_lower = data["subject"].lower()
        
        for alert_term, marketing_terms in marketing_alerts:
            if alert_term in subject_lower:
                # If it's a known alert term in marketing context
                if marketing_terms and any(term in subject_lower for term in marketing_terms):
                    score -= 3.0  # Very strong penalty for these specific combinations
                    reasons.append(f"False importance signal: '{alert_term}' in marketing context")
                    break
                # Or if it's a term strongly linked to marketing even without additional context
                elif not marketing_terms:
                    score -= 2.0  # Strong penalty for these marketing urgency terms without context
                    reasons.append(f"Marketing urgency trigger: '{alert_term}'")
                    break
            
        return score, reasons

    def _analyze_recipients(self, data):
        """Analyze recipients to determine importance."""
        score = 0
        reasons = []

        # Get destination address (to)
        to_address = data["to"]
        
        # Check if it's not a mass mailing
        if to_address and "@" in to_address and not any(common in to_address for common in ["undisclosed", "multiple", "recipients"]):
            score += 0.5
            reasons.append("Directly addressed to user")
            
        return score, reasons

    def _analyze_headers(self, data):
        """Analyze headers to determine importance."""
        score = 0
        reasons = []
        
        headers = data["headers"]
        
        # Check explicit priority
        if headers.get("x-priority") in ["1", "high", "urgent"]:
            score += 1.5
            reasons.append("High priority header")
        elif headers.get("importance") in ["high", "urgent"]:
            score += 1.5
            reasons.append("High importance header")
            
        # Check if it's a reply to a previous email
        if headers.get("in-reply-to") or headers.get("references"):
            score += 5
            reasons.append("Reply to previous email")
            
        return score, reasons

    def _analyze_content(self, html_content):
        """Analyze content to determine importance"""
        score = 0
        reasons = []
        
        # Limit content analysis size
        max_content_length = getattr(config, 'MAX_CONTENT_ANALYSIS_LENGTH', 5000)
        if len(html_content) > max_content_length:
            html_content = html_content[:max_content_length]
        
        # Look for critical keywords in content
        content_keywords = []
        html_lower = html_content.lower()
        for keyword in self.critical_keywords:
            if keyword.lower() in html_lower:
                content_keywords.append(keyword)
                score += 2
                # Limit to maximum 3 different keywords
                if len(set(content_keywords)) >= 3:
                    break
        
        if content_keywords:
            reasons.append("Critical keywords in content")
        
        # Quick content structure analysis
        img_count = html_content.count("<img")
        link_count = html_content.count("href=")
        
        if img_count <= 2 and link_count <= 5:
            score += 1
            reasons.append("Simple content structure")

        # Emoji detection
        emoji_sample = html_content[:min(1000, len(html_content) // 2)]
        emoji_count = self._contains_emoji(emoji_sample)
        if emoji_count > 3:
            score -= 2
            reasons.append("Multiple emojis detected (likely promotional)")
        elif emoji_count > 0:
            score -= 1.5

        # Personal info analysis
        if not getattr(config, 'SKIP_HEAVY_ANALYSIS_FOR_OBVIOUS_CASES', False):
            personal_info_score, personal_info_reasons = self._analyze_personal_info(html_content)
            score += personal_info_score
            reasons.extend(personal_info_reasons)
        else:
            # Quick check for obvious personal info indicators
            personal_indicators = ["numéro", "number", "client", "compte", "account"]
            if any(indicator in html_lower for indicator in personal_indicators):
                score += 1
                reasons.append("May contain personal information (quick check)")
                
        return score, reasons
    
    def _analyze_personal_info(self, html_content):
        """Analyze content to detect personal or sensitive information."""
        score = 0
        reasons = []
        detected_patterns = []
        
        # 1. Highly sensitive patterns (score +1.5)
        high_sensitivity_patterns = [
            # Identification information
            r"\bnum[ée]ro\s+(?:de\s+)?(?:client|adh[ée]rent|s[ée]curit[ée]\s+sociale|ss|compte)\s*:?\s*\w+",
            r"\bclient\s+(?:id|number|num[ée]ro)\s*:?\s*\w+",
            r"\bID\s+(?:client|adh[ée]rent|utilisateur)\s*:?\s*\w+",
            r"\b(?:votre|your)\s+num[ée]ro\s+(?:est|is|:)",
            
            # Banking information
            r"\biban\s*:?\s*\w+",
            r"\bcarte\s+bancaire",
            r"\bcredit\s+card",
            r"\bpaiement\s+de\s+\d+[,\.]\d+\s*(?:€|\$)",
            r"\bfacture\s+(?:de|du|d')\s+\d+[,\.]\d+\s*(?:€|\$)",

            # Government identifiers
            r"\bnum[ée]ro\s+(?:fiscal|de\s+s[ée]curit[ée]\s+sociale)",
        ]
        
        # 2. Moderately sensitive patterns (score +1)
        medium_sensitivity_patterns = [
            # Codes and references
            r"\bcode\s*:?\s*[A-Z0-9]{4,}",
            r"\br[ée]f[ée]rence\s*:?\s*[A-Z0-9]{4,}",
            r"\bdossier\s+(?:num[ée]ro|n[°o])\s*:?\s*[A-Z0-9]+",
            r"\bcontrat\s+(?:num[ée]ro|n[°o])\s*:?\s*[A-Z0-9]+",
            
            # Contact information
            r"\badresse\s*:(?:(?!\@).){5,50}", # Postal address (not email)
            r"\bt[ée]l[ée]phone\s*(?:fixe|mobile|portable)?\s*:?\s*(?:\+\d{1,4}[\s\.-]?)?(?:\(0\)|0)[1-9][\s\.-]?\d{2}[\s\.-]?\d{2}[\s\.-]?\d{2}[\s\.-]?\d{2}",
            
            # Important dates
            r"\b(?:date\s+(?:de|du|d')\s+naissance|birth\s+date)\s*:?\s*\d{1,2}[\/-]\d{1,2}[\/-]\d{2,4}",
            r"\b(?:expiration|expiry|validité)\s*:?\s*\d{1,2}[\/-]\d{2,4}",
        ]
        
        # 3. Mildly sensitive patterns (score +0.5)
        low_sensitivity_patterns = [
            # Reference numbers
            r"\b\d{6,}\b",  # Numbers with 6 digits or more (avoids years/simple amounts)
            r"\b[A-Z]{2,}\d{4,}\b",  # Letter-number combinations typical of references
            
            # Common formulations
            r"\bvos\s+(?:donn[ée]es|informations)\s+(?:personnelles|confidentielles)",
            r"\b(?:confidentiel|personnel)\b",
            r"\b(?:mise\s+[àa]\s+jour|update)\s+(?:de\s+vos|your)\s+(?:donn[ée]es|informations|coordonn[ée]es)",
        ]
        
        # Check highly sensitive patterns
        for pattern in high_sensitivity_patterns:
            if re.search(pattern, html_content, re.IGNORECASE):
                score += 1.5
                detected_patterns.append("high_sensitivity")
                break
        
        # Check moderately sensitive patterns  
        for pattern in medium_sensitivity_patterns:
            if re.search(pattern, html_content, re.IGNORECASE):
                score += 1.0
                detected_patterns.append("medium_sensitivity")
                break
                
        # Check mildly sensitive patterns
        for pattern in low_sensitivity_patterns:
            if re.search(pattern, html_content, re.IGNORECASE):
                score += 0.5
                detected_patterns.append("low_sensitivity")
                break
        
        # Add reasons with detail level
        if "high_sensitivity" in detected_patterns:
            reasons.append("May contains highly sensitive personal information")
        elif "medium_sensitivity" in detected_patterns:
            reasons.append("May contains personal information")
        elif "low_sensitivity" in detected_patterns:
            reasons.append("May contain personal information")
        
        return score, reasons

    def _analyze_time_factors(self, data):
        """Analyze temporal factors to determine importance."""
        score = 0
        reasons = []
        
        # Recent emails are potentially more important
        receipt_date = data["internal_date"]
        current_time = int(time.time() * 1000)
        
        # Ensure receipt_date is an integer
        if isinstance(receipt_date, str):
            try:
                receipt_date = int(receipt_date)
            except (ValueError, TypeError):
                receipt_date = current_time  # Default to current time if conversion fails
        
        hours_old = (current_time - receipt_date) / (60 * 60 * 1000)
        
        if hours_old < 24:
            score += 1
            reasons.append("Recent email (<24h)")
        else:
            score -= 1
            
        return score, reasons
    
    def _analyze_read_status(self, data):
        """Analyze read status to determine importance."""
        score = 0
        reasons = []
        
        # Check if email is unread
        labels = data.get("labels", [])
        is_unread = "UNREAD" in labels
        
        if is_unread:
            # Unread emails might be more important as they require attention
            score += 1.5
            reasons.append("Email is unread")
            
            # Additional scoring based on email age for unread emails
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
                
                if email_age_hours < 1:  # Very recent unread email
                    score += 1.0
                    reasons.append("Very recent unread email (<1h)")
                elif email_age_hours < 6:  # Recent unread email
                    score += 0.5
                    reasons.append("Recent unread email (<6h)")
                elif email_age_hours > 168:  # Old unread email (more than a week)
                    # Old unread emails might be less important (possibly spam/promotional)
                    score -= 2
                    reasons.append("Old unread email (>1 week)")
            except:
                pass  # Skip age analysis if there's an error
        else:
            # Read emails get a small penalty as they might be less urgent
            score -= 0.5
            reasons.append("Email has been read")
        
        return score, reasons
    
    def _determine_threshold(self, reasons):
        """Determine dynamic threshold for important classification."""
        # Base threshold
        base_threshold = self.importance_threshold
        
        # Adjustment based on number of different reasons (diversity of indicators)
        reason_types = len(set(reasons))
        threshold_adjustment = min(1.0, reason_types * 0.25)
        
        # Adjustment based on strong indicators
        strong_indicators = [
            "Reply to previous email",
            "Critical keywords in content",
            "High priority header",
            "High importance header",
            "Reply/Forward subject"
        ]

        strong_count = sum(1 for indicator in strong_indicators if any(indicator in r for r in reasons))
        
        # Reduce threshold if strong indicators are present
        if strong_count >= 2:
            threshold_adjustment -= 1.0
        elif strong_count == 1:
            threshold_adjustment -= 0.5

        # Calculate final threshold
        final_threshold = max(2.0, base_threshold - threshold_adjustment)
        
        return final_threshold


    def _analyze_semantic_relation(self, data):
        """Analyze semantic relationship between subject and content to detect divergence between them."""
        score = 0
        reasons = []
        
        # Subject mentions need for action but content is very promotional
        if data["html_content"] and re.search(r'(?:action|urgent|important|required|nécessaire)', data["subject"], re.IGNORECASE):
            # Check if content contains too many promotional elements
            promo_indicators = [
                r'(?:discount|sale|promo|offer|deal|remise|solde|promotion)',
                r'(?:buy|purchase|acheter|acheter maintenant|buy now)',
                r'(?:new collection|nouvelle collection|new arrival|nouveauté)',
                r'(?:limited time|édition limitée|offre limitée|limited offer)'
            ]
            
            content_promo_count = sum(1 for pattern in promo_indicators if re.search(pattern, data["html_content"], re.IGNORECASE))
            
            # If subject suggests important action but content is very promotional
            if content_promo_count >= 2:
                score += 2.0
                reasons.append("Misleading urgent subject with promotional content")
        
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

    def _check_promotional_indicators(self, data):
        """Check if email contains promotional indicators."""
        indicator_count = 0
        reasons = []
        
        # Check subject for promotional keywords
        subject = data.get("subject", "").lower()
        if subject:
            promo_keywords = [word for word in self.promotional_subjects 
                             if word.lower() in subject]
            if promo_keywords:
                indicator_count += len(promo_keywords)
                reasons.append(f"Promotional keywords in subject: {', '.join(promo_keywords[:3])}")
        
        # Check sender for promotional indicators
        sender = data.get("sender", "").lower()
        
        # Check if sender is a known promotional sending address
        for promo_sender in self.promotional_senders:
            if promo_sender in sender:
                indicator_count += 1
                reasons.append(f"Promotional sender detected: {promo_sender}")
                break
        
        # Search for promotional patterns in HTML content
        html_content = data.get("html_content", "").lower()
        if html_content:
            promo_pattern_matches = []
            for pattern in self.promotional_patterns:
                if re.search(pattern, html_content, re.IGNORECASE):
                    promo_pattern_matches.append(pattern)
                    if len(promo_pattern_matches) >= 3:  # Limit to 3 patterns
                        break
            
            if promo_pattern_matches:
                indicator_count += len(promo_pattern_matches)
                reasons.append(f"Promotional patterns detected in content: {len(promo_pattern_matches)} matches")
        
        # Detect unsubscribe links (strong promotional email indicator)
        unsubscribe_patterns = [
            r"(?:unsubscribe|désabonner|désinscrire|opt[- ]?out)",
            r"(?:manage|gérer).*(?:subscriptions|preferences|abonnements|préférences)",
            r"(?:view|voir).*(?:browser|navigateur)"
        ]
        
        for pattern in unsubscribe_patterns:
            if re.search(pattern, html_content, re.IGNORECASE):
                indicator_count += 1
                reasons.append("Unsubscribe link detected")
                break
        
        # Presence of tracking URLs (common in promotional emails)
        tracking_patterns = [
            r"(?:track|clic|click)\.[a-z0-9-]+\.[a-z]{2,}",
            r"(?:marketing|campaign|promo)[a-z0-9-]*\.[a-z]{2,}",
            r"(?:mailer|mailchimp|sendgrid|mailjet|newsletter)",
            r"utm_(?:source|medium|campaign|content|term)"
        ]
        
        for pattern in tracking_patterns:
            if re.search(pattern, html_content, re.IGNORECASE):
                indicator_count += 1
                reasons.append("Email tracking elements detected")
                break
                
        # Limit score to avoid extreme penalties
        return min(indicator_count, 5), reasons

    def _get_sbert_importance_score(self, meta):
        """Use SBERT to evaluate message importance."""
        if not self.sbert_classifier.model:
            return None, []
            
        try:
            # Get text to analyze
            subject = meta.get('subject', '')
            
            if not subject:
                return None, []
                
            # Prepare text for SBERT
            combined_text = subject
                
            # Get SBERT predictions
            predictions = self.sbert_classifier.predict(combined_text, k=2)
            
            # Important emails are indicated by the "important" class
            sbert_importance_score = 0
            reasons = []
            
            for label, prob in predictions:
                if label == "important":  # Use correct SBERT label format
                    sbert_importance_score = float(prob)
                    break
                    
            # If we don't have "important" class, use inverse of "promo" class
            if sbert_importance_score == 0:
                for label, prob in predictions:
                    if label == "promo":
                        sbert_importance_score = 1.0 - float(prob)  # Inverse of promotional score
                        break
            
            # Add reasoning based on score
            if sbert_importance_score > 0.8:
                reasons.append(f"SBERT: strongly indicates important content ({round(sbert_importance_score*100)}%)")
            elif sbert_importance_score > 0.6:
                reasons.append(f"SBERT: likely important content ({round(sbert_importance_score*100)}%)")
            elif sbert_importance_score > 0.4:
                reasons.append(f"SBERT: moderately important content ({round(sbert_importance_score*100)}%)")
                
            return sbert_importance_score, reasons
            
        except Exception as e:
            print(f"Error in SBERT importance scoring: {e}")
            return None, []