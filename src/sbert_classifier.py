from sentence_transformers import SentenceTransformer
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import accuracy_score
from src.config import config
import joblib
import os
import warnings
import re
import numpy as np
import pandas as pd

# Delete the INFO and WARNING messages of TensorFlow
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'
# Disable the oneDNN messages
os.environ['TF_ENABLE_ONEDNN_OPTS'] = '0'
# Ignore the warnings
warnings.filterwarnings('ignore')

class SBertClassifier:
    """
    Unified email classifier using SBERT with lazy loading for better performance
    """
    
    # Class variable to track if warning has been displayed
    _model_warning_displayed = False
    
    def __init__(self, model_path=None):
        self.model_path = model_path or config.MODEL_PATH
        # Use lazy loading for SBERT model - don't load until needed
        self._sbert_model = None
        self.clf = LogisticRegression(random_state=42, max_iter=1000, class_weight='balanced')
        self.label_encoder = LabelEncoder()
        self.model = None  # For compatibility with existing code
        self.is_trained = False
        self.is_model_loaded = False
        
        # Try to load existing model (fast operation)
        if not self.is_model_loaded:
            self.load_model()

    @property
    def sbert_model(self):
        """Lazy loading property for SBERT model"""
        if self._sbert_model is None:
            # Only load when actually needed
            if getattr(config, 'VERBOSE_LOGGING', False):
                print("🔄 Loading multilingual SBERT model...")
            # Use multilingual model
            self._sbert_model = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")
        return self._sbert_model

    def load_model(self):
        """
        Load the trained model if it exists.
        Returns True if model was loaded successfully, False otherwise.
        """
        try:
            if os.path.exists(self.model_path):
                model_data = joblib.load(self.model_path)
                self.clf = model_data['classifier']
                self.label_encoder = model_data['label_encoder']
                self.model = self.clf  # For compatibility
                self.is_model_loaded = True
                self.is_trained = True
                return True
            else:
                # Only display warning once across all instances
                if not SBertClassifier._model_warning_displayed:
                    if getattr(config, 'VERBOSE_LOGGING', False):
                        print(f"⚠️ Model file not found: {self.model_path}")
                    SBertClassifier._model_warning_displayed = True
                self.is_model_loaded = False
                return False
        except Exception as e:
            print(f"❌ Error loading SBERT model: {e}")
            return False
        
    def get_model_status(self):
        return self.is_model_loaded

    def train(self, training_file=None):
        """
        Train the SBERT model on the provided data.
        
        Args:
            training_file (str): Path to training file. If None, uses config.TRAINING_PATH
            
        Returns:
            bool: True if training succeeded, False otherwise
        """
        try:
            training_path = training_file or config.TRAINING_PATH
            
            if not os.path.exists(training_path):
                print(f"❌ Training file not found: {training_path}")
                return False
            
            texts = []
            labels = []
            
            # Determine file format based on extension
            if training_path.endswith('.csv'):
                # Read CSV format
                try:
                    df = pd.read_csv(training_path)
                    if 'text' not in df.columns or 'label' not in df.columns:
                        print("❌ CSV file must have 'text' and 'label' columns")
                        return False
                    
                    for _, row in df.iterrows():
                        text = str(row['text']).strip()
                        label_val = row['label']
                        
                        # Convert numeric labels to text labels
                        if label_val == 1:
                            label = 'promo'
                        elif label_val == 0:
                            label = 'important'
                        else:
                            # Skip unknown labels
                            continue
                            
                        if text and len(text) > 5:  # Basic validation
                            texts.append(text)
                            labels.append(label)
                    
                    print(f"📄 Loaded CSV format with {len(texts)} samples")
                    
                except Exception as e:
                    print(f"❌ Error reading CSV file: {e}")
                    return False
                    
            else:
                print("❌ CSV training file not found")
                return False
            
            if not texts:
                print("❌ No training data found")
                return False
            
            print(f"📚 Training with {len(texts)} samples...")
            
            # Encode texts using SBERT
            print("🔄 Encoding texts with SBERT...")
            vectors = self.sbert_model.encode(texts, show_progress_bar=True)
            
            # Encode labels
            encoded_labels = self.label_encoder.fit_transform(labels)
            
            # Train classifier
            print("🔄 Training classifier...")
            self.clf.fit(vectors, encoded_labels)
            
            # Save model
            self.save_model()
            self.model = self.clf  # For compatibility
            self.is_trained = True
            self.is_model_loaded = True  # Mark as loaded after training
            
            # Print training results
            train_pred = self.clf.predict(vectors)
            accuracy = accuracy_score(encoded_labels, train_pred)
            print(f"✅ Training completed with accuracy: {accuracy:.3f}")
            
            # Show class distribution
            unique_labels, counts = np.unique(labels, return_counts=True)
            for label, count in zip(unique_labels, counts):
                print(f"   - {label}: {count} samples")
            
            return True
            
        except Exception as e:
            print(f"❌ Error training SBERT model: {e}")
            return False

    def predict(self, text, k=1):
        """
        Get predictions for a given text.
        
        Args:
            text (str): Text to classify
            k (int): Number of top predictions to return
            
        Returns:
            list: List of (label, probability) tuples
            Returns predictions in format compatible with legacy systems.
        """
        try:
            if not self.is_trained or self.clf is None:
                return []
            
            # Preprocess text
            processed_text = self.preprocess_text(text)
            if processed_text.startswith("text too short"):
                return []
            
            # Encode text
            vector = self.sbert_model.encode([processed_text])
            
            # Get probabilities for all classes
            probabilities = self.clf.predict_proba(vector)[0]
            
            # Get class labels
            class_labels = self.label_encoder.inverse_transform(range(len(probabilities)))
            
            # Create predictions with probabilities
            predictions = [(label, prob) for label, prob in zip(class_labels, probabilities)]
            
            # Sort by probability (descending)
            predictions.sort(key=lambda x: x[1], reverse=True)
            
            # Return top k predictions
            return predictions[:k]
            
        except Exception as e:
            print(f"Error in SBERT prediction: {e}")
            return []

    def preprocess_text(self, text):
        """
        Preprocess text for SBERT classification.
        
        Args:
            text (str): Input text to preprocess
            
        Returns:
            str: Preprocessed text ready for classification
            
        Compatible with existing preprocessing pipelines.
        """
        try:
            if not text or len(text.strip()) < 10:
                return "text too short for classification"
            
            # Basic preprocessing
            # Remove extra whitespace
            text = re.sub(r'\s+', ' ', text.strip())
            
            # Remove special characters but keep basic punctuation
            text = re.sub(r'[^\w\s\.,!?@-]', ' ', text)
            
            # Remove extra spaces again
            text = re.sub(r'\s+', ' ', text.strip())
            
            if len(text) < 10:
                return "text too short after preprocessing"
            
            return text
            
        except Exception as e:
            print(f"Error preprocessing text: {e}")
            return "preprocessing error"

    def save_model(self):
        """Save the trained model to disk."""
        try:
            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(self.model_path), exist_ok=True)
            
            # Save both classifier and label encoder
            model_data = {
                'classifier': self.clf,
                'label_encoder': self.label_encoder
            }
            
            joblib.dump(model_data, self.model_path)
            print(f"✅ SBERT model saved to {self.model_path}")
            
        except Exception as e:
            print(f"❌ Error saving SBERT model: {e}")