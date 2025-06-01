"""
Training Optimizer - Improves SBERT model training based on classification errors.
This module analyzes misclassified emails and adds them to the training dataset
to improve future classification accuracy.
"""

import os
import pandas as pd
import json
from datetime import datetime
from typing import List, Dict, Tuple
from src.config import config
from src.classification_analyzer import ClassificationAnalyzer


class TrainingOptimizer:
    """
    Optimizes SBERT training by learning from classification errors.
    """
    
    def __init__(self):
        self.training_data_path = config.TRAINING_PATH
        self.feedback_data_path = "data/feedback_dataset.csv"
        self.error_patterns_path = "data/error_patterns.json"
        
        # Ensure data directory exists
        os.makedirs("data", exist_ok=True)
    
    def analyze_and_improve(self, log_file_path: str) -> bool:
        """
        Analyze log file and improve training data based on errors.
        
        Args:
            log_file_path (str): Path to the actions.log file
            
        Returns:
            bool: True if improvements were made
        """
        print("🔧 Starting training optimization process...")
        
        # Analyze classification errors
        analyzer = ClassificationAnalyzer()
        analysis = analyzer.analyze_log_file(log_file_path)
        
        if not analysis or analysis.get('error_count', 0) == 0:
            print("✅ No classification errors found - model is performing well!")
            return False
        
        # Extract misclassified emails for training improvement
        error_emails = self._extract_error_emails(analysis)
        
        if not error_emails:
            print("⚠️ No actionable errors found for training improvement")
            return False
        
        # Add to feedback dataset
        self._add_to_feedback_dataset(error_emails)
        
        # Update training dataset
        success = self._update_training_dataset()
        
        if success:
            print(f"✅ Training dataset updated with {len(error_emails)} corrections")
            print("💡 Tip: Run model retraining to apply improvements")
            return True
        else:
            print("❌ Failed to update training dataset")
            return False
    
    def _extract_error_emails(self, analysis: Dict) -> List[Dict]:
        """Extract actionable error emails for training improvement."""
        potential_errors = analysis.get('potential_errors', [])
        actionable_errors = []
        
        for error in potential_errors:
            error_type = error.get('error_type', '')
            
            # Focus on Rule-SBERT disagreements which are most trainable
            if 'Rule-SBERT Disagreement' in error_type:
                # Determine correct label based on error analysis
                correct_label = self._determine_correct_label(error)
                if correct_label:
                    training_example = {
                        'text': error.get('subject', ''),
                        'label': correct_label,
                        'sender': error.get('sender', ''),
                        'error_type': error_type,
                        'confidence': self._calculate_correction_confidence(error)
                    }
                    actionable_errors.append(training_example)
        
        # Filter by confidence - only add high-confidence corrections
        high_confidence_errors = [e for e in actionable_errors if e['confidence'] > 0.7]
        
        print(f"📊 Found {len(actionable_errors)} actionable errors, {len(high_confidence_errors)} high-confidence")
        return high_confidence_errors
    
    def _determine_correct_label(self, error: Dict) -> str:
        """
        Determine the correct label for a misclassified email.
        
        Args:
            error (Dict): Error information
            
        Returns:
            str: Correct label ('promo' or 'important')
        """
        error_type = error.get('error_type', '')
        promo_score = error.get('promo_score', 0)
        importance_score = error.get('importance_score', 0)
        action = error.get('action', '')
        
        # Rule-SBERT Disagreement (High Rule) - Rules say promo, SBERT disagrees
        if error_type == 'Rule-SBERT Disagreement (High Rule)':
            # If rules strongly indicate promotional and email was actually kept,
            # the rules are likely correct - label as 'promo'
            if promo_score > 8 and action == 'Kept':
                return 'promo'
            # If importance score is also high, it might be an important email
            elif importance_score > 6:
                return 'important'
            # Default to promotional if rules score is high
            elif promo_score > 6:
                return 'promo'
        
        # Rule-SBERT Disagreement (Low Rule) - Rules say not promo, SBERT disagrees
        elif error_type == 'Rule-SBERT Disagreement (Low Rule)':
            # If rules score is low but email was labelled, SBERT might be right
            if promo_score < 4 and action == 'Labelled as Promotion':
                return 'promo'
            # If importance score is high, definitely important
            elif importance_score > 5:
                return 'important'
            # If promo score is very low, likely important
            elif promo_score < 2:
                return 'important'
        
        # For other error types, use heuristics
        if importance_score > 6:
            return 'important'
        elif promo_score > 6:
            return 'promo'
        
        return None  # Can't determine with confidence
    
    def _calculate_correction_confidence(self, error: Dict) -> float:
        """
        Calculate confidence in the correction.
        
        Args:
            error (Dict): Error information
            
        Returns:
            float: Confidence score (0-1)
        """
        promo_score = error.get('promo_score', 0)
        importance_score = error.get('importance_score', 0)
        error_type = error.get('error_type', '')
        
        base_confidence = 0.5
        
        # Higher confidence for clear cases
        if promo_score > 8 or importance_score > 7:
            base_confidence += 0.3
        elif promo_score > 6 or importance_score > 5:
            base_confidence += 0.2
        
        # Higher confidence for certain error types
        if 'Rule-SBERT Disagreement' in error_type:
            base_confidence += 0.2
        
        # Lower confidence if scores are contradictory
        if promo_score > 5 and importance_score > 5:
            base_confidence -= 0.3
        
        return min(1.0, max(0.0, base_confidence))
    
    def _add_to_feedback_dataset(self, error_emails: List[Dict]) -> None:
        """Add error corrections to feedback dataset."""
        # Create or load existing feedback dataset
        if os.path.exists(self.feedback_data_path):
            try:
                existing_df = pd.read_csv(self.feedback_data_path)
            except:
                existing_df = pd.DataFrame(columns=['text', 'label', 'source', 'confidence', 'timestamp'])
        else:
            existing_df = pd.DataFrame(columns=['text', 'label', 'source', 'confidence', 'timestamp'])
        
        # Prepare new data
        new_data = []
        for error in error_emails:
            new_data.append({
                'text': error['text'],
                'label': error['label'],
                'source': 'error_correction',
                'confidence': error['confidence'],
                'timestamp': datetime.now().isoformat(),
                'error_type': error.get('error_type', ''),
                'sender': error.get('sender', '')
            })
        
        # Combine and save
        if new_data:
            new_df = pd.DataFrame(new_data)
            combined_df = pd.concat([existing_df, new_df], ignore_index=True)
            
            # Remove duplicates based on text
            combined_df = combined_df.drop_duplicates(subset=['text'], keep='last')
            
            combined_df.to_csv(self.feedback_data_path, index=False)
            print(f"📝 Added {len(new_data)} corrections to feedback dataset")
    
    def _update_training_dataset(self) -> bool:
        """Update the main training dataset with feedback corrections."""
        try:
            # Load feedback data
            if not os.path.exists(self.feedback_data_path):
                return False
            
            feedback_df = pd.read_csv(self.feedback_data_path)
            if feedback_df.empty:
                return False
            
            # Load existing training data
            if os.path.exists(self.training_data_path):
                training_df = pd.read_csv(self.training_data_path)
            else:
                # Create minimal training dataset structure
                training_df = pd.DataFrame(columns=['text', 'label'])
            
            # Filter high-confidence feedback
            high_conf_feedback = feedback_df[feedback_df['confidence'] > 0.7]
            
            if high_conf_feedback.empty:
                return False
            
            # Prepare training data format
            training_additions = high_conf_feedback[['text', 'label']].copy()
            
            # Combine datasets
            updated_training = pd.concat([training_df, training_additions], ignore_index=True)
            
            # Remove duplicates
            updated_training = updated_training.drop_duplicates(subset=['text'], keep='last')
            
            # Save updated training dataset
            updated_training.to_csv(self.training_data_path, index=False)
            
            print(f"✅ Training dataset updated with {len(training_additions)} examples")
            print(f"📊 Total training examples: {len(updated_training)}")
            
            return True
            
        except Exception as e:
            print(f"❌ Error updating training dataset: {e}")
            return False
    
    def generate_training_report(self) -> str:
        """Generate a report on training improvements."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_path = f"logs/training_optimization_{timestamp}.md"
        
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write("# Training Optimization Report\n\n")
            f.write(f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            
            # Training dataset status
            if os.path.exists(self.training_data_path):
                training_df = pd.read_csv(self.training_data_path)
                f.write(f"## Training Dataset Status\n\n")
                f.write(f"- **Total training examples**: {len(training_df)}\n")
                
                label_dist = training_df['label'].value_counts()
                for label, count in label_dist.items():
                    f.write(f"- **{label}**: {count} examples\n")
                f.write("\n")
            
            # Feedback dataset status
            if os.path.exists(self.feedback_data_path):
                feedback_df = pd.read_csv(self.feedback_data_path)
                f.write(f"## Feedback Dataset Status\n\n")
                f.write(f"- **Total feedback examples**: {len(feedback_df)}\n")
                
                if not feedback_df.empty:
                    error_types = feedback_df['error_type'].value_counts()
                    f.write(f"- **Error types corrected**:\n")
                    for error_type, count in error_types.items():
                        f.write(f"  - {error_type}: {count}\n")
                f.write("\n")
            
            # Recommendations
            f.write("## Recommendations\n\n")
            f.write("1. **Retrain SBERT model** with updated dataset\n")
            f.write("2. **Monitor classification performance** after retraining\n")
            f.write("3. **Continue error analysis** to identify remaining issues\n\n")
            
        print(f"📊 Training report generated: {report_path}")
        return report_path
    
    def suggest_model_retraining(self) -> Dict:
        """Analyze if model retraining is recommended."""
        feedback_count = 0
        recent_errors = 0
        
        if os.path.exists(self.feedback_data_path):
            feedback_df = pd.read_csv(self.feedback_data_path)
            feedback_count = len(feedback_df)
            
            # Count recent high-confidence corrections
            high_conf = feedback_df[feedback_df['confidence'] > 0.7]
            recent_errors = len(high_conf)
        
        recommendation = {
            'should_retrain': False,
            'priority': 'LOW',
            'reason': '',
            'feedback_examples': feedback_count,
            'high_confidence_corrections': recent_errors
        }
        
        if recent_errors >= 10:
            recommendation.update({
                'should_retrain': True,
                'priority': 'HIGH',
                'reason': f'Many high-confidence corrections available ({recent_errors})'
            })
        elif recent_errors >= 5:
            recommendation.update({
                'should_retrain': True,
                'priority': 'MEDIUM',
                'reason': f'Several corrections available ({recent_errors})'
            })
        elif feedback_count >= 3:
            recommendation.update({
                'should_retrain': True,
                'priority': 'LOW',
                'reason': f'Some feedback available ({feedback_count} examples)'
            })
        
        return recommendation


def optimize_from_latest_log() -> bool:
    """
    Optimize training based on the latest log file.
    
    Returns:
        bool: True if optimization was performed
    """
    logs_dir = "logs"
    if not os.path.exists(logs_dir):
        print("No logs directory found")
        return False
    
    # Find the most recent log directory
    log_dirs = [d for d in os.listdir(logs_dir) if os.path.isdir(os.path.join(logs_dir, d))]
    if not log_dirs:
        print("No log directories found")
        return False
    
    latest_log_dir = max(log_dirs)
    actions_log_path = os.path.join(logs_dir, latest_log_dir, "actions.log")
    
    if not os.path.exists(actions_log_path):
        print(f"No actions.log found in {latest_log_dir}")
        return False
    
    print(f"🎯 Optimizing training from: {latest_log_dir}")
    
    optimizer = TrainingOptimizer()
    success = optimizer.analyze_and_improve(actions_log_path)
    
    if success:
        # Generate report
        optimizer.generate_training_report()
        
        # Check if retraining is recommended
        retrain_rec = optimizer.suggest_model_retraining()
        if retrain_rec['should_retrain']:
            print(f"\n🚀 Model retraining recommended ({retrain_rec['priority']} priority)")
            print(f"   Reason: {retrain_rec['reason']}")
            print("   Run: `python -m src.sbert_classifier --train` to retrain")
        
    return success


if __name__ == "__main__":
    optimize_from_latest_log() 