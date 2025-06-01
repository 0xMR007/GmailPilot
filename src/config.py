# src/config.py

"""
Configuration settings for GmailPilot.
"""

import os

class Config:
    """
    Configuration for GmailPilot application.
    Focus on promotional email detection using SBERT AI and rule-based logic.
    """
    def __init__(self):
        
        # Define paths to important folders
        self.LOGS_DIR = "./logs"
        self.MODELS_DIR = "./models"
        self.DATA_DIR = "./data"
        self.MODEL_PATH = self.MODELS_DIR + "/sbert_model.pkl"
        self.TRAINING_PATH = self.DATA_DIR + "/dataset.csv"

        # Create important folders if they don't exist
        os.makedirs(self.LOGS_DIR, exist_ok=True)
        os.makedirs(self.MODELS_DIR, exist_ok=True)
        os.makedirs(self.DATA_DIR, exist_ok=True)
        
        # Application configuration
        self.TARGET_FOLDER = "GmailPilot"  # Target folder name for promotional emails
        
        # Classification parameters
        self.PROMO_THRESHOLD = 0.55  # Promotional detection threshold (0.0-1.0)
        self.IMPORTANCE_THRESHOLD = 4.5  # Important email protection level (0-10)
        self.SEMANTIC_THRESHOLD = 0.25  # Semantic similarity threshold
        self.PROMOTIONAL_PENALTY = 0.5  # Penalty for promotional indicators in importance scoring
        
        # Importance skipping parameters
        self.IMPORTANCE_SKIP_THRESHOLD = 5.5  # Reduced from 6.0 to protect more important emails
        self.IMPORTANCE_FAST_SKIP_THRESHOLD = 7.5  # Reduced from 8.0 for better safety
        
        # AI Model weights
        self.SBERT_WEIGHT = 0.50  # Model weight for SBERT predictions
        self.RULES_WEIGHT = 0.50  # Rule-based scoring weight
        
        self.MIN_CONFIDENCE_THRESHOLD = 0.15  # Minimum confidence for AI predictions
        self.DISAGREEMENT_THRESHOLD = 0.35  # Maximum acceptable disagreement between SBERT and rules
        self.BORDERLINE_THRESHOLD = 0.08  # Threshold for borderline cases
        
        self.HIGH_CONFIDENCE_THRESHOLD_REDUCTION = 0.03  # High confidence threshold reduction
        self.LOW_CONFIDENCE_THRESHOLD_INCREASE = 0.08  # Low confidence threshold increase
        self.MAX_THRESHOLD_ADJUSTMENT = 0.10  # Maximum threshold adjustment
        
        # Temporal analysis parameters
        self.TEMPORAL_WINDOW_DAYS = 30  # Temporal analysis window in days
        self.TEMPORAL_MIN_EMAILS = 10  # Minimum number of emails for temporal analysis
        self.TEMPORAL_REGULARITY_THRESHOLD = 0.5  # Temporal regularity threshold

        # Performance parameters
        self.BATCH_SIZE = 20  # Batch size for complex Gmail API operations
        self.MAX_RESULTS = 500  # Number of emails to retrieve from Gmail API (max 500)

        # Reporting configuration
        self.ENABLE_REPORTING = True  # Enable report generation
        
        # Performance optimization settings
        self.SKIP_HEAVY_ANALYSIS_FOR_OBVIOUS_CASES = False  # Skip heavy analysis for obvious cases (default to False)
        
        # Optional performance optimizations (set to True to skip analysis for speed)
        self.SKIP_CONTEXT_ANALYSIS = False  # Skip context analysis for better performance
        self.SKIP_TEMPORAL_ANALYSIS = False  # Skip temporal analysis for faster processing
        self.SKIP_SEMANTIC_ANALYSIS = False  # Keep semantic analysis as it's core feature
        
        # New performance optimizations
        self.USE_METADATA_CACHE = True  # Enable metadata caching
        self.CACHE_TTL_HOURS = 24  # Cache time-to-live in hours

        # Email patterns
        self.RESPONSE_PATTERNS = ["re:", "fwd:", "tr:", "fw:"]  # Patterns indicating a response
        self.NO_REPLY_PATTERNS = ["noreply", "no-reply", "donotreply", "do-not-reply", "no.reply"]
        
        # KEYWORD LISTS FOR CLASSIFICATION
        
        # List of senders exempt from classification
        self.WHITELIST = [] # You can add your own whitelist of senders here

        # IMPORTANCE CLASSIFIER CONFIGURATION
        self.CRITICAL_KEYWORDS = [
            # Security and connection alerts
            "security alert", "alerte sécurité", "sign-in", "login", "connexion", 
            "new device", "nouvel appareil", "suspicious", "suspect", "security", "sécurité",
            "verify account", "vérifier compte", "verification code", "code vérification",
            "two-factor", "2fa", "authentification", "breach", "violation", "compromised",
            "unauthorized", "non autorisé", "unusual activity", "activité inhabituelle", 
            "account locked", "compte verrouillé", "password reset", "réinitialisation mot de passe",
            "votre code", "code",
            
            # Financial alerts
            "payment", "paiement", "transaction", "facture", "invoice", "bank", "banque",
            "refund", "remboursement", "charge", "prélèvement", "overdue", "retard",
            "balance", "solde", "credit", "débit", "statement", "relevé", "wire transfer", "virement",
            "montant dû", "carte bancaire", "credit card", "expiration", "fraudulent", "frauduleux",
            
            # Professional alerts
            "urgent", "action required", "action nécessaire", "deadline", "échéance",
            "meeting", "réunion", "project", "projet", "follow-up", "suivi", "reminder",
            "invite", "invitation", "webinar", "conference", "interview", "entretien",
            "application", "candidature", "contract", "contrat", "agreement", "signature",
            
            # Health alerts
            "health alert", "alerte santé", "medical", "appointment", "rendez-vous", "doctor",
            "prescription", "ordonnance", "test results", "résultats", "vaccine", "vaccin",
            "diagnosis", "diagnostic", "treatment", "traitement", "insurance", "assurance",
            "emergency", "urgence", "symptoms", "symptômes", "surgery", "chirurgie",
            "documents partagés", "shared documents", "document médical", "medical document",
            "analyse", "analysis", "examen", "examination", "consultation", "patient",
            
            # System and service notifications
            "system alert", "alerte système", "login attempt", "tentative connexion", "blocked", "bloqué",
            "update required", "mise à jour", "security update", "account verification",
            "suspension", "service interruption", "panne", "maintenance", "backup", "sauvegarde",
            "critical update", "expiring", "expire", "action needed", "confirmation",
            
            # Other important alerts
            "subscription", "abonnement", "renewal", "renouvellement", "delivery", "livraison",
            "tracking", "suivi", "order", "commande", "support", "assistance", "contact",
            "complaint", "réclamation", "dispute", "litige", "warranty", "garantie",
            "return", "retour", "cancellation", "annulation", "important notice", "avis important",
            "policy update", "terms of service", "privacy", "confidentialité", "data", "données",
            
            # Additional keywords for important communications
            "confirmed", "confirmé", "approved", "approuvé", "validated", "validé",
            "receipt", "reçu", "tax document", "document fiscal", "salary", "salaire",
            "payslip", "fiche de paie", "legal notice", "avis légal", "court", "tribunal",
            "lawsuit", "procès", "inheritance", "héritage", "notary", "notaire",
            "property", "propriété", "landlord", "propriétaire", "rent", "loyer",
            "employment", "emploi", "job offer", "offre d'emploi", "resignation", "démission",
            "promotion", "layoff", "licenciement", "severance", "indemnité",
            
            # Transactional keywords
            "order confirmation", "confirmation commande", "shipping", "expédition",
            "tracking", "suivi", "delivered", "livré", "return", "retour",
            "refund", "remboursement", "warranty", "garantie", "support ticket",
            "ticket support", "case number", "numéro dossier", "reference number",
            "numéro référence", "activation", "désactivation", "deactivation",
            "subscription", "abonnement", "renewal", "renouvellement", "upgrade",
            "downgrade", "plan change", "changement plan", "billing", "facturation",
            "payment method", "méthode paiement", "card expiry", "expiration carte",
            "verification required", "vérification requise", "action required",
            "action nécessaire", "update required", "mise à jour requise"
        ]

        # List of critical senders
        self.CRITICAL_SENDERS = [
            # Financial & banking services
            "bank", "banque", "paypal", "visa", "mastercard", "payment", "paiement",
            "invoice", "facture", "billing", "tax", "impôt", "finance",
            "amex", "american express", "carte", "card", "crédit", "credit", "loan", "prêt",
            "mortgage", "hypothèque", "assurance", "insurance", "mutuelle", "wallet", "portefeuille",
            
            # Security & identity
            "security", "sécurité", "authentication", "verify", "verification", "identity",
            "password", "recovery", "récupération", "account", "compte", "protection", "alert",
            "alerte", "notice", "warning", "avertissement", "suspicious", "suspect", "fraud",
            "fraude", "detect", "détection", "monitor", "surveillance",
            
            # Administrative & essential services
            "admin", "helpdesk", "official", "gouvernement", "customer-care", "insurance",
            "healthcare", "santé", "medical", "legal", "juridique", "service-public",
            "impots.gouv", "ameli", "caf", "cpam", "pole-emploi", "mairie", "prefecture",
            "administration", "agence", "authority", "autorité", "ministry", "ministère",
            "embassy", "ambassade", "consulate", "consulat", "court", "tribunal",
            
            # Alerts & HR
            "critical-alert", "alerte-critique", "action-required", "urgent",
            "recruiter", "payroll", "university", "académique", "school", "école", "scholarship",
            "bourse", "career", "carrière", "job", "emploi", "interview", "entretien",
            "application", "candidature", "mentor", "coach", "training", "formation",
            
            # Essential services and providers
            "electric", "électricité", "internet", "telecom",
            "provider", "fournisseur", "utility", "utilities", "service", "support", "assistance",
            "help", "aide", "emergency", "urgence", "housing", "logement", "property", "propriété",

            # Health services
            "health", "santé", "medical", "hospital", "hôpital", "clinic",
            "clinique", "doctor", "docteur", "médecin", "patient", "mutuelle",
            "insurance", "assurance", "pharmacy", "pharmacie", "analyse médicale",
            "medical analysis", "tests médicaux", "blood test", "blood tests",
            "doctolib", "docteur", "cabinet médical", "medical office",
            "rendez-vous médical", "medical appointment", "documents médicaux",
        ]

        # List of common senders associated with promotional emails
        self.PROMOTIONAL_SENDERS = [
            # Marketing communication
            "newsletter", "ne-pas-repondre", "no-reply", "noreply", 
            "donotreply", "do-not-reply", "marketing", "promotion", "promo", 
            "offres", "offers", "deals", "soldes", "sales", "commercial", 
            "publicite", "advertisement", "actualites", "news", "diffusion", 
            "communication", "campaign", "campagne", "discover", "marketplace",
            "mail-client", "e-mail-marketing", "automated-mail",
            
            # General e-commerce
            "shop", "boutique", "store", "e-commerce", "online",
            "retail", "distribution", "vente-privee", "veepee", "marketplace",
            "shopping",
            
            # Marketing customer services
            "info-promo", "info-newsletter", "info-offres", "contact-commercial", 
            "service-consommateur", "welcome", "hello", "bonjour",
            "client-care", "satisfaction", "feedback", "avis-client",
            "community", "communauté", "ambassadeur", "ambassador", "influencer",
            
            # General social networks
            "notifications", "follow", "suivre", "subscriber", 
            "friend", "notification", "facebook", "instagram", "twitter",
            "linkedin", "pinterest", "tiktok", "snapchat", "youtube", 
            "twitch", "reddit", "discord", "telegram", "whatsapp",
            
            # Marketing subscriptions and registration
            "abonnement", "subscription", "inscription", "signup", "register",
            "invitation-event", "confirmation-achat", "nouveautes",
            "unsubscribe", "désabonnement", "opt-out", "opt-in", "free-trial",
            "essai-gratuit", "premium", "upgrade", "plan", "subscribe",
            
            # Loyalty programs
            "fidelite", "loyalty", "member", "membre", "vip", "privilege", 
            "rewards", "recompense", "points", "bonus", "cadeau", "gift",
            "birthday", "anniversaire", "exclusive", "vente-privée",
            "club", "avantage", "benefit", "programm", "programme",
            
            # Events & Entertainment
            "event", "événement", "tickets", "billets", "concert", "spectacle",
            "cinema", "movie", "film", "festival", "conference", "exhibition",
            "exposition", "show", "entertainment", "divertissement", "game", "jeu"
        ]

        # List of common keywords in promotional email subjects
        self.PROMOTIONAL_SUBJECTS = [
            # Promotional offers
            "offre", "offer", "promo", "promotion", "solde", "sale", "remise", 
            "discount", "reduction", "deal", "-{}%", "gratuit", "free", "cadeau", 
            "gift", "économisez", "save", "coupon", "code promo", "prix", "price",
            "destockage", "clearance", "pas cher", "achetez", "buy", "black friday",
            "cyber monday", "vente flash", "flash sale", "outlet", "liquidation",
            
            # Temporal/urgent character (marketing)
            "dernière chance", "last chance", "ne manquez pas", "don't miss", 
            "limité", "limited", "vente flash", "flash sale", "jusqu'à", "up to", 
            "aujourd'hui", "today", "exceptionnel", "dernier jour", "last day",
            "termine bientôt", "ending soon", "24h", "week-end", "weekend",
            "n'attendez plus", "don't wait", "urgent", "soon", "bientôt",
            "final sale", "vente finale", "countdown", "compte à rebours",
            
            # Marketing incentive terms
            "nouveau", "new", "découvrez", "discover", "profitez", "enjoy",
            "exclusif", "exclusive", "spécial", "special", "seulement", "only", 
            "meilleur", "best", "opportunité", "opportunity", "must-have", 
            "top", "idéal", "ideal", "parfait", "perfect", "incroyable", "amazing",
            "trending", "tendance", "viral", "popular", "populaire", "hit",
            
            # Advantages and benefits
            "livraison gratuite", "free shipping", "satisfait ou remboursé", 
            "money back", "gagnez", "win", "concours", "contest", "VIP", 
            "premium", "essai gratuit", "free trial", "sans engagement", 
            "échantillon", "sample", "bonus", "advantage", "avantage",
            "2-for-1", "2 pour 1", "bundle", "pack", "combo", "ensemble",
            
            # Marketing customer relations
            "bienvenue", "welcome", "fidélité", "loyalty", "anniversaire", 
            "birthday", "invitez", "refer", "parrainage", "referral", 
            "subscribe", "newsletter", "désabonner", "unsubscribe", 
            "member", "membre", "club", "join", "rejoignez", "we miss you",
            "vous nous manquez", "comeback", "return", "retour",
            
            # Specific marketing events
            "black friday", "cyber monday", "soldes d'été", "summer sale",
            "boxing day", "christmas", "noël", "halloween", "valentines",
            "saint valentin", "fête des mères", "mother's day", "fête des pères",
            "father's day", "season", "saison", "holiday", "vacances", 
            "back to school", "rentrée", "festival", "prime day"
        ]
        
        # Regular expressions for common promotional patterns
        self.PROMOTIONAL_PATTERNS = [
            # Typical promotional patterns
            r"([0-9]{1,2}|[0-9]{1,2},[0-9]{1,2})(\s*[-–]\s*|\s*%\s*|€\s*|$\s*|\s*euros?|\s*dollars?)(\s*de\s*remise|\s*off|\s*discount)",
            r"(free|gratuit)\s*(shipping|delivery|livraison)",
            r"(dont|ne)\s*(miss|manquez)\s*",
            r"(limited|limité)\s*(time|temps|offer|offre)",
            r"(new\s*arrivals|nouveautés)",
            r"(promo|promotion|deal|offer|offre|discount|remise|solde)s?",
            
            # Artificial urgency patterns
            r"(last\s*chance|dernière\s*chance)",
            r"(sale\s*ends|fin\s*des\s*soldes)",
            r"(only|seulement)\s*[0-9]+\s*(days|jours)",
            r"(today\s*only|aujourd'hui\s*seulement)",
            r"(expires|expire)\s*(today|soon|bientôt)",
            
            # Call to actions
            r"(shop|achetez)\s*(now|maintenant)",
            r"(learn|découvrez)\s*(more|plus)",
            r"(sign\s*up|inscrivez[\s-]vous)",
            r"(buy|achetez|order|commandez)\s*(now|maintenant)",
            r"(click|cliquez)\s*(here|ici)",
            r"(subscribe|abonnez[\s-]vous)",
            r"(register|enregistrez[\s-]vous)",
            r"(try|essayez)\s*(it|le)\s*(now|today|maintenant|aujourd'hui)",
            
            # Satisfaction or commercial formulas
            r"(satisfaction\s*guaranteed|satisfaction\s*garantie)",
            r"(money\s*back|remboursé)",
            r"(no\s*obligation|sans\s*engagement)",
            r"(no\s*risk|sans\s*risque)",
            r"(unsubscribe|désabonner|désinscri)",
            r"(view\s*in\s*browser|voir\s*dans\s*navigateur)"
        ]
        
        # Additional transactional patterns to better detect important emails
        self.TRANSACTIONAL_PATTERNS = [
            # Confirmations and receipts
            r"(confirmation|confirmed|receipt|reçu|facture|invoice)",
            r"(order|commande)\s*(#|n[o°]|:|\s)*[a-zA-Z0-9]+",
            r"(payment|paiement)\s*(received|reçu|confirmed|confirmé)",
            r"(shipping|livraison|delivery|expédition)",
            r"(tracking|suivi)\s*(number|numéro|#)",
            r"(reservation|booking|réservation)",
            r"(appointment|rendez-vous)\s*(confirmed|confirmé)",
            r"(subscription|abonnement)\s*(activated|activé|renewed|renouvelé)",
            
            # Medical and health documents
            r"(documents?\s*(partagés?|shared|médicaux?|medical))",
            r"(résultats?\s*(d'analyse|de\s*test|medical))",
            r"(nouveau\s*(message|document)\s*(de|from)\s*dr)",
            r"(consultation|appointment|rendez-vous)\s*(confirmé|confirmed)",
            
            # Security alerts
            r"(security|sécurité)\s*(alert|alerte)",
            r"(login|connexion)\s*(attempt|tentative)",
            r"(password|mot\s*de\s*passe)\s*(reset|réinitialisation)",
            r"(account|compte)\s*(verification|vérification)",
            
            # Banking and financial services
            r"(statement|relevé)\s*(available|disponible)",
            r"(transaction|virement)\s*(completed|effectué)",
            r"(card|carte)\s*(blocked|bloquée|expired|expirée)",
            r"(balance|solde)\s*(alert|alerte|notification)"
        ]
        
        # Protected services that should never be classified as promotional
        self.PROTECTED_SERVICES = [
            # Medical services
            "doctolib", "monespacesante", "ameli", "cpam", "mutuelle", "assurance-maladie",
            "mesanalyses", "lbm", "laboratoire", "hopital", "clinique", "cabinet-medical",
            
            # Banking services
            "banque", "bank", "credit-agricole", "bnp", "societe-generale", "lcl",
            "boursobank", "revolut", "n26", "paypal", "stripe", "wise",
            
            # Government services
            "gouv.fr", "service-public", "impots.gouv", "pole-emploi", "caf",
            "prefecture", "mairie", "administration",
            
            # Security services
            "security", "account", "verification", "authentication", "2fa",
            
            # Essential platforms
            "google", "microsoft", "apple", "amazon", "github", "gitlab"
        ]

config = Config()