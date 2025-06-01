# src/hybrid_classifier.py

"""
Hybrid classifier combining SBERT and rule-based classification.
Now using SBERT for better semantic understanding.
"""

from src.sbert_classifier import SBertClassifier
from src.importance_classifier import ImportantClassifier
from src.promo_classifier import PromoClassifier
from src.config import config

class HybridClassifier:
    """
    Optimized hybrid classifier focusing on promotional email detection.
    Uses lazy loading and fast paths for better performance.
    """
    
    def __init__(self, fast_mode=False):
        # Core classifier - always initialized
        self._sbert_classifier = None
        self._important_classifier = None
        self._promo_classifier = None
        
        # Lazy loading for heavy components
        self._semantic_analyzer = None
        self._temporal_analyzer = None
        
        # Performance mode
        self.fast_mode = fast_mode
        
        # Configuration values
        self.sbert_weight = config.SBERT_WEIGHT
        self.rules_weight = config.RULES_WEIGHT
        self.promo_threshold = config.PROMO_THRESHOLD
        self.importance_threshold = config.IMPORTANCE_THRESHOLD
        
        # Enhanced parameters
        self.uncertainty_threshold = 0.05
        self.safety_margin = 0.12
        self.max_confidence_delta = 0.35
        
        # Check model status without loading
        self.is_model_loaded = self._check_model_status()
        
        # Attachment analysis patterns (lightweight initialization)
        self.important_attachment_types = {
            'application/pdf', 'application/msword', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            'application/vnd.ms-excel', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            'application/zip', 'application/x-zip-compressed', 'application/x-rar-compressed',
            'text/csv', 'text/plain'
        }
        
        self.promo_attachment_types = {
            'image/jpeg', 'image/png', 'image/gif', 'application/vnd.ms-powerpoint',
            'application/vnd.openxmlformats-officedocument.presentationml.presentation'
        }
        
        # Definition of important vs promotional extensions
        self.important_extensions = {
            '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.zip', '.rar', '.csv', '.txt'
        }
        
        self.promo_extensions = {
            '.jpg', '.jpeg', '.png', '.gif', '.ppt', '.pptx'
        }
        
    def _check_model_status(self):
        """Quick check if model exists without loading it"""
        import os
        return os.path.exists(config.MODEL_PATH)

    @property
    def sbert_classifier(self):
        """Lazy loading for SBERT classifier with automatic training if needed"""
        if self._sbert_classifier is None:
            self._sbert_classifier = SBertClassifier()
            # Check if model needs to be loaded or trained
            if not self._sbert_classifier.is_model_loaded:
                if getattr(config, 'VERBOSE_LOGGING', False):
                    print("🤖 SBERT model not found. Training a new model...")
                # Try to train the model automatically
                if self._sbert_classifier.train():
                    if getattr(config, 'VERBOSE_LOGGING', False):
                        print("✅ SBERT model trained and saved successfully")
                    self.is_model_loaded = True
                else:
                    if getattr(config, 'VERBOSE_LOGGING', False):
                        print("⚠️ Failed to train SBERT model. Running without AI classification.")
                    self.is_model_loaded = False
        return self._sbert_classifier

    @property
    def important_classifier(self):
        """Lazy loading for importance classifier"""
        if self._important_classifier is None:
            self._important_classifier = ImportantClassifier(sbert_classifier=self.sbert_classifier)
        return self._important_classifier

    @property
    def promo_classifier(self):
        """Lazy loading for promo classifier"""
        if self._promo_classifier is None:
            self._promo_classifier = PromoClassifier(importance_classifier=self.important_classifier)
        return self._promo_classifier

    @property
    def semantic_analyzer(self):
        """Lazy loading for semantic analyzer"""
        if self._semantic_analyzer is None and not self.fast_mode:
            from src.semantic_analyzer import SemanticAnalyzer
            self._semantic_analyzer = SemanticAnalyzer()
        return self._semantic_analyzer

    @property
    def temporal_analyzer(self):
        """Lazy loading for temporal analyzer"""
        if self._temporal_analyzer is None and not self.fast_mode:
            from src.temporal_analyzer import TemporalAnalyzer
            self._temporal_analyzer = TemporalAnalyzer()
        return self._temporal_analyzer
        
    def _load_or_train_model(self):
        """
        Loads the SBERT model if it exists, otherwise trains it with default parameters.
        """
        # Load model if it exists
        if self.is_model_loaded:
            if getattr(config, 'VERBOSE_LOGGING', False):
                print("✅ SBERT model loaded successfully")
            return True
        else:
            if getattr(config, 'VERBOSE_LOGGING', False):
                print("SBERT model not found, training a new one...")
            if self.sbert_classifier.train():
                if getattr(config, 'VERBOSE_LOGGING', False):
                    print("✅ SBERT model trained and saved")
                return True
            else:
                print("❌ Failed to train SBERT model")
                return False
        
    def analyze_attachments(self, meta):
        """
        Analyzes email attachments to deduce their impact on classification.
        
        Args:
            meta (dict): Email metadata containing attachment information
            
        Returns:
            float: Attachment score (positive for promotional, negative for important)
        """
        try:
            attachment_score = 0
            evidence = []
            
            # Check if email contains attachments
            has_attachments = meta.get('has_attachments', False)
            
            if not has_attachments:
                return attachment_score, evidence
            
            # Get attachment information if available
            attachments = meta.get('attachments', [])
            
            if not attachments:
                # If we know there are attachments but don't have details
                return 1, ["Has attachments (details unavailable)"]
            
            # Analyze each attachment
            for attachment in attachments:
                filename = attachment.get('filename', '').lower()
                mime_type = attachment.get('mimeType', '').lower()
                size = attachment.get('size', 0)
                
                # Check MIME type and extension
                if any(ext in filename for ext in ['.pdf', '.doc', '.docx', '.xls', '.xlsx']):
                    # Documents often indicate important content
                    attachment_score -= 0.3
                    evidence.append(f"Document attachment: {filename}")
                elif any(ext in filename for ext in ['.jpg', '.png', '.gif', '.jpeg']):
                    # Images often indicate promotional content
                    attachment_score += 0.2
                    evidence.append(f"Image attachment: {filename}")
                elif 'image' in mime_type:
                    attachment_score += 0.2
                    evidence.append(f"Image attachment (MIME: {mime_type})")
                
                # Additional analysis based on size and name
                if size > 1000000:  # > 1MB
                    # Large files often indicate important content
                    attachment_score -= 0.2
                    evidence.append(f"Large attachment: {filename} ({size} bytes)")
                
                # Analyze filename for promotional indicators
                promo_indicators = ['flyer', 'catalog', 'catalogue', 'promo', 'offer', 'deal']
                if any(indicator in filename for indicator in promo_indicators):
                    attachment_score += 0.4
                    evidence.append(f"Promotional attachment name: {filename}")
                
                # Analyze filename for important indicators
                important_indicators = ['invoice', 'facture', 'contract', 'contrat', 'report', 'rapport']
                if any(indicator in filename for indicator in important_indicators):
                    attachment_score -= 0.5
                    evidence.append(f"Important attachment name: {filename}")
            
            # Calculate final score
            # Limit between -1.0 and 1.0
            attachment_score = max(-1.0, min(1.0, attachment_score))
            
            return attachment_score, evidence
            
        except Exception as e:
            print(f"Error analyzing attachments: {e}")
            return 0, [f"Attachment analysis error: {str(e)}"]
        
    def classify_email(self, meta):
        """
        Classify an email as promotional or not by combining SBERT and rules.
        """
        try:
            # Initialize default values for all required fields
            results = {
                'is_promotional': False,
                'is_important': False,
                'importance_score': 0,
                'sbert_importance_score': 0,
                'importance_reasons': [],
                'promo_score': 0,
                'sbert_promo_score': 0,
                'combined_promo_score': 0,
                'attachment_score': 0,
                'confidence': 'low',
                'sbert_confidence': 0,
                'reasons': [],
                # Compatibility fields that must always be present
                'sbert_promo_score': 0,
                'sbert_importance_score': 0
            }
            
            reasons = []
            
            # FAST MODE : Quick classification with minimal analysis
            if self.fast_mode:
                return self._fast_classify(meta, results, reasons)
            
            # Quick exit for obvious cases
            if hasattr(config, 'SKIP_HEAVY_ANALYSIS_FOR_OBVIOUS_CASES') and config.SKIP_HEAVY_ANALYSIS_FOR_OBVIOUS_CASES:
                # Quick analysis for obvious promotional emails
                sender = meta.get('sender', '').lower()
                subject = meta.get('subject', '').lower()
                
                # Check for obvious promotional senders
                obvious_promo = any(term in sender for term in ['noreply', 'marketing', 'newsletter', 'promo'])
                obvious_promo_subjects = any(term in subject for term in ['unsubscribe', 'sale', 'offer', 'discount'])
                
                if obvious_promo and obvious_promo_subjects:
                    results.update({
                        'is_promotional': True,
                        'promo_score': 8.0,
                        'combined_promo_score': 0.8,
                        'confidence': 'high',
                        'reasons': ["Quick analysis: Obvious promotional email"],
                        'sbert_promo_score': 0.8,
                        'sbert_importance_score': 0.2
                    })
                    return results
            
            # Continue with standard classification...
            return self._full_classify(meta, results, reasons)
            
        except Exception as e:
            print(f"Critical error in email classification: {e}")
            # Return safe fallback result with all required fields
            return {
                'is_promotional': False,
                'is_important': False,
                'importance_score': 0,
                'sbert_importance_score': 0,
                'importance_reasons': [],
                'promo_score': 0,
                'sbert_promo_score': 0,
                'combined_promo_score': 0,
                'attachment_score': 0,
                'confidence': 'unknown',
                'sbert_confidence': 0,
                'reasons': [f"Critical classification error: {str(e)}"],
                'sbert_promo_score': 0,
                'sbert_importance_score': 0
            }

    def _fast_classify(self, meta, results, reasons):
        """
        Fast classification mode with minimal analysis for performance.
        """
        try:
            sender = meta.get('sender', '').lower()
            subject = meta.get('subject', '').lower()
            
            # Basic promotional indicators
            promo_indicators = [
                'newsletter', 'unsubscribe', 'marketing', 'promotion', 'offer', 
                'sale', 'discount', 'deal', 'noreply', 'no-reply'
            ]
            
            # Basic important indicators
            important_indicators = [
                'security', 'verification', 'confirm', 'urgent', 'payment',
                'invoice', 'receipt', 'bank', 'alert'
            ]
            
            promo_score = 0
            importance_score = 0
            
            # Check sender and subject for indicators
            for indicator in promo_indicators:
                if indicator in sender or indicator in subject:
                    promo_score += 2
                    reasons.append(f"Fast mode: Found promotional indicator '{indicator}'")
            
            for indicator in important_indicators:
                if indicator in sender or indicator in subject:
                    importance_score += 3
                    reasons.append(f"Fast mode: Found important indicator '{indicator}'")
            
            # Simple decision logic
            is_promotional = promo_score > 2 and importance_score < 3
            is_important = importance_score >= 3
            
            # If both scores are present, prioritize importance
            if importance_score >= 3 and promo_score > 2:
                is_promotional = False
                reasons.append("Fast mode: Importance overrides promotional")
            
            combined_promo_score = min(promo_score / 10.0, 1.0)
            confidence = 'medium' if promo_score > 4 or importance_score > 6 else 'low'
            
            results.update({
                'is_promotional': is_promotional,
                'is_important': is_important,
                'importance_score': importance_score,
                'promo_score': promo_score,
                'combined_promo_score': combined_promo_score,
                'confidence': confidence,
                'reasons': reasons + ["Fast mode: Limited analysis for speed"],
                'sbert_promo_score': combined_promo_score,
                'sbert_importance_score': importance_score / 10.0
            })
            
            return results
            
        except Exception as e:
            reasons.append(f"Fast mode error: {str(e)}")
            return results
    
    def _full_classify(self, meta, results, reasons):
        """
        Full classification with all analyses enabled.
        """
        # IMPORTANCE ANALYSIS (Must be done first)
        importance_score_rules = None
        importance_reasons = []
        
        try:
            is_important_rules, importance_score_rules, importance_reasons = self.important_classifier.is_important_email(meta)
            results['importance_score'] = max(0, importance_score_rules)
            results['importance_reasons'] = importance_reasons
        except Exception as e:
            print(f"Error in importance classification: {e}")
            is_important_rules = False
            importance_score_rules = 0
            importance_reasons = [f"Importance analysis error: {str(e)}"]
            results['importance_score'] = 0
            results['importance_reasons'] = importance_reasons
            reasons.append(f"Importance classification error: {str(e)}")
        
        # PROMO RULES ANALYSIS
        try:
            is_promo, promo_score, promo_reasons = self.promo_classifier.is_promo_email(meta)
            results['promo_score'] = max(0, promo_score)
            results['promo_reasons'] = promo_reasons
        except Exception as e:
            print(f"Error in rule-based classification: {e}")
            is_promo = False
            promo_score = 0
            results['promo_score'] = 0
            results['promo_reasons'] = [f"Rule classification error: {str(e)}"]
            reasons.append(f"Rule classification error: {str(e)}")
        
        # SBERT ANALYSIS
        sbert_promo_score = 0
        sbert_importance_score = 0
        sbert_confidence = 0

        if self.sbert_classifier.model:
            try:
                # Check if the email has content to analyze
                subject = meta.get('subject', '')
                sender = meta.get('sender', '')
                message_id = meta.get('message_id', '')
                
                # Generate a more informative ID if missing
                if not message_id or message_id == 'unknown':
                    sender_domain = sender.split('@')[-1] if '@' in sender else sender
                    subject_snippet = subject[:20] if subject else "no_subject"
                    message_id = f"temp_{sender_domain}_{subject_snippet}".replace(' ', '_')

                combined_text = subject if subject else ""
                                    
                if len(combined_text.strip()) < 15:  # Slightly higher threshold
                    # Only print warning if in verbose mode or for debugging
                    if getattr(config, 'VERBOSE_LOGGING', False):
                        print(f"Warning: Insufficient content for SBERT classification: {message_id}")
                    reasons.append("SBERT skipped: insufficient content")
                    # Set default SBERT values
                    sbert_promo_score = 0
                    sbert_importance_score = 0
                else:
                    # Preprocess the text
                    preprocessed_text = self.sbert_classifier.preprocess_text(combined_text)

                    # Check text length after preprocessing
                    if preprocessed_text.startswith("text too short"):
                        if getattr(config, 'VERBOSE_LOGGING', False):
                            print(f"Warning: SBERT preprocessing failed for {message_id}: {preprocessed_text}")
                        reasons.append(f"SBERT skipped: {preprocessed_text}")
                        sbert_promo_score = 0
                        sbert_importance_score = 0
                    else:
                        # Get SBERT predictions for all classes with higher k for better confidence
                        predictions = self.sbert_classifier.predict(preprocessed_text, 5)
                        
                        # Calculate confidence based on score distribution
                        if predictions and len(predictions) > 1:
                            top_score = predictions[0][1]
                            second_score = predictions[1][1] if len(predictions) > 1 else 0
                            sbert_confidence = top_score - second_score  # Higher difference = higher confidence
                        
                        # Retrieve scores for promo and importance classes
                        if not predictions:
                            sbert_promo_score = 0
                            sbert_importance_score = 0
                            reasons.append("SBERT skipped: no predictions returned")
                        else:
                            # Extract scores for both classes
                            for label, prob in predictions:
                                if label == "promo":
                                    sbert_promo_score = float(prob)
                                    reasons.append(f"SBERT promo: {round(prob*100, 1)}%")
                                elif label == "important":
                                    sbert_importance_score = float(prob)
                                    reasons.append(f"SBERT importance: {round(prob*100, 1)}%")
                                
                                # Add confidence information
                                if sbert_confidence > 0.3:
                                    reasons.append(f"SBERT confidence: high ({round(sbert_confidence*100, 1)}%)")
                                elif sbert_confidence > 0.1:
                                    reasons.append(f"SBERT confidence: medium ({round(sbert_confidence*100, 1)}%)")
                                else:
                                    reasons.append(f"SBERT confidence: low ({round(sbert_confidence*100, 1)}%)")
                                    
            except Exception as e:
                # Generate informative ID if missing for error reporting
                message_id_for_error = meta.get('message_id', '')
                if not message_id_for_error or message_id_for_error == 'unknown':
                    sender = meta.get('sender', 'unknown_sender')
                    sender_domain = sender.split('@')[-1] if '@' in sender else sender
                    subject = meta.get('subject', '')
                    subject_snippet = subject[:20] if subject else "no_subject"
                    message_id_for_error = f"temp_{sender_domain}_{subject_snippet}".replace(' ', '_')
                
                # Only print error if in verbose mode or for debugging
                if getattr(config, 'VERBOSE_LOGGING', False):
                    print(f"Error in SBERT classification for {message_id_for_error}: {e}")
                reasons.append(f"SBERT error: {str(e)[:50]}...")  # Truncate long error messages
                # Set safe default values
                sbert_promo_score = 0
                sbert_importance_score = 0
                sbert_confidence = 0
        else:
            # Model not loaded - set defaults and log
            reasons.append("SBERT model not available - using rules only")
            sbert_promo_score = 0
            sbert_importance_score = 0
            sbert_confidence = 0

        # Always update results with SBERT scores (even if 0)
        results['sbert_promo_score'] = max(0, sbert_promo_score)
        results['sbert_importance_score'] = max(0, sbert_importance_score)
        results['sbert_confidence'] = max(0, sbert_confidence)
        # Always set compatibility fields
        results['sbert_promo_score'] = max(0, sbert_promo_score)
        results['sbert_importance_score'] = max(0, sbert_importance_score)
        
        # COMBINE IMPORTANCE SCORES
        combined_importance_score = importance_score_rules if importance_score_rules is not None else 0
        
        # If SBERT has detected importance, integrate it
        if sbert_importance_score > 0:
            # Normalize SBERT score (0-1) to rules scale (0-10)
            sbert_importance_normalized = sbert_importance_score * 10.0
            
            # Adaptive weighting based on SBERT confidence
            if sbert_confidence > 0.3:  # High confidence SBERT
                effective_sbert_weight = self.sbert_weight * 1.2  # Increase weight
                effective_rules_weight = self.rules_weight * 0.9  # Slightly decrease rules weight
            elif sbert_confidence < 0.1:  # Low confidence SBERT
                effective_sbert_weight = self.sbert_weight * 0.7  # Decrease weight
                effective_rules_weight = self.rules_weight * 1.1  # Increase rules weight
            else:
                effective_sbert_weight = self.sbert_weight
                effective_rules_weight = self.rules_weight
            
            # Combine scores with adaptive weighting
            if importance_score_rules is not None and importance_score_rules > 0:
                combined_importance_score = (
                    (importance_score_rules * effective_rules_weight) + 
                    (sbert_importance_normalized * effective_sbert_weight)
                ) / (effective_rules_weight + effective_sbert_weight)
                reasons.append(f"Combined importance: rules {round(importance_score_rules, 1)} + SBERT {round(sbert_importance_normalized, 1)} = {round(combined_importance_score, 1)}")
            else:
                # If rules didn't detect importance, use SBERT with confidence-based weight
                confidence_factor = max(0.4, sbert_confidence)  # Minimum 40% weight
                combined_importance_score = sbert_importance_normalized * confidence_factor
                reasons.append(f"SBERT-only importance: {round(combined_importance_score, 1)} (confidence-weighted)")
        
        # Determine if email is important with combined score
        is_important = combined_importance_score >= self.importance_threshold
        
        # Update results
        results['importance_score'] = max(0, combined_importance_score)
        results['is_important'] = is_important
        
        # IMPORTANCE SKIPPING LOGIC - Skip promotional analysis for highly important emails
        if combined_importance_score >= config.IMPORTANCE_FAST_SKIP_THRESHOLD:
            # Very high importance - skip all promotional analysis
            results.update({
                'is_promotional': False,
                'combined_promo_score': 0,
                'confidence': 'high',
                'reasons': [f"Email skipped promotional analysis - very high importance score: {round(combined_importance_score, 1)}"]
            })
            return results
        
        elif combined_importance_score >= config.IMPORTANCE_SKIP_THRESHOLD:
            # High importance - skip detailed promotional analysis but still check for strong promotional signals
            is_strongly_promotional_basic = (
                (promo_score >= 9.0) or  # Only very high rule scores
                (sbert_promo_score >= 0.95 and sbert_confidence > 0.5)  # Only very confident SBERT
            )
            
            if not is_strongly_promotional_basic:
                results.update({
                    'is_promotional': False,
                    'combined_promo_score': 0,
                    'confidence': 'high',
                    'reasons': [f"Email skipped promotional analysis - high importance score: {round(combined_importance_score, 1)}"]
                })
                return results
            else:
                reasons.append(f"High importance ({round(combined_importance_score, 1)}) but very strong promotional signals detected")
        
        # Continue with full analysis if not skipped by importance
        # Apply basic promotional classification logic
        
        # Normalize promo score to 0-1 range
        normalized_promo_score = min(1.0, max(0, promo_score) / 10.0)
        
        # Combine scores if SBERT is available with improved adaptive weighting
        if sbert_promo_score > 0 and self.sbert_classifier.model:
            # Adaptive weighting based on SBERT confidence and agreement
            if sbert_confidence > 0.3:  # High confidence SBERT
                effective_sbert_weight = self.sbert_weight * 1.3  # Boost SBERT significantly
                effective_rules_weight = self.rules_weight * 0.7  # Reduce rules weight
                reasons.append(f"High SBERT confidence: boosting AI weight to {effective_sbert_weight:.2f}")
            elif sbert_confidence > 0.15:  # Medium confidence SBERT
                effective_sbert_weight = self.sbert_weight * 1.1  # Slight boost
                effective_rules_weight = self.rules_weight * 0.9  # Slight reduction
            else:  # Low confidence SBERT
                effective_sbert_weight = self.sbert_weight * 0.8  # Reduce SBERT weight
                effective_rules_weight = self.rules_weight * 1.2  # Increase rules weight
                reasons.append(f"Low SBERT confidence: reducing AI weight to {effective_sbert_weight:.2f}")
            
            # Weighted combination with adaptive factors
            combined_promo_score = (
                (sbert_promo_score * effective_sbert_weight) + 
                (normalized_promo_score * effective_rules_weight)
            ) / (effective_sbert_weight + effective_rules_weight)
            
            # Check for strong agreement between SBERT and rules
            score_difference = abs(normalized_promo_score - sbert_promo_score)
            if score_difference < 0.15:  # Strong agreement
                # Boost the combined score slightly when both agree
                agreement_boost = 0.05
                combined_promo_score = min(1.0, combined_promo_score + agreement_boost)
                reasons.append(f"Strong agreement (Δ={score_difference:.2f}): boosted by {agreement_boost:.2f}")
            elif score_difference > 0.4:  # Strong disagreement
                # Be more conservative when they disagree
                disagreement_penalty = 0.05
                combined_promo_score = max(0.0, combined_promo_score - disagreement_penalty)
                reasons.append(f"Strong disagreement: Rules {round(normalized_promo_score*100,1)}% vs SBERT {round(sbert_promo_score*100,1)}%")
            else:
                reasons.append(f"Moderate agreement: combined {round(combined_promo_score*100,1)}%")
        else:
            combined_promo_score = normalized_promo_score
            reasons.append("Using rules-only classification")
        
        # Dynamic threshold adjustment based on confidence and disagreement
        effective_threshold = self.promo_threshold
        disagreement_score = abs(normalized_promo_score - sbert_promo_score) if sbert_promo_score > 0 else 0
        
        # Enhanced threshold adjustment logic
        if sbert_confidence > 0.4:  # Very high confidence
            # Lower threshold slightly for high-confidence predictions
            threshold_reduction = min(config.HIGH_CONFIDENCE_THRESHOLD_REDUCTION, config.MAX_THRESHOLD_ADJUSTMENT)
            effective_threshold = max(0.35, self.promo_threshold - threshold_reduction)
            reasons.append(f"High confidence: adjusted threshold to {effective_threshold:.2f}")
        elif sbert_confidence < config.MIN_CONFIDENCE_THRESHOLD and sbert_promo_score > 0:  # Low confidence
            # Raise threshold for low-confidence predictions
            threshold_increase = min(config.LOW_CONFIDENCE_THRESHOLD_INCREASE, config.MAX_THRESHOLD_ADJUSTMENT)
            effective_threshold = min(0.75, self.promo_threshold + threshold_increase)
            reasons.append(f"Low confidence: adjusted threshold to {effective_threshold:.2f}")
        
        # Handle significant disagreements between SBERT and rules
        if disagreement_score > config.DISAGREEMENT_THRESHOLD:
            # Strong disagreement - be more conservative
            conservative_adjustment = min(0.1, disagreement_score * 0.2)
            effective_threshold = min(0.75, effective_threshold + conservative_adjustment)
            reasons.append(f"Strong disagreement detected (Δ={disagreement_score:.2f}): conservative threshold {effective_threshold:.2f}")
            
            # Add warning for potential classification issues
            if sbert_confidence > 0.3:
                reasons.append(f"⚠️ Potential classification issue: Rules {round(normalized_promo_score*100,1)}% vs AI {round(sbert_promo_score*100,1)}%")
        
        # Determine if promotional based on dynamic threshold
        is_promotional = combined_promo_score >= effective_threshold
        
        # Enhanced borderline case detection
        distance_from_threshold = abs(combined_promo_score - effective_threshold)
        is_borderline = distance_from_threshold < config.BORDERLINE_THRESHOLD
        
        if is_borderline:
            # For borderline cases, be more conservative (lean towards keeping)
            if not is_promotional and distance_from_threshold < 0.03:
                reasons.append(f"Borderline case: keeping email (distance: {distance_from_threshold:.3f})")
            elif is_promotional and distance_from_threshold < 0.03:
                # Very borderline promotional - add extra check
                if importance_score_rules and importance_score_rules > 2.0:
                    is_promotional = False
                    reasons.append(f"Borderline promotional overridden by importance ({importance_score_rules:.1f})")
                else:
                    reasons.append(f"Borderline promotional: proceeding with caution")
        
        # Determine confidence level with improved logic
        if sbert_confidence > 0.3 and distance_from_threshold > config.BORDERLINE_THRESHOLD and disagreement_score < 0.2:
            confidence_level = 'high'
        elif sbert_confidence > 0.15 and distance_from_threshold > config.BORDERLINE_THRESHOLD/2:
            confidence_level = 'medium'  
        elif distance_from_threshold > config.BORDERLINE_THRESHOLD * 2:  # Far from threshold even without SBERT
            confidence_level = 'medium'
        else:
            confidence_level = 'low'
            # For low confidence, add extra reasoning
            if is_borderline:
                reasons.append("Low confidence + borderline case: review recommended")
        
        # Enhanced final decision reasoning
        if is_promotional:
            action_reason = f"Classified as promotional: {round(combined_promo_score*100,1)}% >= {round(effective_threshold*100,1)}%"
            if disagreement_score > config.DISAGREEMENT_THRESHOLD:
                action_reason += f" (with disagreement: {round(disagreement_score*100,1)}%)"
            reasons.append(action_reason)
        else:
            action_reason = f"Kept: {round(combined_promo_score*100,1)}% < {round(effective_threshold*100,1)}%"
            if disagreement_score > config.DISAGREEMENT_THRESHOLD:
                action_reason += f" (with disagreement: {round(disagreement_score*100,1)}%)"
            reasons.append(action_reason)
        
        # Update final results
        results.update({
            'is_promotional': is_promotional,
            'is_important': False,
            'importance_score': max(0, combined_importance_score),
            'sbert_importance_score': max(0, sbert_importance_score),
            'importance_reasons': importance_reasons,
            'promo_score': max(0, promo_score),
            'sbert_promo_score': max(0, sbert_promo_score),
            'combined_promo_score': max(0, combined_promo_score),
            'attachment_score': 0,  # Set to 0 for simplified version
            'confidence': confidence_level,
            'sbert_confidence': sbert_confidence,
            'reasons': reasons[:6]  # Limit to most important reasons
        })
        
        return results
                    
    def get_sender_profile(self, sender):
        """Get comprehensive sender profile from temporal analyzer."""
        try:
            return self.temporal_analyzer.get_sender_profile(sender)
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