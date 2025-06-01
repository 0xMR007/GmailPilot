# src/classification_analyzer.py

"""
Classification Analyzer - Analyzes classification errors and suggests improvements.
This module helps identify patterns in misclassified emails and provides recommendations
for tuning the classification parameters.
"""

import json
import os
from datetime import datetime
from collections import defaultdict, Counter
from typing import Dict, List, Tuple, Optional

from src.config import config


class ClassificationAnalyzer:
    """
    Analyzes classification results to identify patterns and suggest improvements.
    """
    
    def __init__(self):
        self.analysis_results = {}
        self.error_patterns = defaultdict(list)
        self.suggested_improvements = []
        
    def analyze_log_file(self, log_file_path: str) -> Dict:
        """
        Analyze a log file and extract classification issues.
        
        Args:
            log_file_path (str): Path to the actions.log file
            
        Returns:
            Dict: Analysis results with recommendations
        """
        print(f"🔍 Analyzing classification log: {log_file_path}")
        
        emails_data = []
        potential_errors = []
        
        try:
            with open(log_file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                
            # Parse email data from log
            for line in lines:
                if "|" in line and ("Kept" in line or "Labelled as Promotion" in line):
                    email_data = self._parse_log_line(line)
                    if email_data:
                        emails_data.append(email_data)
                        
                        # Check for potential errors
                        if self._is_potential_error(email_data):
                            error_type = self._classify_error_type(email_data)
                            email_data['error_type'] = error_type
                            potential_errors.append(email_data)
                            self.error_patterns[error_type].append(email_data)
            
            # Generate analysis
            analysis = self._generate_analysis(emails_data, potential_errors)
            self.analysis_results = analysis
            
            # Generate improvement suggestions
            self.suggested_improvements = self._generate_improvements(analysis)
            
            return analysis
            
        except Exception as e:
            print(f"❌ Error analyzing log file: {e}")
            return {}
    
    def _parse_log_line(self, line: str) -> Optional[Dict]:
        """Parse a single log line to extract email data."""
        try:
            parts = line.strip().split(" | ")
            if len(parts) < 6:
                return None
                
            # Extract basic information
            timestamp = parts[0]
            message_id = parts[1].replace("ID:", "")
            action = parts[2]
            sender = parts[3]
            subject = parts[4]
            scores_part = parts[5]
            
            # Parse scores
            scores = {}
            if "Promo:" in scores_part:
                promo_match = scores_part.split("Promo:")[1].split("/")[0].strip()
                scores['promo_score'] = float(promo_match)
            
            if "Combined:" in scores_part:
                combined_match = scores_part.split("Combined:")[1].split("/")[0].strip()
                scores['combined_score'] = float(combined_match)
            
            if "Importance:" in scores_part:
                importance_part = scores_part.split("Importance:")[1].strip()
                if "IMPORTANT" in importance_part:
                    scores['importance_score'] = 10.0  # High importance
                    scores['is_important'] = True
                elif "Score:" in importance_part:
                    score_match = importance_part.split("Score:")[1].split(")")[0].strip()
                    scores['importance_score'] = float(score_match)
                    scores['is_important'] = False
                else:
                    scores['importance_score'] = 0.0
                    scores['is_important'] = False
            
            return {
                'timestamp': timestamp,
                'message_id': message_id,
                'action': action,
                'sender': sender,
                'subject': subject,
                **scores
            }
            
        except Exception as e:
            print(f"Error parsing line: {e}")
            return None
    
    def _is_potential_error(self, email_data: Dict) -> bool:
        """Determine if an email classification might be an error."""
        promo_score = email_data.get('promo_score', 0)
        combined_score = email_data.get('combined_score', 0)
        importance_score = email_data.get('importance_score', 0)
        is_important = email_data.get('is_important', False)
        action = email_data.get('action', '')
        
        # Define error conditions
        error_conditions = [
            # High rule score but kept
            promo_score > 7 and combined_score < 0.5 and action == "Kept",
            
            # Low rule score but labelled
            promo_score < 3 and combined_score > 0.6 and action == "Labelled as Promotion",
            
            # Borderline case
            abs(combined_score - config.PROMO_THRESHOLD) < 0.05,
            
            # Important email labelled as promotional
            is_important and action == "Labelled as Promotion",
            
            # High importance score but labelled
            importance_score > 5.0 and action == "Labelled as Promotion"
        ]
        
        return any(error_conditions)
    
    def _classify_error_type(self, email_data: Dict) -> str:
        """Classify the type of potential error."""
        promo_score = email_data.get('promo_score', 0)
        combined_score = email_data.get('combined_score', 0)
        importance_score = email_data.get('importance_score', 0)
        is_important = email_data.get('is_important', False)
        action = email_data.get('action', '')
        
        # Determine error type
        if is_important and action == "Labelled as Promotion":
            return "Important Email Misclassified"
        elif importance_score > 5.0 and action == "Labelled as Promotion":
            return "High Importance Score Ignored"
        elif abs(combined_score - config.PROMO_THRESHOLD) < 0.05:
            return "Threshold Borderline Case"
        elif promo_score > 7 and combined_score < 0.5:
            return "Rule-SBERT Disagreement (High Rule)"
        elif promo_score < 3 and combined_score > 0.6:
            return "Rule-SBERT Disagreement (Low Rule)"
        else:
            return "Other Classification Issue"
    
    def _generate_analysis(self, emails_data: List[Dict], potential_errors: List[Dict]) -> Dict:
        """Generate comprehensive analysis of classification results."""
        total_emails = len(emails_data)
        labelled_count = len([e for e in emails_data if e['action'] == "Labelled as Promotion"])
        kept_count = total_emails - labelled_count
        
        # Error type distribution
        error_types = Counter([e['error_type'] for e in potential_errors])
        
        # Score distributions
        promo_scores = [e.get('promo_score', 0) for e in emails_data]
        combined_scores = [e.get('combined_score', 0) for e in emails_data]
        importance_scores = [e.get('importance_score', 0) for e in emails_data]
        
        # Identify problematic score ranges
        borderline_cases = [e for e in emails_data 
                          if abs(e.get('combined_score', 0) - config.PROMO_THRESHOLD) < 0.1]
        
        # Sender analysis
        sender_stats = defaultdict(lambda: {'kept': 0, 'labelled': 0, 'errors': 0})
        for email in emails_data:
            sender = email.get('sender', '').split('@')[-1] if '@' in email.get('sender', '') else email.get('sender', '')
            action_key = 'labelled' if email['action'] == "Labelled as Promotion" else 'kept'
            sender_stats[sender][action_key] += 1
            
            if email in potential_errors:
                sender_stats[sender]['errors'] += 1
        
        return {
            'total_emails': total_emails,
            'labelled_count': labelled_count,
            'kept_count': kept_count,
            'error_count': len(potential_errors),
            'error_rate': len(potential_errors) / total_emails if total_emails > 0 else 0,
            'error_types': dict(error_types),
            'borderline_cases': len(borderline_cases),
            'score_stats': {
                'promo_scores': {
                    'min': min(promo_scores) if promo_scores else 0,
                    'max': max(promo_scores) if promo_scores else 0,
                    'avg': sum(promo_scores) / len(promo_scores) if promo_scores else 0
                },
                'combined_scores': {
                    'min': min(combined_scores) if combined_scores else 0,
                    'max': max(combined_scores) if combined_scores else 0,
                    'avg': sum(combined_scores) / len(combined_scores) if combined_scores else 0
                },
                'importance_scores': {
                    'min': min(importance_scores) if importance_scores else 0,
                    'max': max(importance_scores) if importance_scores else 0,
                    'avg': sum(importance_scores) / len(importance_scores) if importance_scores else 0
                }
            },
            'problematic_senders': {k: v for k, v in sender_stats.items() if v['errors'] > 0},
            'potential_errors': potential_errors[:10]  # Top 10 errors for detailed review
        }
    
    def _generate_improvements(self, analysis: Dict) -> List[Dict]:
        """Generate specific improvement suggestions based on analysis."""
        suggestions = []
        
        error_rate = analysis.get('error_rate', 0)
        error_types = analysis.get('error_types', {})
        
        # High error rate
        if error_rate > 0.15:  # More than 15% errors
            suggestions.append({
                'priority': 'HIGH',
                'category': 'Threshold Adjustment',
                'issue': f'High error rate detected: {error_rate:.1%}',
                'suggestion': 'Consider increasing PROMO_THRESHOLD from {:.2f} to {:.2f}'.format(
                    config.PROMO_THRESHOLD, min(0.75, config.PROMO_THRESHOLD + 0.1)
                ),
                'config_change': {'PROMO_THRESHOLD': min(0.75, config.PROMO_THRESHOLD + 0.1)}
            })
        
        # Many borderline cases
        borderline_count = analysis.get('borderline_cases', 0)
        if borderline_count > analysis.get('total_emails', 0) * 0.1:
            suggestions.append({
                'priority': 'MEDIUM',
                'category': 'Borderline Handling',
                'issue': f'Many borderline cases: {borderline_count}',
                'suggestion': 'Increase BORDERLINE_THRESHOLD to better handle uncertain cases',
                'config_change': {'BORDERLINE_THRESHOLD': 0.12}
            })
        
        # Rule-SBERT disagreements
        disagreement_count = (error_types.get('Rule-SBERT Disagreement (High Rule)', 0) + 
                            error_types.get('Rule-SBERT Disagreement (Low Rule)', 0))
        if disagreement_count > 5:
            suggestions.append({
                'priority': 'HIGH',
                'category': 'Weight Rebalancing',
                'issue': f'Frequent Rule-SBERT disagreements: {disagreement_count}',
                'suggestion': 'Adjust SBERT_WEIGHT to improve agreement between AI and rules',
                'config_change': {'SBERT_WEIGHT': 0.75, 'RULES_WEIGHT': 0.25}
            })
        
        # Important emails misclassified
        important_errors = error_types.get('High Importance Score Ignored', 0)
        if important_errors > 2:
            suggestions.append({
                'priority': 'HIGH',
                'category': 'Importance Protection',
                'issue': f'Important emails being misclassified: {important_errors}',
                'suggestion': 'Lower importance skip thresholds for better protection',
                'config_change': {
                    'IMPORTANCE_SKIP_THRESHOLD': 5.0,
                    'IMPORTANCE_FAST_SKIP_THRESHOLD': 7.0
                }
            })
        
        return suggestions
    
    def generate_improvement_report(self, output_path: str = None) -> str:
        """Generate a detailed improvement report."""
        if not output_path:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = f"logs/classification_analysis_{timestamp}.md"
        
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write("# Classification Analysis Report\n\n")
            f.write(f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            
            # Summary
            if self.analysis_results:
                f.write("## Summary\n\n")
                f.write(f"- **Total emails analyzed**: {self.analysis_results.get('total_emails', 0)}\n")
                f.write(f"- **Emails labelled as promotional**: {self.analysis_results.get('labelled_count', 0)}\n")
                f.write(f"- **Emails kept**: {self.analysis_results.get('kept_count', 0)}\n")
                f.write(f"- **Potential errors detected**: {self.analysis_results.get('error_count', 0)}\n")
                f.write(f"- **Error rate**: {self.analysis_results.get('error_rate', 0):.1%}\n\n")
            
            # Error types
            if self.analysis_results.get('error_types'):
                f.write("## Error Types Distribution\n\n")
                for error_type, count in self.analysis_results['error_types'].items():
                    f.write(f"- **{error_type}**: {count} emails\n")
                f.write("\n")
            
            # Improvement suggestions
            if self.suggested_improvements:
                f.write("## Improvement Suggestions\n\n")
                for i, suggestion in enumerate(self.suggested_improvements, 1):
                    f.write(f"### {i}. {suggestion['category']} ({suggestion['priority']} Priority)\n\n")
                    f.write(f"**Issue**: {suggestion['issue']}\n\n")
                    f.write(f"**Suggestion**: {suggestion['suggestion']}\n\n")
                    
                    if 'config_change' in suggestion:
                        f.write("**Recommended config changes**:\n")
                        for key, value in suggestion['config_change'].items():
                            f.write(f"- `{key} = {value}`\n")
                        f.write("\n")
            
            # Problematic senders
            if self.analysis_results.get('problematic_senders'):
                f.write("## Problematic Senders\n\n")
                f.write("| Sender | Kept | Labelled | Errors |\n")
                f.write("|--------|------|----------|--------|\n")
                for sender, stats in list(self.analysis_results['problematic_senders'].items())[:10]:
                    f.write(f"| {sender} | {stats['kept']} | {stats['labelled']} | {stats['errors']} |\n")
                f.write("\n")
        
        print(f"📊 Analysis report generated: {output_path}")
        return output_path
    
    def apply_suggestions(self, config_path: str = "src/config.py") -> bool:
        """
        Apply high-priority suggestions to the config file.
        
        Args:
            config_path (str): Path to the config file
            
        Returns:
            bool: True if changes were applied
        """
        if not self.suggested_improvements:
            print("No suggestions available to apply")
            return False
        
        high_priority_suggestions = [s for s in self.suggested_improvements if s['priority'] == 'HIGH']
        if not high_priority_suggestions:
            print("No high-priority suggestions to apply")
            return False
        
        print(f"📝 Applying {len(high_priority_suggestions)} high-priority suggestions...")
        
        # Here you would implement the logic to modify the config file
        # For now, just print the suggestions
        for suggestion in high_priority_suggestions:
            print(f"  - {suggestion['category']}: {suggestion['suggestion']}")
            if 'config_change' in suggestion:
                for key, value in suggestion['config_change'].items():
                    print(f"    {key} = {value}")
        
        print("✅ Suggestions applied. Please review and restart the application.")
        return True


def analyze_latest_log() -> Optional[str]:
    """
    Analyze the most recent log file and generate improvement suggestions.
    
    Returns:
        str: Path to the generated report, or None if no log found
    """
    logs_dir = "logs"
    if not os.path.exists(logs_dir):
        print("No logs directory found")
        return None
    
    # Find the most recent log directory
    log_dirs = [d for d in os.listdir(logs_dir) if os.path.isdir(os.path.join(logs_dir, d))]
    if not log_dirs:
        print("No log directories found")
        return None
    
    latest_log_dir = max(log_dirs)
    actions_log_path = os.path.join(logs_dir, latest_log_dir, "actions.log")
    
    if not os.path.exists(actions_log_path):
        print(f"No actions.log found in {latest_log_dir}")
        return None
    
    print(f"📈 Analyzing latest log: {latest_log_dir}")
    
    analyzer = ClassificationAnalyzer()
    analyzer.analyze_log_file(actions_log_path)
    
    report_path = analyzer.generate_improvement_report()
    
    # Print key suggestions
    if analyzer.suggested_improvements:
        print("\n🎯 Key Improvement Suggestions:")
        for suggestion in analyzer.suggested_improvements[:3]:  # Top 3
            print(f"  {suggestion['priority']}: {suggestion['suggestion']}")
    
    return report_path


if __name__ == "__main__":
    analyze_latest_log() 