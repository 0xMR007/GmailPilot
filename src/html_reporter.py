# src/html_reporter.py

"""
HTML report generator for GmailPilot.
"""

import os
from datetime import datetime
from jinja2 import Environment, FileSystemLoader, select_autoescape

class HTMLReporter:
    """
    HTML report generator for GmailPilot.
    """
    
    def __init__(self, template_dir="templates", log_dir="logs"):
        self.template_dir = template_dir
        self.log_dir = log_dir
        
        # Create the templates directory if it doesn't exist
        os.makedirs(template_dir, exist_ok=True)
        
        # Jinja2 configuration
        self.env = Environment(
            loader=FileSystemLoader(template_dir),
            autoescape=select_autoescape(['html', 'xml'])
        )
        
    def generate_html_report(self, 
        total_scanned, 
        total_labelled,
        potential_errors,
        actions_summary,
        top_domains=None,
        processing_time=None,
        dry_run=False,
        promotional_emails=None,
        important_emails=None):
        """
        Generate a complete HTML report.
        
        Args:
            total_scanned: Total number of emails scanned
            total_labelled: Number of emails moved
            potential_errors: List of potential errors
            actions_summary: Summary of actions performed
            top_domains: Most frequent domains
            processing_time: Processing time
            dry_run: If it was a test run
            
        Returns:
            str: Path to the generated HTML file
        """
        
        try:
            template = self.env.get_template('report_template.html')
            
            # Calculate estimated accuracy
            accuracy_percentage = self._calculate_accuracy(potential_errors, total_scanned)
            
            # Prepare data for template with error handling
            try:
                formatted_errors = self._format_potential_errors(potential_errors)
            except Exception as e:
                print(f"Error formatting potential errors: {e}")
                formatted_errors = []
            
            try:
                formatted_actions = self._format_actions_summary(actions_summary)
            except Exception as e:
                print(f"Error formatting actions summary: {e}")
                formatted_actions = {'Emails labelled': 0, 'Emails kept': 0, 'Emails skipped': 0}
            
            template_data = {
                'report_date': datetime.now().strftime("%d/%m/%Y at %H:%M"),
                'total_scanned': total_scanned,
                'total_labelled': total_labelled,
                'potential_errors': formatted_errors,
                'actions_summary': formatted_actions,
                'accuracy_percentage': accuracy_percentage,
                'top_domains': top_domains[:min(5, len(top_domains))] if top_domains else [],
                'processing_time': processing_time,
                'dry_run': dry_run,
                'promotional_emails': promotional_emails if promotional_emails else [],
                'important_emails': important_emails if important_emails else []
            }
            
            # Generate HTML
            html_content = template.render(**template_data)
            
            # Save the file
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"report_{timestamp}.html"
            latest_log_dir = self.get_latest_log_dir()
            filepath = os.path.join(latest_log_dir, filename)
            
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(html_content)
                
            return filepath
            
        except Exception as e:
            import traceback
            print(f"Error generating HTML report: {e}")
            print(f"Stack trace: {traceback.format_exc()}")
            return None
    
    def _calculate_accuracy(self, potential_errors, total_scanned):
        """Calculate the estimated sorting accuracy."""
        if total_scanned == 0:
            return 100
            
        error_count = len(potential_errors)
        accuracy = max(0, min(100, ((total_scanned - error_count) / total_scanned) * 100))
        return round(accuracy)
    
    def _format_potential_errors(self, potential_errors):
        """Format potential errors for display."""
        formatted_errors = []
        
        for error in potential_errors:
            # Simplify technical reasons
            raw_reasons = error.get('reasons', [])
            simplified_reasons = self._simplify_classification_reasons(raw_reasons)
            
            formatted_error = {
                'sender': error.get('sender', 'Unknown sender'),
                'subject': error.get('subject', 'Unknown subject'),
                'action': 'labelled' if error.get('action') == 'Labelled as Promotion' else 'kept',
                'reason': self._get_error_reason_description(error.get('error_type', 'unknown')),
                'classification_reasons': simplified_reasons
            }
            
            # Add scores if available (ensure they are not negative)
            if 'promo_score' in error:
                formatted_error['promo_score'] = max(0, float(error['promo_score']))
            if 'importance_score' in error:
                # Normalize the importance score if necessary
                importance_val = max(0, float(error['importance_score']))
                # If the score is > 1, it is probably on the 0-10 scale, so normalize it
                if importance_val > 1:
                    importance_val = importance_val / 10.0
                formatted_error['importance_score'] = importance_val
            if 'sbert_promo_score' in error:
                formatted_error['sbert_promo_score'] = max(0, float(error['sbert_promo_score']))
            if 'sbert_importance_score' in error:
                formatted_error['sbert_importance_score'] = max(0, float(error['sbert_importance_score']))
            
            # If sbert_promo_score is not defined, try to extract it from reasons
            if 'sbert_promo_score' not in formatted_error and raw_reasons:
                for reason in raw_reasons:
                    if isinstance(reason, str):
                        # Try to extract SBERT promo score from reason text
                        if 'SBERT promo:' in reason:
                            try:
                                sbert_part = reason.split('SBERT promo:')[1].split('%')[0].strip()
                                sbert_part = sbert_part.split(',')[0].strip()
                                formatted_error['sbert_promo_score'] = max(0, float(sbert_part) / 100.0)
                                break
                            except Exception as e:
                                print(f"Error parsing SBERT promo: {e}, text: {reason}")
                                pass
                        elif 'SBERT:' in reason and 'SBERT importance:' not in reason:
                            try:
                                sbert_part = reason.split('SBERT:')[1].split('%')[0].strip()
                                sbert_part = sbert_part.split(',')[0].strip()
                                formatted_error['sbert_promo_score'] = max(0, float(sbert_part) / 100.0)
                                break
                            except Exception as e:
                                print(f"Error parsing SBERT promo: {e}, text: {reason}")
                                pass
            
            # If sbert_importance_score is not defined, try to extract it from reasons
            if 'sbert_importance_score' not in formatted_error and raw_reasons:
                for reason in raw_reasons:
                    if isinstance(reason, str):
                        # Try to extract SBERT importance score from reason text
                        if 'SBERT importance:' in reason:
                            try:
                                sbert_part = reason.split('SBERT importance:')[1].split('%')[0].strip()
                                sbert_part = sbert_part.split(',')[0].strip()
                                formatted_error['sbert_importance_score'] = max(0, float(sbert_part) / 100.0)
                                break
                            except Exception as e:
                                print(f"Error parsing SBERT importance: {e}, text: {reason}")
                                pass
                        elif 'sbert importance contribution:' in reason.lower():
                            try:
                                importance_start = reason.lower().find('sbert importance contribution:')
                                if importance_start != -1:
                                    substr = reason[importance_start:]
                                    sbert_part = substr.split(':')[1].split('%')[0].strip()
                                    sbert_part = sbert_part.split(',')[0].strip()
                                    formatted_error['sbert_importance_score'] = max(0, float(sbert_part) / 100.0)
                                    break
                            except Exception as e:
                                print(f"Error parsing SBERT importance contribution: {e}, text: {reason}")
                                pass
                
            formatted_errors.append(formatted_error)
            
        return formatted_errors
    
    def _format_actions_summary(self, actions_summary):
        """Format the actions summary with English labels."""
        english_labels = {
            'labelled': 'Emails labelled',
            'kept': 'Emails kept', 
            'skipped': 'Emails skipped',
            'error': 'Processing errors'
        }
        
        formatted_summary = {}
        try:
            for action, count in actions_summary.items():
                # Ensure action is a string
                action_str = str(action) if action is not None else 'unknown'
                label = english_labels.get(action_str, action_str.title())
                formatted_summary[label] = count
        except Exception as e:
            print(f"Error in _format_actions_summary: {e}")
            print(f"actions_summary: {actions_summary}")
            # Return default summary in case of error
            formatted_summary = {
                'Emails labelled': 0,
                'Emails kept': 0,
                'Emails skipped': 0,
                'Processing errors': 0
            }
            
        return formatted_summary
    
    def _get_error_reason_description(self, reason_key):
        """Convert error keys to readable descriptions."""
        descriptions = {
            'low_confidence': 'Low confidence classification',
            'conflicting_signals': 'Conflicting signals detected',
            'important_but_labelled': 'Important email marked as promotional',
            'promotional_but_kept': 'Promotional email kept in inbox',
            'borderline_score': 'Score close to threshold',
            'sender_mismatch': 'Sender classification mismatch',
            'content_analysis_failed': 'Content analysis failed',
            'unknown': 'Classification uncertainty',
            
            # Types of errors generated by the current system
            'Important Email Misclassified': 'Important email marked as promotional',
            'High Importance Score Ignored': 'High importance score overridden',
            'Threshold Borderline Case': 'Score very close to decision threshold',
            'Rule-SBERT Disagreement (High Rule)': 'Rules suggest promotional, AI disagrees',
            'Rule-SBERT Disagreement (Low Rule)': 'Rules suggest non-promotional, AI disagrees',
            'Rule-SBERT Disagreement (High SBERT)': 'AI strongly suggests promotional, rules disagree',
            'Importance-Promotion Conflict': 'Conflicting importance and promotional signals',
            'Potential Classification Error': 'Uncertain classification'
        }
        
        return descriptions.get(reason_key, reason_key.replace('_', ' ').title())
    
    def _simplify_classification_reasons(self, reasons):
        """
        Simplify technical reasons into user-friendly explanations.
        """
        simplified_reasons = []
        
        for reason in reasons:
            if not reason or not isinstance(reason, str):
                continue
                
            reason = reason.strip()
            simplified = self._translate_technical_reason(reason)
            
            if simplified and simplified not in simplified_reasons:
                simplified_reasons.append(simplified)
        
        return simplified_reasons[:5]  # Limit to 5 reasons max
    
    def _translate_technical_reason(self, reason):
        """
        Convert technical reasons to user-friendly explanations.
        """
        if not reason:
            return reason
            
        reason_lower = reason.lower()
        
        # Simple keyword matching first
        if 'unsubscribe' in reason_lower:
            return "🔗 Contains unsubscribe links"
        if 'promotion' in reason_lower or 'promo' in reason_lower:
            return "🏷️ Promotional keywords detected"
        if 'marketing' in reason_lower or 'newsletter' in reason_lower:
            return "📧 Marketing/Newsletter sender"
        if 'noreply' in reason_lower or 'no-reply' in reason_lower:
            return "📧 No-reply sender address"
        if 'important' in reason_lower or 'urgent' in reason_lower:
            return "⚠️ Important/urgent content detected"
        if 'confidence' in reason_lower and 'high' in reason_lower:
            return "✅ High confidence classification"
        if 'confidence' in reason_lower and 'low' in reason_lower:
            return "❓ Low confidence classification"
        if 'attachment' in reason_lower:
            return "📎 Contains attachments"
        if 'rule' in reason_lower:
            return "📋 Rule-based analysis"
        
        # Scores SBERT - More intuitive explanations
        if 'sbert promo:' in reason_lower:
            try:
                score = float(reason.split(':')[1].replace('%', '').strip())
                if score > 70:
                    return f"🤖 AI analysis: Strong promotional indicators ({score:.1f}%)"
                elif score > 40:
                    return f"🤖 AI analysis: Moderate promotional indicators ({score:.1f}%)"
                else:
                    return f"🤖 AI analysis: Non-promotional content indicators ({score:.1f}%)"
            except:
                return "🤖 AI promotional content analysis performed"
        
        if 'sbert importance:' in reason_lower:
            try:
                score = float(reason.split(':')[1].replace('%', '').strip())
                if score > 70:
                    return f"🤖 AI analysis: High importance signals detected ({score:.1f}%)"
                elif score > 40:
                    return f"🤖 AI analysis: Moderate importance signals detected ({score:.1f}%)"
                else:
                    return f"🤖 AI analysis: Low importance signals detected ({score:.1f}%)"
            except:
                return "🤖 AI importance analysis performed"
        
        if 'sbert confidence:' in reason_lower:
            try:
                # Extract confidence level and percentage
                if 'high' in reason_lower:
                    return "✅ AI analysis: High confidence in classification"
                elif 'medium' in reason_lower:
                    return "⚠️ AI analysis: Medium confidence in classification"
                elif 'low' in reason_lower:
                    return "❓ AI analysis: Low confidence in classification"
                else:
                    return "🤖 AI confidence assessment performed"
            except:
                return "🤖 AI confidence assessment performed"
        
        # Generic SBERT mentions
        if 'sbert' in reason_lower:
            return "🤖 AI content analysis performed"
        
        # Keep original if no translation found
        return reason
    
    def load_data_from_logs(self, actions_log_path, errors_log_path):
        """
        Load data from existing log files.
        
        Args:
            actions_log_path: Path to the actions log file
            errors_log_path: Path to the potential errors log file
            
        Returns:
            Dict containing formatted data
        """
        data = {
            'potential_errors': [],
            'actions_summary': {},
            'top_domains': [],
            'total_scanned': 0,
            'total_labelled': 0,
            'promotional_emails': [],
            'important_emails': []
        }
        
        # Load potential errors from the custom text format
        if os.path.exists(errors_log_path):
            try:
                with open(errors_log_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    
                # Parse the custom error format
                error_sections = content.split('--------------------------------------------------------------------------------')
                
                for section in error_sections:
                    if 'EMAIL:' in section and 'From:' in section:
                        lines = section.strip().split('\n')
                        error_data = {}
                        classification_reasons = []
                        
                        # Collect all classification reasons
                        in_reasons_section = False
                        
                        for line in lines:
                            line = line.strip()
                            if line.startswith('EMAIL:'):
                                error_data['subject'] = line.replace('EMAIL:', '').strip()
                            elif line.startswith('From:'):
                                error_data['sender'] = line.replace('From:', '').strip()
                            elif line.startswith('Action:'):
                                action = line.replace('Action:', '').strip()
                                error_data['action'] = 'labelled' if 'Labelled as Promotion' in action else 'kept'
                            elif line.startswith('Scores:'):
                                # Parser les scores: "Promo: 8.80 / 10.0 | Combined: 0.97 / 0.60"
                                scores_text = line.replace('Scores:', '').strip()
                                if 'Promo:' in scores_text:
                                    promo_part = scores_text.split('|')[0].strip()
                                    if '/' in promo_part:
                                        promo_score = promo_part.split(':')[1].strip().split('/')[0].strip()
                                        try:
                                            # Convert 0-10 score to 0-1 percentage
                                            error_data['promo_score'] = float(promo_score) / 10.0
                                        except:
                                            pass
                            elif line.startswith('Importance:'):
                                # Parser: "Not Important (Score: 4.60)" ou "IMPORTANT (Score: 8.60)"
                                importance_text = line.replace('Importance:', '').strip()
                                if '(' in importance_text and 'Score:' in importance_text:
                                    score_part = importance_text.split('Score:')[1].replace(')', '').strip()
                                    try:
                                        # The score may be on the 0-10 scale, keep it as is for now
                                        # Normalization will be done in _format_potential_errors
                                        error_data['importance_score'] = float(score_part)
                                    except:
                                        pass
                            elif line.startswith('Reasons:'):
                                # Extract SBERT scores from reasons
                                reasons_text = line.replace('Reasons:', '').strip()
                                in_reasons_section = True
                                
                                # Extract SBERT promo score (format: "SBERT: 85.1%")
                                if 'SBERT:' in reasons_text and 'SBERT importance:' not in reasons_text:
                                    try:
                                        sbert_part = reasons_text.split('SBERT:')[1].split('%')[0].strip()
                                        # Clean the string to keep only digits and decimal point
                                        sbert_part = sbert_part.split(',')[0].strip()  # Take only the first part before the comma
                                        error_data['sbert_promo_score'] = float(sbert_part) / 100.0
                                    except Exception as e:
                                        print(f"Error parsing SBERT promo: {e}, text: {reasons_text}")
                                        pass
                                
                                # Extract SBERT importance score (multiple formats)
                                # Format 1: "SBERT importance: 56.4%"
                                if 'SBERT importance:' in reasons_text:
                                    try:
                                        sbert_part = reasons_text.split('SBERT importance:')[1].split('%')[0].strip()
                                        # Clean the string to keep only digits and decimal point
                                        sbert_part = sbert_part.split(',')[0].strip()  # Take only the first part before the comma
                                        error_data['sbert_importance_score'] = float(sbert_part) / 100.0
                                    except Exception as e:
                                        print(f"Error parsing SBERT importance: {e}, text: {reasons_text}")
                                        pass
                                
                                # Format 2: "sbert importance contribution: 56.4%"
                                if 'sbert importance contribution:' in reasons_text.lower():
                                    try:
                                        # Case insensitive search
                                        importance_start = reasons_text.lower().find('sbert importance contribution:')
                                        if importance_start != -1:
                                            substr = reasons_text[importance_start:]
                                            sbert_part = substr.split(':')[1].split('%')[0].strip()
                                            sbert_part = sbert_part.split(',')[0].strip()
                                            error_data['sbert_importance_score'] = float(sbert_part) / 100.0
                                    except Exception as e:
                                        print(f"Error parsing SBERT importance contribution: {e}, text: {reasons_text}")
                                        pass
                                
                                # Compatibility with old format "SBERT promo:"
                                if 'SBERT promo:' in reasons_text:
                                    try:
                                        sbert_part = reasons_text.split('SBERT promo:')[1].split('%')[0].strip()
                                        error_data['sbert_promo_score'] = float(sbert_part) / 100.0
                                    except:
                                        pass
                                
                                # Add the reasons line to the list
                                if reasons_text:
                                    classification_reasons.append(reasons_text)
                                
                                error_data['reason'] = 'low_confidence'  # Default reason
                            elif in_reasons_section and line and not line.startswith('EMAIL:') and not line.startswith('From:') and not line.startswith('Action:') and not line.startswith('Scores:') and not line.startswith('Importance:') and not line.startswith('Severity:') and not line.startswith('TIMESTAMP:'):
                                # Continue collecting reasons on the following lines
                                # Also parse SBERT scores from continuation lines
                                line_text = line.strip()
                                
                                # Check for SBERT importance in continuation lines
                                if 'SBERT importance:' in line_text:
                                    try:
                                        sbert_part = line_text.split('SBERT importance:')[1].split('%')[0].strip()
                                        sbert_part = sbert_part.split(',')[0].strip()
                                        error_data['sbert_importance_score'] = float(sbert_part) / 100.0
                                    except Exception as e:
                                        print(f"Error parsing SBERT importance in continuation: {e}, text: {line_text}")
                                        pass
                                
                                # Check for sbert importance contribution in continuation lines
                                if 'sbert importance contribution:' in line_text.lower():
                                    try:
                                        importance_start = line_text.lower().find('sbert importance contribution:')
                                        if importance_start != -1:
                                            substr = line_text[importance_start:]
                                            sbert_part = substr.split(':')[1].split('%')[0].strip()
                                            sbert_part = sbert_part.split(',')[0].strip()
                                            error_data['sbert_importance_score'] = float(sbert_part) / 100.0
                                    except Exception as e:
                                        print(f"Error parsing SBERT importance contribution in continuation: {e}, text: {line_text}")
                                        pass
                                
                                classification_reasons.append(line_text)
                            elif in_reasons_section and line.startswith('Severity:'):
                                # End of reasons section
                                in_reasons_section = False
                                
                        # Post-processing: If sbert_importance_score is still missing, try to extract from all collected reasons
                        if 'sbert_importance_score' not in error_data and classification_reasons:
                            for reason in classification_reasons:
                                if 'SBERT importance:' in reason:
                                    try:
                                        sbert_part = reason.split('SBERT importance:')[1].split('%')[0].strip()
                                        sbert_part = sbert_part.split(',')[0].strip()
                                        error_data['sbert_importance_score'] = float(sbert_part) / 100.0
                                        break
                                    except Exception as e:
                                        print(f"Error parsing SBERT importance post-processing: {e}, text: {reason}")
                                        pass
                        
                        # Add the classification reasons to the error
                        if classification_reasons:
                            error_data['reasons'] = classification_reasons
                        
                        if 'subject' in error_data and 'sender' in error_data:
                            data['potential_errors'].append(error_data)
                            
            except Exception as e:
                print(f"Error loading errors: {e}")
        
        # Load actions from the custom text format
        if os.path.exists(actions_log_path):
            try:
                actions_count = {'labelled': 0, 'kept': 0, 'skipped': 0, 'error': 0}
                domains = {}
                
                with open(actions_log_path, 'r', encoding='utf-8') as f:
                    for line in f:
                        if line.strip() and '|' in line:
                            try:
                                # Format: "2025-05-24 14:19:33 | ID:... | Action | Sender | Subject | ..."
                                parts = line.split('|')
                                if len(parts) >= 5:
                                    action_part = parts[2].strip()
                                    sender_part = parts[3].strip()
                                    subject_part = parts[4].strip() if len(parts) > 4 else 'No subject'
                                    
                                    # Determine the action
                                    if 'Labelled as Promotion' in action_part:
                                        action = 'labelled'
                                        actions_count['labelled'] += 1
                                        data['total_labelled'] += 1
                                        
                                        # Add to promotional emails
                                        data['promotional_emails'].append({
                                            'sender': sender_part,
                                            'subject': subject_part,
                                            'action': 'labelled'
                                        })
                                        
                                    elif 'Kept' in action_part:
                                        action = 'kept'
                                        actions_count['kept'] += 1
                                        
                                        # Check if it's marked as important
                                        if 'IMPORTANT' in action_part:
                                            data['important_emails'].append({
                                                'sender': sender_part,
                                                'subject': subject_part,
                                                'action': 'kept'
                                            })
                                    else:
                                        action = 'skipped'
                                        actions_count['skipped'] += 1
                                    
                                    data['total_scanned'] += 1
                                    
                                    # Extract the domain of the sender
                                    if '@' in sender_part:
                                        domain = sender_part.split('@')[-1].lower().strip()
                                        domains[domain] = domains.get(domain, 0) + 1
                                        
                            except Exception:
                                continue
                
                data['actions_summary'] = actions_count
                data['top_domains'] = sorted(domains.items(), key=lambda x: x[1], reverse=True)[:10]
                
            except Exception as e:
                print(f"Error loading actions: {e}")
        
        return data
    
    def generate_report_from_logs(self, 
        actions_log_path, 
        errors_log_path,
        processing_time=None,
        dry_run=False):
        """
        Generate an HTML report from existing log files.
        
        Args:
            actions_log_path: Path to the actions log file
            errors_log_path: Path to the errors log file
            processing_time: Processing time
            dry_run: If it was a test run
            
        Returns:
            str: Path to the generated HTML file
        """
        data = self.load_data_from_logs(actions_log_path, errors_log_path)
        
        return self.generate_html_report(
            total_scanned=data['total_scanned'],
            total_labelled=data['total_labelled'],
            potential_errors=data['potential_errors'],
            actions_summary=data['actions_summary'],
            top_domains=data['top_domains'],
            processing_time=processing_time,
            dry_run=dry_run,
            promotional_emails=data['promotional_emails'],
            important_emails=data['important_emails']
        )
    
    def get_latest_log_dir(self):
        """
        Get the latest log directory.
        
        Returns:
            Path to the latest log directory
        """
        dirs = os.listdir(self.log_dir)
        dirs.sort(key=lambda x: os.path.getmtime(os.path.join(self.log_dir, x)))
        return os.path.join(self.log_dir, dirs[-1])
    
if __name__ == "__main__":
    reporter = HTMLReporter()
    infos = reporter.load_data_from_logs("logs/log_30May2025-16h57/actions.log", "logs/log_30May2025-16h57/potential_errors.log")
    errors = infos.get("potential_errors")
    for error in errors:
        print(error.get("importance_score"))
        print(error.get("sbert_importance_score"))
        print(error.get("promo_score"))
        print(error.get("sbert_promo_score"))
        print("--------------------------------")