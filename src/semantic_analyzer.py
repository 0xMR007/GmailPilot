# src/semantic_analyzer.py

"""
Semantic analyzer for promotional email detection.
Uses linguistic analysis to determine if an email's content is promotional or important.
"""

import re
from bs4 import BeautifulSoup
from src.config import config

class SemanticAnalyzer:
    """
    Class for semantic analysis of email content.
    This class uses linguistic analysis techniques to 
    determine if an email's content is promotional or important.
    """
    
    def __init__(self):
        # Promotional keywords with their weights (between 0 and 1)
        self.promo_keywords = {
            # Offers and direct promotions
            "promo": 0.7, "promotion": 0.7, "offer": 0.7, "discount": 0.8, "remise": 0.8, "reduction": 0.8, "sale": 0.7,
            "solde": 0.7, "save": 0.7, "deal": 0.6,
            "coupon": 0.8, "promo code": 0.8, "price": 0.5, "prix": 0.5,
            # Marketing urgency
            "last chance": 0.8, "dernière chance": 0.8, "limited time": 0.7,
            "temps limité": 0.7, "expire": 0.6, "ending soon": 0.7,
            "don't miss": 0.6, "ne manquez pas": 0.6, "aujourd'hui": 0.4,
            "today only": 0.8, "seulement aujourd'hui": 0.8,
            # Call to action
            "shop now": 0.7, "achetez maintenant": 0.7, "buy now": 0.7,
            "order now": 0.7, "commandez": 0.6, "découvrez": 0.4,
            "discover": 0.4, "click here": 0.5, "cliquez ici": 0.5,
            # Typical advertising content
            "newsletter": 0.6, "subscribe": 0.6, "abonnez": 0.6,
            "unsubscribe": 0.8, "désabonnement": 0.8, "view online": 0.7,
            "voir en ligne": 0.7, "follow us": 0.7, "suivez-nous": 0.7,
            # Commercial content indicators
            "free shipping": 0.7, "livraison gratuite": 0.7, "gift": 0.6,
            "cadeau": 0.6, "collection": 0.5, "nouveautés": 0.5, "new": 0.4,
            "bundle": 0.6, "pack": 0.6, "premium": 0.5, "upgrade": 0.6,
            "flash sale": 0.8, "vente flash": 0.8, "exclusively": 0.6,
            "exclusive": 0.6, "special": 0.5, "spécial": 0.5
        }
        
        # Important keywords with their weights
        self.important_keywords = {
            # Security and account
            "security": 0.9, "sécurité": 0.9, "alert": 0.8, "alerte": 0.8,
            "password": 0.8, "mot de passe": 0.8, "account": 0.7, "compte": 0.7,
            "login": 0.8, "connexion": 0.8, "verify": 0.7, "verification": 0.7,
            "suspicious": 0.9, "suspect": 0.9, "unauthorized": 0.9, "non autorisé": 0.9,
            # Finance and payments
            "payment": 0.8, "paiement": 0.8, "transaction": 0.8, "invoice": 0.8,
            "facture": 0.8, "receipt": 0.7, "reçu": 0.7, "tax": 0.8, "impôt": 0.8,
            "overdue": 0.9, "retard": 0.9, "credit card": 0.8, "carte bancaire": 0.8,
            # Real urgency
            "urgent": 0.8, "deadline": 0.8, "échéance": 0.8, "reminder": 0.6,
            "rappel": 0.6, "action required": 0.7, "action nécessaire": 0.7,
            "important": 0.6, "critical": 0.8, "critique": 0.8,
            # Personal and professional
            "appointment": 0.7, "rendez-vous": 0.7, "interview": 0.8, "entretien": 0.8,
            "meeting": 0.7, "réunion": 0.7, "contract": 0.8, "contrat": 0.8,
            "application": 0.7, "candidature": 0.7, "job": 0.7, "emploi": 0.7,
            # Health
            "medical": 0.9, "médical": 0.9, "health": 0.8, "santé": 0.8,
            "prescription": 0.9, "ordonnance": 0.9, "results": 0.8, "résultats": 0.8,
            "appointment": 0.7, "rendez-vous": 0.7, "insurance": 0.7, "assurance": 0.7
        }
        
        # Confidence threshold for analysis
        self.threshold = config.SEMANTIC_THRESHOLD
    
    def _extract_text_from_html(self, html_content):
        """
        Extracts text from HTML content while preserving semantic structure.
        This method gives more weight to titles, links, and bold texts.
        """
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Remove script and style tags
            for script in soup(['script', 'style']):
                script.extract()
            
            # Extract text with certain tags treated specifically
            text_parts = []
            
            # Extract titles with higher weight
            for heading in soup.find_all(['h1', 'h2', 'h3']):
                heading_text = heading.get_text().strip()
                if heading_text:
                    # Repeat titles for higher weight
                    text_parts.append(heading_text + " ")
                    text_parts.append(heading_text + " ")
            
            # Extract bold or strong texts
            for emphasis in soup.find_all(['strong', 'b']):
                emphasis_text = emphasis.get_text().strip()
                if emphasis_text:
                    # Add repetition for higher weight
                    text_parts.append(emphasis_text + " ")
            
            # Extract text from links
            for link in soup.find_all('a'):
                link_text = link.get_text().strip()
                if link_text:
                    text_parts.append(link_text + " ")
            
            # Extract normal paragraphs
            for paragraph in soup.find_all('p'):
                paragraph_text = paragraph.get_text().strip()
                if paragraph_text:
                    text_parts.append(paragraph_text + " ")
            
            # Extract lists
            for list_item in soup.find_all('li'):
                list_text = list_item.get_text().strip()
                if list_text:
                    text_parts.append(list_text + " ")
            
            # Extract remaining text
            remaining_text = soup.get_text().strip()
            if remaining_text:
                text_parts.append(remaining_text)
            
            # Join all text parts
            extracted_text = " ".join(text_parts)
            
            # Final cleaning
            cleaned_text = re.sub(r'\s+', ' ', extracted_text).strip().lower()
            
            return cleaned_text
            
        except Exception as e:
            print(f"Error extracting text from HTML: {e}")
            return html_content if html_content else ""
    
    def calculate_semantic_score(self, html_content):
        """
        Calculates a semantic score for HTML content indicating how much
        it seems to be promotional.
        
        Returns:
            tuple: (score, evidence) where score is between 0 and 1, and evidence is
            a list of reasons explaining the score
        """
        if not html_content:
            return 0, []
        
        # Limit content size for analysis
        max_content_length = getattr(config, 'MAX_HTML_ANALYSIS_LENGTH', 10000)
        if len(html_content) > max_content_length:
            html_content = html_content[:max_content_length]
        
        # Quick check for obvious promotional content
        html_lower = html_content.lower()
        obvious_promo_indicators = ['unsubscribe', 'newsletter', 'promotional', 'marketing']
        if any(indicator in html_lower for indicator in obvious_promo_indicators):
            return 0.8, ["Obvious promotional content detected (quick semantic analysis)"]
        
        # Extract and normalize text from HTML
        content_text = self._extract_text_from_html(html_content)
        content_text = content_text.lower()
        
        # Limit text analysis size
        max_text_length = getattr(config, 'MAX_CONTENT_ANALYSIS_LENGTH', 5000)
        if len(content_text) > max_text_length:
            content_text = content_text[:max_text_length]
        
        # Early check for personal emails to avoid false positives
        is_personal, personal_confidence, personal_evidence = self.is_personal_email(content_text)
        if is_personal and personal_confidence > 0.7:
            # Strongly personal emails should not be considered promotional
            return 0, ["Personal email detected"] + personal_evidence[:2]
        
        # Calculate promotional and important scores
        promo_score, promo_evidence = self._calculate_keyword_score(
            content_text, self.promo_keywords
        )
        
        important_score, important_evidence = self._calculate_keyword_score(
            content_text, self.important_keywords
        )
        
        # Additional check for transactional/service content
        transactional_indicators = [
            'invoice', 'receipt', 'payment', 'transaction', 'confirmation',
            'security', 'password', 'verification', 'account', 'statement'
        ]
        
        transactional_count = sum(1 for indicator in transactional_indicators 
                                if indicator in content_text)
        
        if transactional_count >= 2:
            # Strong transactional content should reduce promotional score
            important_score += 0.3
            important_evidence.append(f"Transactional content detected ({transactional_count} indicators)")
        
        # Simplified structure analysis
        # Skip complex HTML parsing if content is too large
        if len(html_content) > 5000:
            structure_score = 0.5 if html_content.count('<img') > 3 else 0.2
            structure_evidence = ["Structure analysis simplified (large content)"]
        else:
            structure_score, structure_evidence = self._analyze_content_structure(html_content)
        
        # Calculate text/HTML ratio to detect very graphic emails
        text_ratio = len(content_text) / max(len(html_content), 1)
        
        # Weights of different analyses
        promo_weight = 0.5
        important_weight = 0.3  # Negative weight on promotional score
        structure_weight = 0.2
        
        # Calculate final score
        # Important scores reduce promotional score
        final_score = (
            (promo_score * promo_weight) - 
            (important_score * important_weight) +
            (structure_score * structure_weight)
        )
        
        # Normalize score to 0-1 range
        final_score = max(0, min(1, final_score))
        
        # Prepare evidence list
        evidence = []
        
        if promo_score > 0.3:
            evidence.extend([f"Promotional keywords: {promo_score:.1f}"] + promo_evidence[:2])
        
        if important_score > 0.3:
            evidence.extend([f"Important keywords: {important_score:.1f}"] + important_evidence[:2])
        
        if structure_score > 0.3:
            evidence.extend([f"Structure analysis: {structure_score:.1f}"] + structure_evidence[:1])
        
        # Apply text ratio penalty for very graphic emails
        if text_ratio < 0.2:
            final_score += 0.2
            evidence.append("Very low text/HTML ratio (graphic content)")
        
        # Additional penalties for low information density
        if len(content_text) < 100:
            final_score += 0.1
            evidence.append("Very short content")
        
        return final_score, evidence
    
    def _calculate_keyword_score(self, text, keywords_dict):
        """
        Calculates a score based on the presence of keywords in the text.
        
        Args:
            text (str): The text to analyze
            keywords_dict (dict): Dictionary of keywords with their weights
            
        Returns:
            tuple: (score, evidence) where score is between 0 and 1, and evidence is
            a list of found keywords
        """
        if not text:
            return 0, []
            
        evidence = []
        total_weight = 0
        max_possible_weight = 0
        
        # Calculate score based on keyword occurrences
        for keyword, weight in keywords_dict.items():
            keyword = keyword.lower()
            occurrences = text.count(keyword)
            
            if occurrences > 0:
                # Normalize impact of excessive repetitions
                normalized_occurrences = min(occurrences, 3)
                
                # Add to total weight with reduction for repetitions
                keyword_impact = weight * (1 + 0.3 * (normalized_occurrences - 1))
                total_weight += keyword_impact
                
                # Add to evidence
                evidence.append(f"'{keyword}' ({occurrences}x)")
            
            # Accumulate maximum possible weight (for normalization)
            max_possible_weight += weight
        
        # Normalize score between 0 and 1, with cap to prevent extreme values
        # due to multiple matches
        max_score_cap = 5  # Cap to prevent too high scores
        normalized_score = min(total_weight / max_score_cap, 1.0) if max_score_cap > 0 else 0
        
        return normalized_score, evidence
    
    def _analyze_content_structure(self, html_content):
        """
        Analyzes HTML content structure to detect promotional patterns.
        
        Args:
            html_content (str): The HTML content to analyze
            
        Returns:
            tuple: (score, evidence) where score is between 0 and 1, and evidence is
            a list of found structural features
        """
        evidence = []
        score = 0
        
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # 1. Detect multiple images (often found in promotional emails)
            images = soup.find_all('img')
            if len(images) > 3:
                score += min(0.2, 0.05 * len(images))
                evidence.append(f"Multiple images ({len(images)})")
            
            # 2. Detect call-to-action buttons
            action_buttons = 0
            for a in soup.find_all('a'):
                # Search styled links as buttons or containing action words
                if a.get('class') and any('button' in cls.lower() for cls in a.get('class')):
                    action_buttons += 1
                elif a.get('style') and ('background' in a.get('style').lower() or 'padding' in a.get('style').lower()):
                    action_buttons += 1
                elif a.text and any(action in a.text.lower() for action in ['shop', 'buy', 'order', 'acheter', 'commander', 'discover', 'découvrir']):
                    action_buttons += 1
            
            if action_buttons > 0:
                score += min(0.3, 0.1 * action_buttons)
                evidence.append(f"Call-to-action buttons ({action_buttons})")
            
            # 3. Detect table layouts (common in marketing emails)
            tables = soup.find_all('table')
            if len(tables) > 2:
                score += min(0.2, 0.05 * len(tables))
                evidence.append(f"Complex table layout ({len(tables)} tables)")
            
            # 4. Detect marketing email footer (unsubscribe, social networks)
            footer_indicators = [
                'unsubscribe', 'désabonner', 'privacy policy', 'politique de confidentialité',
                'facebook', 'twitter', 'instagram', 'linkedin', 'follow us', 'suivez-nous'
            ]
            
            # Find footer text (last section or parts containing these words)
            footer_elements = soup.find_all(['div', 'p', 'td'], text=lambda text: text and any(
                indicator in text.lower() for indicator in footer_indicators
            ))
            
            if footer_elements:
                score += 0.15
                evidence.append("Marketing email footer detected")
            
            # 5. Detect colorful and promotional formatting
            colorful_elements = 0
            for tag in soup.find_all(style=True):
                style = tag.get('style', '').lower()
                if 'color' in style or 'background' in style:
                    colorful_elements += 1
            
            if colorful_elements > 5:
                score += min(0.2, 0.02 * colorful_elements)
                evidence.append(f"Heavily styled content ({colorful_elements} colorful elements)")
            
            # 6. Detect price mentions
            price_pattern = re.compile(r'(\d+[.,]?\d*\s*(?:€|\$|£|USD|EUR)|\d+[.,]?\d*\s*%)')
            text = soup.get_text()
            price_matches = price_pattern.findall(text)
            
            if price_matches:
                score += min(0.25, 0.05 * len(price_matches))
                evidence.append(f"Price mentions ({len(price_matches)})")
            
            return score, evidence
            
        except Exception as e:
            print(f"Error analyzing HTML structure: {e}")
            return 0, ["Error analyzing HTML structure"]
            
    def is_personal_email(self, content):
        """
        Detects if an email contains personal information or
        a personal conversation.
        
        Args:
            content (str): The text or HTML content of the email
            
        Returns:
            tuple: (is_personal, confidence, evidence)
        """
        if not content:
            return False, 0, []
            
        # Extract text if it's HTML
        if '<html' in content.lower() or '<body' in content.lower():
            text = self._extract_text_from_html(content)
        else:
            text = content
            
        text = text.lower()
        
        # Personal email indicators
        personal_indicators = {
            # Personal salutations
            r'\b(hi|hello|hey|bonjour|salut|cher|chère|dear)\b.*\b\w+\b': 0.3,
            r'\bjust (wanted|checking|following|writing)\b': 0.5,
            r'\blet me know\b': 0.4,
            r'\bi (hope|think|believe|wanted)\b': 0.6,
            r'\bcould you\b': 0.4,
            r'\b(thanks|thank you|merci)\b.*\b\w+\b': 0.3,
            r'\b(à bientôt|see you soon|talk soon|à plus tard)\b': 0.5,
            r'\b(je|j\'ai|nous|notre|i|we|my|our|your)\b': 0.2,
            
            # Conversation style
            r'\?': 0.15,  # Questions
            r'[\.\!\?][^\.\!\?]+[\.\!\?]': 0.2,  # Short phrases
            
            # Personal content indicators
            r'\b(rendez-vous|meeting|call|appel|discussed|discuté|mentioned|mentionné)\b': 0.4,
            r'\b(attached|pièce jointe|document|fichier|file)\b': 0.3,
            r'\b(cv|resume|projet|project|report|rapport)\b': 0.4
        }
        
        score = 0
        evidence = []
        
        for pattern, weight in personal_indicators.items():
            matches = re.findall(pattern, text)
            if matches:
                normalized_matches = min(len(matches), 3)
                pattern_score = weight * normalized_matches
                score += pattern_score
                
                # Simplify model for display
                simple_pattern = pattern.replace(r'\b', '').replace(r'[^\.\!\?]+', '...').replace('.*', '...')
                evidence.append(f"Personal pattern '{simple_pattern}' ({len(matches)}x)")
        
        # Normalize score
        normalized_score = min(1.0, score / 3.0)
        
        # Final decision
        is_personal = normalized_score > 0.6
        
        return is_personal, min(1.0, normalized_score), evidence[:3] 