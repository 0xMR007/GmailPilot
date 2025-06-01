# src/logger.py

"""
Logger for GmailPilot.
Handles all logging operations.
"""

import json
from datetime import datetime
from src.config import config
import os
import csv
import re
from .html_reporter import HTMLReporter
from src.utils import Utils

class ReportLogger:
    """
    Manages logging of actions for processed emails.
    Enhanced version with Markdown report generation and potential error detection.
    """
    
    # Class variable to track if HTML report message was already displayed
    _html_report_displayed = False

    def __init__(self, log_dir=None):
        """Initializes the logger with appropriate file paths."""
        # Use default logs folder if none is specified
        self.log_dir = log_dir if log_dir else "./logs"
        
        # Create a more readable timestamp (format: 23Jan2024_14h30)
        date_now = datetime.now()
        self.timestamp = date_now.strftime("%Y%m%d_%H%M%S")  # Machine format for uniqueness
        self.readable_date = date_now.strftime("%d%b%Y-%Hh%M")  # Human readable format
        
        self.classified_data = []
        
        # Create a specific log folder for this session with a more readable name
        self.session_log_dir = os.path.join(self.log_dir, f"log_{self.readable_date}")
        os.makedirs(self.session_log_dir, exist_ok=True)
        
        # Log files
        self.action_log_path = os.path.join(self.session_log_dir, "actions.log")
        self.csv_log_path = os.path.join(self.session_log_dir, "classified_emails.csv")
        self.report_path = os.path.join(self.session_log_dir, "report.txt")
        self.md_report_path = os.path.join(self.session_log_dir, "report.md")
        self.errors_path = os.path.join(self.session_log_dir, "potential_errors.log")
        self.detailed_report_path = os.path.join(self.session_log_dir, "detailed_report.md")
        self.decisions_csv_path = os.path.join(self.session_log_dir, "all_decisions.csv")
        self.message_ids_path = os.path.join(self.session_log_dir, "message_ids.txt")
        
        # Track potential errors to group duplicates
        self.error_tracking = {}
        
        # Logger headers for CSV output (define before use)
        self.csv_headers = [
            "timestamp", "message_id", "sender", "subject", "action",
            "promo_score", "sbert_promo_score", "combined_promo_score", 
            "importance_score", "sbert_importance_score", "is_important", "reasons"
        ]
        
        # Detailed CSV file headers
        self.detailed_csv_headers = [
            "timestamp", "message_id", "sender", "subject", "action",
            "promo_score", "sbert_promo_score", "combined_promo_score", 
            "importance_score", "sbert_importance_score", "is_important", 
            "domain", "reasons", "potential_error"
        ]
        
        # Initialize CSV file with header
        with open(self.csv_log_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(self.csv_headers)
            
        # Initialize potential errors file
        with open(self.errors_path, 'w', encoding='utf-8') as f:
            f.write(f"GmailPilot Potential Errors - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("=" * 80 + "\n\n")
            
        # Initialize message IDs file
        with open(self.message_ids_path, 'w', encoding='utf-8') as f:
            f.write(f"GmailPilot Message IDs - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("=" * 80 + "\n")
            f.write("List of message IDs for future reference and feedback.\n")
            f.write("Format: MESSAGE_ID | Action | Sender | Subject\n\n")
        
        # Statistics for the summary report
        self.kept_count = 0
        self.deleted_count = 0
    
    def log_action(self, message_id, action, email_meta, promo_score, 
                   sbert_promo_score, sbert_importance_score, combined_promo_score, reasons,
                   importance_score=0, is_important=False, importance_reasons=None):
        """
        Records an action performed on an email.
        Note: sbert_promo_score and sbert_importance_score are now SBERT scores 
        but field names are kept for compatibility.
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        sender = email_meta.get("sender", "Unknown")
        subject = email_meta.get("subject", "No subject")
        
        # Update counters for summary
        if action.lower() == "kept":
            self.kept_count += 1
        elif "deleted" in action.lower() or "labelled" in action.lower():
            self.deleted_count += 1
        
        # Text log format with scores and importance info on a single line (s'assurer que les scores ne sont pas négatifs)
        display_promo_score = max(0, promo_score)
        display_combined_score = max(0, combined_promo_score)
        log_entry = f"{timestamp} | ID:{message_id} | {action} | {sender} | {subject} | Scores: Promo: {display_promo_score:.2f} / 10.0 | Combined: {display_combined_score:.2f} / 0.60"
        
        # Add importance information if available
        if importance_score > 0 or is_important:
            importance_status = "IMPORTANT" if is_important else f"Not important (Score: {importance_score:.2f})"
            log_entry += f" | Importance: {importance_status}"
            
        # Add to log file
        with open(self.action_log_path, 'a', encoding='utf-8') as f:
            f.write(log_entry + "\n")
            # Add all reasons on the next line with indentation
            if reasons:
                f.write(f"    Reasons: {', '.join(reasons)}\n")
        
        # Prepare CSV entry (still limit to 3 for CSV readability, s'assurer que les scores ne sont pas négatifs)
        csv_entry = [
            timestamp, 
            message_id, 
            sender, 
            subject, 
            action,
            f"{max(0, promo_score):.2f}",
            f"{max(0, sbert_promo_score):.2f}",  # Actually SBERT score now
            f"{max(0, combined_promo_score):.2f}",
            f"{max(0, importance_score):.2f}",
            f"{max(0, sbert_importance_score):.2f}",  # Actually SBERT importance score now
            str(is_important),
            ", ".join(reasons[:3])  # Limit for CSV readability
        ]
        
        # Add to CSV
        with open(self.csv_log_path, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(csv_entry)
        
        # Add to message IDs file
        with open(self.message_ids_path, 'a', encoding='utf-8') as f:
            importance_tag = " [IMPORTANT]" if is_important else ""
            f.write(f"{message_id} | {action}{importance_tag} | {sender} | {subject}\n")
        
        # Store data for report - store all reasons instead of limiting to 3
        email_data = {
            "message_id": message_id,
            "sender": sender,
            "subject": subject,
            "action": action,
            "promo_score": promo_score,
            "sbert_promo_score": sbert_promo_score,
            "sbert_importance_score": sbert_importance_score,
            "combined_promo_score": combined_promo_score,
            "importance_score": importance_score,
            "is_important": is_important,
            "domain": Utils.extract_domain(sender),
            "reasons": reasons,  # Store all reasons for report
            "timestamp": timestamp
        }
        
        # Add importance reasons if available
        if importance_reasons:
            email_data["importance_reasons"] = importance_reasons
        
        self.classified_data.append(email_data)
        
        # Check if this might be a questionable classification
        is_potential_error = self._check_for_potential_error(action, promo_score, combined_promo_score, sbert_promo_score, sbert_importance_score, importance_score, is_important)
        if is_potential_error:
            self._log_potential_error(message_id, sender, subject, action, promo_score, combined_promo_score, reasons, importance_score, is_important)
            
    def _check_for_potential_error(self, action, promo_score, combined_promo_score, sbert_promo_score, sbert_importance_score, importance_score, is_important):
        """
        Checks if a classification might be an error based on several criteria.
        Note: sbert_promo_score and sbert_importance_score are now SBERT scores.
        """
        # Case 1: High raw score but low combined score (significant disagreement)
        if promo_score > 7 and combined_promo_score < 0.5 and action == "Kept":
            return True
            
        # Case 2: Low raw score but high combined score
        if promo_score < 3 and combined_promo_score > 0.6 and action == "Labelled as Promotion":
            return True
            
        # Case 3: Significant disagreement between SBERT and rules
        if sbert_promo_score > 0.75 and promo_score < 3 and action == "Kept":
            return True
            
        # Case 4: Score very close to threshold
        threshold = config.PROMO_THRESHOLD  # Ideally use the threshold from config.py
        if abs(combined_promo_score - threshold) < 0.05:
            return True
            
        # Case 5: Important email classified as promotional
        if is_important and action == "Labelled as Promotion":
            return True
            
        # Case 6: High importance score but classified as promotional
        if importance_score > 5.0 and action == "Labelled as Promotion":
            return True
            
        # Case 7: Significant conflict between importance and promotion scores
        if importance_score > 4.0 and combined_promo_score > 0.7:
            return True
            
        return False
        
    def _track_potential_error(self, sender, subject, reason_key, error_data):
        """
        Tracks and groups similar potential errors.
        
        Args:
            sender (str): The email sender
            subject (str): The email subject
            reason_key (str): Key identifying the error type
            error_data (dict): Additional error data
            
        Returns:
            tuple: (is_new, occurrence_count) - Whether this is a new entry and the number of occurrences
        """
        # Create a unique key based on sender and subject for similar errors
        if "security" in subject.lower() and "google.com" in sender.lower():
            group_key = "google_security_alert"
        elif "notion.so" in sender and "download" in subject.lower():
            group_key = "notion_template_download"
        else:
            # Use a combination of normalized sender and subject
            # Remove variable characters like dates, numbers, etc.
            normalized_subject = re.sub(r'\d+', 'X', subject)
            normalized_subject = re.sub(r'\s+', '_', normalized_subject.lower())
            domain = Utils.extract_domain(sender)
            group_key = f"{domain}:{normalized_subject[:20]}"
        
        # Add reason_key to differentiate error types from the same email
        error_key = f"{group_key}:{reason_key}"
        
        if error_key not in self.error_tracking:
            self.error_tracking[error_key] = {
                "count": 1,
                "examples": [error_data],
                "sender": sender,
                "subject_pattern": subject
            }
            return True, 1
        else:
            # Add this example to the list if we have fewer than 3 examples
            if len(self.error_tracking[error_key]["examples"]) < 3:
                self.error_tracking[error_key]["examples"].append(error_data)
            
            self.error_tracking[error_key]["count"] += 1
            return False, self.error_tracking[error_key]["count"]
            
    def _log_potential_error(self, message_id, sender, subject, action, promo_score, combined_promo_score, reasons, importance_score, is_important):
        """Logs a potential error to the dedicated file."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Determine severity based on proximity to threshold
        threshold = config.PROMO_THRESHOLD  # Ideally get from config.py
        deviation = abs(combined_promo_score - threshold)
        
        if deviation < 0.05:
            severity = "High"
        elif deviation < 0.1:
            severity = "Medium"
        else:
            severity = "Low"
            
        # Clarify the detection reason for the sender domain
        clarified_reasons = []
        for reason in reasons:
            if "Promotional sender" in reason:
                domain = Utils.extract_domain(sender)
                clarified_reasons.append(f"Promotional sender detected (domain: {domain})")
            elif "Unsubscribe header present" in reason:
                clarified_reasons.append("Unsubscribe link/header detected in email")
            else:
                clarified_reasons.append(reason)
                
        # Create error data for tracking
        error_data = {
            "message_id": message_id,
            "subject": subject,
            "combined_score": combined_promo_score,
            "promo_score": promo_score,
            "importance_score": importance_score,
            "is_important": is_important,
            "severity": severity
        }
        
        # Determine error type for grouping
        if sender in config.CRITICAL_SENDERS and any(keyword in subject.lower() for keyword in config.CRITICAL_KEYWORDS):
            reason_key = "security_alert"
        elif is_important and "labelled" in action.lower():
            reason_key = "important_email_marked_promotional"
        elif importance_score > 4.0 and combined_promo_score > 0.7:
            reason_key = "importance_promo_conflict"
        elif abs(combined_promo_score - threshold) < 0.05:
            reason_key = "threshold_close"
        else:
            reason_key = "other"
            
        # Track the error and check if it's a duplicate
        is_new, occurrence_count = self._track_potential_error(sender, subject, reason_key, error_data)
        
        # Only write to file if it's a new entry or an additional example
        if is_new or occurrence_count <= 3:
            with open(self.errors_path, 'a', encoding='utf-8') as f:
                f.write(f"TIMESTAMP: {timestamp}\n")
                f.write(f"EMAIL: {subject}\n")
                f.write(f"Message ID: {message_id}\n")
                f.write(f"From: {sender}\n")
                f.write(f"Action: {action}\n")
                f.write(f"Scores: Promo: {max(0, promo_score):.2f} / 10.0 | Combined: {max(0, combined_promo_score):.2f} / 0.60\n")
                
                # Add importance information
                if is_important:
                    f.write(f"Importance: IMPORTANT (Score: {importance_score:.2f})\n")
                elif importance_score > 0:
                    f.write(f"Importance: Not Important (Score: {importance_score:.2f})\n")
                
                f.write(f"Reasons: {', '.join(clarified_reasons)}\n")
                f.write(f"Severity: {severity} (deviation from threshold: {deviation:.3f})\n")
                
                # If it's a duplicate but not the first example, indicate how many similar occurrences
                if occurrence_count > 1 and occurrence_count <= 3:
                    f.write(f"Similar Occurrences: {occurrence_count} emails with this pattern\n")
                
                f.write("-" * 80 + "\n\n")
        
        # If it's a new duplicate after the first 3 examples, add a summary entry
        elif occurrence_count > 3 and occurrence_count % 5 == 0:  # Add periodic summaries
            with open(self.errors_path, 'a', encoding='utf-8') as f:
                f.write(f"TIMESTAMP: {timestamp}\n")
                f.write(f"GROUP SUMMARY: Similar emails from {sender}\n")
                f.write(f"Pattern: {subject}\n")
                f.write(f"Total Occurrences: {occurrence_count} similar emails\n")
                f.write(f"Scores Range: Promo: ~{max(0, promo_score):.2f} / 10.0 | Combined: ~{max(0, combined_promo_score):.2f} / 0.60\n")
                f.write(f"Severity: {severity}\n")
                f.write(f"Recommendation: Consider creating a specific rule for these emails\n")
                f.write("-" * 80 + "\n\n")
    
    def generate_report(self, total_scanned, total_labelled, processing_time=None, dry_run=False):
        """
        Generates a report in plain text, markdown and HTML format for processed emails.
        
        Args:
            total_scanned (int): Total number of emails analyzed
            total_labelled (int): Number of emails marked as promotional
            processing_time (str): Time taken to process emails
            dry_run (bool): Whether this was a dry run
            
        Returns:
            dict: Paths to the generated report files
        """
        # Add a summary to the end of the actions.log file
        self._add_actions_log_summary(total_scanned, total_labelled)
        
        # Generate standard text report (for compatibility)
        self._generate_text_report(total_scanned, total_labelled)
        
        # Generate enhanced Markdown report
        self._generate_markdown_report(total_scanned, total_labelled)
        
        # Generate detailed report with all decisions
        self._generate_detailed_report(total_scanned, total_labelled)
        
        # Export all decisions to CSV
        self._export_all_decisions_csv()
        
        # Generate elegant HTML report
        html_path = self._generate_html_report(total_scanned, total_labelled, processing_time, dry_run)
        
        # Display success message only once per session
        if html_path and not self._html_report_displayed:
            print(f"✅ HTML report generated: {os.path.abspath(html_path)}")
            self._html_report_displayed = True
        
        # Return paths to all generated reports
        return {
            'text': os.path.abspath(self.report_path),
            'markdown': os.path.abspath(self.md_report_path),
            'html': html_path if html_path else None,
            'csv': os.path.abspath(self.decisions_csv_path)
        }
        
    def _add_actions_log_summary(self, total_scanned, total_labelled):
        """Adds a summary of actions at the bottom of the actions.log file."""
        # Extract domain statistics
        domain_stats = self._analyze_domain_distribution()
        
        # Sort domains by number of promotional (deleted) emails
        top_promo_domains = sorted(
            domain_stats, 
            key=lambda x: x[1]['promotional'], 
            reverse=True
        )[:10]  # Top 10 domains
        
        # Calculate totals
        total_kept = self.kept_count
        total_deleted = self.deleted_count
        
        # Calculate importance statistics
        important_count = sum(1 for e in self.classified_data if e.get('is_important', False))
        important_kept = sum(1 for e in self.classified_data if e.get('is_important', False) and e.get('action', '').lower() == 'kept')
        important_deleted = sum(1 for e in self.classified_data if e.get('is_important', False) and e.get('action', '').lower() != 'kept')
        
        # Add a separator and summary at the end of the actions file
        with open(self.action_log_path, 'a', encoding='utf-8') as f:
            f.write("\n" + "=" * 80 + "\n")
            f.write(f"SUMMARY - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("-" * 80 + "\n")
            f.write(f"Total emails scanned: {total_scanned}\n")
            f.write(f"Emails kept: {total_kept}\n")
            f.write(f"Emails deleted/labelled: {total_deleted}\n")
            
            # Add importance statistics
            f.write(f"Important emails detected: {important_count}\n")
            if important_deleted > 0:
                f.write(f"⚠️ Important emails marked as promotional: {important_deleted}\n")
            
            if total_scanned > 0:
                f.write(f"Promotional rate: {(total_labelled/total_scanned*100):.1f}%\n")
                if important_count > 0:
                    f.write(f"Important email rate: {(important_count/total_scanned*100):.1f}%\n")
            else:
                f.write(f"Promotional rate: 0%\n")
                f.write(f"Important email rate: 0%\n")
                
            # Add domain statistics
            if top_promo_domains:
                f.write("\nTop promotional domains:\n")
                for domain, stats in top_promo_domains:
                    if stats['promotional'] > 0:
                        f.write(f"- {domain}: {stats['promotional']} emails marked\n")
                        
            # Add statistics about potential errors
            potential_errors = self._extract_error_info()
            if potential_errors:
                f.write(f"\nPotential classification issues: {len(potential_errors)} emails\n")
                
                # Group by error type
                error_types = {}
                for error in potential_errors:
                    error_type = error.get('error_type', 'Unknown')
                    if error_type not in error_types:
                        error_types[error_type] = 0
                    error_types[error_type] += 1
                    
                # Display most common error types
                for error_type, count in sorted(error_types.items(), key=lambda x: x[1], reverse=True):
                    f.write(f"- {error_type}: {count} emails\n")
                    
            f.write("-" * 80 + "\n")
    
    def _generate_text_report(self, total_scanned, total_labelled):
        """Generates a plain text report (historical format)."""
        with open(self.report_path, 'w', encoding='utf-8') as f:
            # Header with timestamp
            f.write(f"GmailPilot Report - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("=" * 80 + "\n\n")
            
            # Summary section
            f.write("📊 SUMMARY\n")
            f.write("-" * 80 + "\n")
            f.write(f"Total emails scanned: {total_scanned}\n")
            f.write(f"Promotional emails found: {total_labelled}\n")
            f.write(f"Emails kept: {self.kept_count}\n")
            f.write(f"Emails deleted/labelled: {self.deleted_count}\n")
            
            if total_scanned > 0:
                f.write(f"Detection rate: {(total_labelled/total_scanned*100):.1f}%\n")
            else:
                f.write(f"Detection rate: 0%\n")
            f.write("-" * 80 + "\n\n")
            
            # Errors section
            has_potential_errors = os.path.getsize(self.errors_path) > 200
            if has_potential_errors:
                f.write("⚠️ POTENTIAL CLASSIFICATION ERRORS\n")
                f.write("-" * 80 + "\n")
                f.write("Some emails showed conflicting classification signals.\n")
                f.write("Check the 'potential_errors.log' file for details.\n\n")
                
            f.write("See full report in 'report.md' and 'detailed_report.md'.\n")
            f.write("-" * 80 + "\n")
    
    def _generate_markdown_report(self, total_scanned, total_labelled):
        """Generates a Markdown report with more details."""
        # Analyze data for additional insights
        domain_distribution = self._analyze_domain_distribution()
        
        with open(self.md_report_path, 'w', encoding='utf-8') as f:
            # Header with timestamp
            f.write(f"# 📊 GmailPilot Report\n\n")
            f.write(f"*Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*\n\n")
            
            # Table of contents / Navigation
            f.write("## Navigation\n\n")
            f.write("- [📊 Summary](#summary)\n")
            f.write("- [🌐 Domain Distribution](#domain-distribution)\n")
            f.write("- [⚠️ Uncertain Classifications](#uncertain-classifications)\n")
            f.write("- [📧 Top Promotional Emails](#top-promotional-emails)\n")
            f.write("- [🔔 Important Emails](#important-emails)\n")
            f.write("- [💡 Recommendations](#recommendations)\n")
            f.write("- [📁 Reports and Logs](#reports-and-logs)\n\n")
            
            # Calculate importance statistics
            important_count = sum(1 for e in self.classified_data if e.get('is_important', False))
            high_importance_count = sum(1 for e in self.classified_data if not e.get('is_important', False) and e.get('importance_score', 0) > 4.0)
            
            # Global summary
            f.write("## Summary\n\n")
            f.write(f"- **Emails analyzed**: {total_scanned}\n")
            f.write(f"- **Promotional emails detected**: {total_labelled}")
            if total_scanned > 0:
                f.write(f" ({(total_labelled/total_scanned*100):.1f}%)\n")
            else:
                f.write(" (0%)\n")
            f.write(f"- **Important emails detected**: {important_count}")
            if total_scanned > 0:
                f.write(f" ({(important_count/total_scanned*100):.1f}%)\n")
            else:
                f.write(" (0%)\n")
            f.write(f"- **Emails kept**: {self.kept_count} ✅\n")
            f.write(f"- **Emails marked/deleted**: {self.deleted_count} 🗑️\n\n")
            
            # Add a section for important emails
            f.write("## Important Emails\n\n")
            
            if important_count > 0 or high_importance_count > 0:
                f.write(f"GmailPilot has identified {important_count} emails as important and {high_importance_count} emails with high importance scores.\n\n")
                
                # Show most recent important emails
                important_emails = [e for e in self.classified_data if e.get('is_important', False)]
                important_emails.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
                
                if important_emails:
                    f.write("### Recently Detected Important Emails\n\n")
                    f.write("| Sender | Subject | Importance Score | Action |\n")
                    f.write("|--------|---------|-----------------|--------|\n")
                    
                    for email in important_emails[:10]:  # Show top 10
                        f.write(f"| {email.get('sender', 'Unknown')} | {email.get('subject', 'No subject')} | {email.get('importance_score', 0):.1f} | {email.get('action', 'Unknown')} |\n")
                    
                    f.write("\n")
                    
                # Show potential importance/promotional conflicts
                conflicts = [e for e in self.classified_data if e.get('is_important', False) and e.get('action', '') == 'Labelled as Promotion']
                if conflicts:
                    f.write("### Important Emails Marked as Promotional ⚠️\n\n")
                    f.write("The following emails were detected as important but also classified as promotional. These might require review:\n\n")
                    f.write("| Sender | Subject | Importance Score | Promo Score |\n")
                    f.write("|--------|---------|-----------------|-------------|\n")
                    
                    for email in conflicts[:10]:  # Show top 10
                        f.write(f"| {email.get('sender', 'Unknown')} | {email.get('subject', 'No subject')} | {email.get('importance_score', 0):.1f} | {email.get('promo_score', 0):.1f} |\n")
                    
                    f.write("\n")
            else:
                f.write("No important emails were detected in this scan.\n\n")
                
            # Domain distribution
            f.write("## Domain Distribution\n\n")
            f.write("### Top 10 Sender Domains\n\n")
            f.write("| Domain | Total | Promotional | % Promo |\n")
            f.write("|---------|-------|--------------|--------|\n")
            
            for domain, stats in domain_distribution[:10]:
                total_count = stats['total']
                promo_count = stats['promotional']
                promo_percent = (promo_count / total_count * 100) if total_count > 0 else 0
                f.write(f"| {domain} | {total_count} | {promo_count} | {promo_percent:.1f}% |\n")
            f.write("\n")
            
            # Analyze potential errors
            potential_errors = self._extract_error_info()
            
            # Uncertain classifications
            if potential_errors:
                error_count = len(potential_errors)
                f.write(f"## Uncertain Classifications\n\n")
                f.write(f"{error_count} emails show contradictory signals or are close to the threshold.\n\n")
                
                f.write("### Examples of Emails with Uncertain Classification\n\n")
                f.write("| Message ID | Sender | Subject | Action | Score | Severity |\n")
                f.write("|------------|------------|-------|--------|-------|----------|\n")
                
                for i, error in enumerate(potential_errors):  # Show all potential errors
                    message_id = error.get('message_id', 'Unknown')
                    sender = error.get('sender', 'Unknown')
                    subject = error.get('subject', 'Unknown')
                    if len(subject) > 25:
                        subject = subject[:22] + "..."
                    action = error.get('action', 'Unknown')
                    score = error.get('combined_score', 0)
                    severity = error.get('severity_level', 'Low')
                    
                    severity_display = {
                        'High': '⚠️ High',
                        'Medium': '⚠ Medium',
                        'Low': '• Low'
                    }.get(severity, severity)
                    
                    f.write(f"| {message_id} | {sender} | {subject} | {action} | {score:.2f} | {severity_display} |\n")
                                    
                f.write("\n> See the `potential_errors.log` or `detailed_report.md` file for more details.\n\n")
            
            # Top promotional emails
            promo_emails = [e for e in self.classified_data if e['action'] == 'Labelled as Promotion']
            if promo_emails:
                # Sort by combined score
                sorted_promos = sorted(promo_emails, key=lambda x: x['combined_promo_score'], reverse=True)
                
                f.write("## Top Promotional Emails\n\n")
                f.write("| Message ID | Sender | Subject | Score | Main Signal |\n")
                f.write("|------------|------------|-------|-------|----------------|\n")
                
                for promo in sorted_promos[:5]:  # Top 5
                    message_id = promo['message_id']
                    sender = promo['sender']
                    subject = promo['subject']
                    if len(subject) > 25:
                        subject = subject[:22] + "..."
                    score = promo['combined_promo_score']
                    reason = promo['reasons'][0] if promo['reasons'] else 'Unknown'
                    
                    f.write(f"| {message_id} | {sender} | {subject} | {score:.2f} | {reason} |\n")
                f.write("\n")
            
            # Recommendations section
            f.write("## Recommendations\n\n")
            
            # Get frequent senders from potential errors
            error_domains = {}
            for error in potential_errors:
                domain = error.get('domain', 'unknown')
                error_domains[domain] = error_domains.get(domain, 0) + 1
            
            top_error_domains = sorted(error_domains.items(), key=lambda x: x[1], reverse=True)
            
            f.write("### Improvement Suggestions\n\n")
            
            # Generate recommendations
            if top_error_domains:
                f.write("- **Adjust thresholds for these domains:**\n")
                for domain, count in top_error_domains[:3]:
                    f.write(f"  - `{domain}` ({count} emails near threshold)\n")
            
            # Check if there are many Google security alerts
            google_security = sum(1 for e in potential_errors if 'google.com' in e.get('sender', '') 
                                and 'Security Alert' in e.get('subject', ''))
            if google_security > 3:
                f.write("- **Create a specific rule** for Google security alerts\n")
            
            f.write("- **Check sensitivity settings** if too many emails are marked as promotional\n")
            f.write("- **Review the potential errors file** to identify recurring patterns\n\n")
            
            # Reports and logs
            f.write("## Reports and Logs\n\n")
            f.write("The following files are available in the logs folder for deeper analysis:\n\n")
            f.write("| File | Description |\n")
            f.write("|---------|-------------|\n")
            f.write("| message_ids.txt | List of message IDs for feedback |\n")
            f.write("| detailed_report.md | Detailed report of all classifications |\n")
            f.write("| all_decisions.csv | Raw data in CSV format |\n")
            f.write("| potential_errors.log | Analysis of emails with uncertain classification |\n")
            
            # Add link to detailed report
            f.write("\nFor more details, see [the detailed report](detailed_report.md).\n")
    
    def _extract_error_info(self):
        """
        Extracts information about potential errors from classified data.
        
        Returns:
            list: List of emails with potential classification issues
        """
        potential_errors = []
        threshold = config.PROMO_THRESHOLD  # Ideally, retrieved from config.py
        
        for email in self.classified_data:
            # Use the same criteria as _check_for_potential_error to verify potential errors
            promo_score = email.get('promo_score', 0)
            combined_score = email.get('combined_promo_score', 0)
            sbert_promo_score = email.get('sbert_promo_score', 0)
            sbert_importance_score = email.get('sbert_importance_score', 0)
            action = email.get('action', '')
            importance_score = email.get('importance_score', 0)
            is_important = email.get('is_important', False)
            
            # Check if the email matches potential error criteria
            is_error = False
            
            # Case 1: High raw score but low combined score
            if promo_score > 7 and combined_score < 0.5 and action == "Kept":
                is_error = True
                
            # Case 2: Low raw score but high combined score
            if promo_score < 3 and combined_score > 0.6 and action == "Labelled as Promotion":
                is_error = True
                
            # Case 3: Significant disagreement between SBERT and rules
            if sbert_promo_score > 0.75 and promo_score < 3 and action == "Kept":
                is_error = True
                
            # Case 4: Score very close to threshold
            if abs(combined_score - threshold) < 0.05:
                is_error = True
                
            # Case 5: Important email classified as promotional
            if is_important and action == "Labelled as Promotion":
                is_error = True
                
            # Case 6: High importance score but classified as promotional
            if importance_score > 5.0 and action == "Labelled as Promotion":
                is_error = True
                
            # Case 7: Significant conflict between importance and promotion scores
            if importance_score > 4.0 and combined_score > 0.7:
                is_error = True
            
            if is_error:
                # Calculate severity
                deviation = abs(combined_score - threshold)
                
                if deviation < 0.05:
                    severity = "High"
                elif deviation < 0.1:
                    severity = "Medium"
                else:
                    severity = "Low"
                
                # Determine error type
                error_type = self._determine_error_type(email)
                
                # Add information
                potential_errors.append({
                    'message_id': email.get('message_id', 'Unknown'),
                    'sender': email.get('sender', 'Unknown'),
                    'subject': email.get('subject', 'Unknown'),
                    'action': email.get('action', 'Unknown'),
                    'promo_score': email.get('promo_score', 0),
                    'combined_score': email.get('combined_promo_score', 0),
                    'sbert_promo_score': email.get('sbert_promo_score', 0),
                    'sbert_importance_score': email.get('sbert_importance_score', 0),
                    'importance_score': email.get('importance_score', 0),
                    'is_important': is_important,
                    'reasons': email.get('reasons', []),
                    'error_type': error_type,
                    'severity_level': severity,
                    'deviation': deviation,
                    'domain': email.get('domain', 'unknown'),
                    'timestamp': email.get('timestamp', 'Unknown')
                })
        
        # Trier par sévérité puis par écart au seuil
        return sorted(potential_errors, key=lambda x: (
            {'High': 0, 'Medium': 1, 'Low': 2}.get(x['severity_level'], 3),
            x['deviation']
        ))
    
    def _analyze_domain_distribution(self):
        """
        Analyzes the distribution of sender domains in emails.
        
        Returns:
            list: Sorted list of tuples (domain, statistics)
        """
        domain_stats = {}
        
        for email in self.classified_data:
            domain = email["domain"]
            is_promo = email["action"] == "Labelled as Promotion"
            
            if domain not in domain_stats:
                domain_stats[domain] = {"total": 0, "promotional": 0}
                
            domain_stats[domain]["total"] += 1
            if is_promo:
                domain_stats[domain]["promotional"] += 1
        
        # Sort domains by total number of emails
        sorted_domains = sorted(domain_stats.items(), key=lambda x: x[1]["total"], reverse=True)
        
        return sorted_domains

    def _export_all_decisions_csv(self):
        """
        Exports all decisions made to a detailed CSV file.
        This file contains absolutely all processed emails with their scores and reasons.
        """
        with open(self.decisions_csv_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(self.detailed_csv_headers)
            
            timestamp_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            for email in self.classified_data:
                # Check if this email is a potential error
                potential_error = self._is_potential_error(email)
                
                # Get all the reasons from the email data
                reasons = email.get("reasons", [])
                
                # Prepare detailed CSV entry (s'assurer que les scores ne sont pas négatifs)
                csv_entry = [
                    timestamp_str,
                    email.get("message_id", "Unknown"),
                    email.get("sender", "Unknown"),
                    email.get("subject", "No subject"),
                    email.get("action", "Unknown"),
                    f"{max(0, email.get('promo_score', 0)):.2f}",
                    f"{max(0, email.get('sbert_promo_score', 0)):.2f}",  # SBERT promo score
                    f"{max(0, email.get('combined_promo_score', 0)):.2f}",
                    f"{max(0, email.get('importance_score', 0)):.2f}",
                    f"{max(0, email.get('sbert_importance_score', 0)):.2f}",  # SBERT importance score
                    str(email.get('is_important', False)),
                    email.get("domain", "unknown"),
                    "; ".join(reasons),  # Include ALL reasons
                    "Yes" if potential_error else "No"
                ]
                
                writer.writerow(csv_entry)
    
    def _determine_error_type(self, email):
        """
        Determines the type of potential error for an email.
        
        Args:
            email (dict): Dictionary containing email information
            
        Returns:
            str: Identified error type
        """
        promo_score = email.get("promo_score", 0)
        combined_score = email.get("combined_promo_score", 0)
        sbert_promo_score = email.get("sbert_promo_score", 0)
        sbert_importance_score = email.get("sbert_importance_score", 0)
        action = email.get("action", "")
        importance_score = email.get("importance_score", 0)
        is_important = email.get("is_important", False)
        threshold = config.PROMO_THRESHOLD
        
        # Check different types of possible errors
        if is_important and action == "Labelled as Promotion":
            return "Important Email Misclassified"
            
        if importance_score > 5.0 and action == "Labelled as Promotion":
            return "High Importance Score Ignored"
            
        if abs(combined_score - threshold) < 0.05:
            return "Threshold Borderline Case"
            
        if promo_score > 7 and combined_score < 0.5 and action == "Kept":
            return "Rule-SBERT Disagreement (High Rule)"
            
        if promo_score < 3 and combined_score > 0.6 and action == "Labelled as Promotion":
            return "Rule-SBERT Disagreement (Low Rule)"
            
        if sbert_promo_score > 0.75 and promo_score < 3 and action == "Kept":
            return "Rule-SBERT Disagreement (High SBERT)"
            
        if importance_score > 4.0 and combined_score > 0.7:
            return "Importance-Promotion Conflict"
            
        # If no specific type is identified, return a generic type
        return "Potential Classification Error"
    
    def _get_error_description(self, error_type):
        """
        Returns a detailed description for each type of classification error.
        
        Args:
            error_type (str): Error type identified by _determine_error_type
            
        Returns:
            str: Explanatory description of the error
        """
        descriptions = {
            "Important Email Misclassified": "Email identified as important but nevertheless classified as promotional",
            "High Importance Score Ignored": "High importance score that was ignored in the final classification",
            "Threshold Borderline Case": "Score very close to decision threshold (difference < 0.05)",
            "Rule-SBERT Disagreement (High Rule)": "Important disagreement: rules indicate promotional, but SBERT does not confirm it",
            "Rule-SBERT Disagreement (Low Rule)": "Important disagreement: rules indicate non-promotional, but SBERT suggests otherwise",
            "Rule-SBERT Disagreement (High SBERT)": "Important disagreement: SBERT strongly indicates promotional, but rules suggest otherwise",
            "Importance-Promotion Conflict": "Conflict between importance indicators and promotional signals",
            "Potential Classification Error": "General inconsistency in classification signals"
        }
        
        # Return description if it exists, otherwise a default description
        return descriptions.get(error_type, "Uncertain classification requiring manual verification")
    
    def _is_potential_error(self, email):
        """
        Determines if an email could represent a classification error.
        
        Args:
            email (dict): Dictionary containing email information
            
        Returns:
            bool: True if the email shows contradictory signals
        """
        promo_score = email.get("promo_score", 0)
        combined_score = email.get("combined_promo_score", 0)
        sbert_promo_score = email.get("sbert_promo_score", 0)
        sbert_importance_score = email.get("sbert_importance_score", 0)
        action = email.get("action", "")
        importance_score = email.get("importance_score", 0)
        is_important = email.get("is_important", False)
        
        # Case 1: High raw score but low combined score (significant disagreement)
        if promo_score > 7 and combined_score < 0.5 and action == "Kept":
            return True
            
        # Case 2: Low raw score but high combined score
        if promo_score < 3 and combined_score > 0.6 and action == "Labelled as Promotion":
            return True
            
        # Case 3: Significant disagreement between SBERT and rules
        if sbert_promo_score > 0.75 and promo_score < 3 and action == "Kept":
            return True
            
        # Case 4: Score very close to threshold
        threshold = config.PROMO_THRESHOLD  # Ideally use threshold from config.py
        if abs(combined_score - threshold) < 0.05:
            return True
            
        # Case 5: Important email classified as promotional
        if is_important and action == "Labelled as Promotion":
            return True
            
        # Case 6: High importance score but classified as promotional
        if importance_score > 5.0 and action == "Labelled as Promotion":
            return True
            
        # Case 7: Significant conflict between importance and promotion scores
        if importance_score > 4.0 and combined_score > 0.7:
            return True
            
        return False
    
    def _generate_detailed_report(self, total_scanned, total_labelled):
        """
        Generates a detailed Markdown report of all classification decisions.
        
        Args:
            total_scanned (int): Total number of emails analyzed
            total_labelled (int): Number of emails marked as promotional
        """
        # Extract potential error data
        potential_errors = self._extract_error_info()
        
        # Group by error type
        error_types = {}
        for error in potential_errors:
            error_type = error['error_type']
            if error_type not in error_types:
                error_types[error_type] = 0
            error_types[error_type] += 1
            
        with open(self.detailed_report_path, 'w', encoding='utf-8') as f:
            # Header and timestamp
            f.write(f"# 📊 GmailPilot Detailed Report\n\n")
            f.write(f"*Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*\n\n")
            
            # Table of contents / Navigation
            f.write("## Navigation\n\n")
            f.write("- [📊 Summary](#summary)\n")
            f.write("- [⚠️ Potential Classification Errors](#potential-classification-errors)\n")
            f.write("- [🔔 Important Emails](#important-emails)\n")
            f.write("- [📋 All Decisions](#all-decisions)\n")
            f.write("  - [📧 Emails Classified as Promotional](#emails-classified-as-promotional)\n")
            f.write("  - [📩 Non-Promotional Emails](#non-promotional-emails)\n")
            f.write("- [📁 Complete Data Files](#complete-data-files)\n\n")
            
            # Calculate importance statistics
            important_count = sum(1 for e in self.classified_data if e.get('is_important', False))
            important_kept = sum(1 for e in self.classified_data if e.get('is_important', False) and e.get('action', '').lower() == 'kept')
            important_deleted = sum(1 for e in self.classified_data if e.get('is_important', False) and e.get('action', '').lower() != 'kept')
            
            # Global summary
            f.write("## Summary\n\n")
            f.write(f"- **Emails analyzed**: {total_scanned}\n")
            f.write(f"- **Promotional emails detected**: {total_labelled}")
            if total_scanned > 0:
                f.write(f" ({(total_labelled/total_scanned*100):.1f}%)\n")
            else:
                f.write(" (0%)\n")
            f.write(f"- **Important emails detected**: {important_count}")
            if total_scanned > 0:
                f.write(f" ({(important_count/total_scanned*100):.1f}%)\n")
            else:
                f.write(" (0%)\n")
            if important_deleted > 0:
                f.write(f"- **⚠️ Important emails marked as promotional**: {important_deleted}\n")
            f.write(f"- **Emails kept**: {self.kept_count} ✅\n")
            f.write(f"- **Emails marked/deleted**: {self.deleted_count} 🗑️\n\n")
            
            # Potential classification errors
            if potential_errors:
                f.write("## Potential Classification Errors\n\n")
                f.write(f"The system detected {len(potential_errors)} potential classification issues, grouped by type:\n\n")
                
                # Display error types
                f.write("| Error Type | Count | Description |\n")
                f.write("|------------|-------|-------------|\n")
                for error_type, count in sorted(error_types.items(), key=lambda x: x[1], reverse=True):
                    description = self._get_error_description(error_type)
                    f.write(f"| {error_type} | {count} | {description} |\n")
                f.write("\n")
                
                # Show most significant errors
                f.write("### Most Significant Classification Issues\n\n")
                f.write("| Sender | Subject | Promo Score | Combined Score | Action | Issue |\n")
                f.write("|--------|---------|-------------|----------------|--------|-------|\n")
                
                # Sort by severity and show top 10
                sorted_errors = sorted(potential_errors, key=lambda x: x.get('severity', 'Low'), reverse=True)
                for error in sorted_errors[:10]:
                    f.write(f"| {error.get('sender', 'Unknown')} | {error.get('subject', 'No subject')} | {error.get('promo_score', 0):.1f} | {error.get('combined_score', 0):.2f} | {error.get('action', 'Unknown')} | {error.get('error_type', 'Unknown')} |\n")
                
                f.write("\n")
                
                # Show detailed classification reasons for potential errors
                f.write("### Detailed Reasons for Potential Errors\n\n")
                for i, error in enumerate(sorted_errors[:10]):
                    message_id = error.get('message_id', 'Unknown')
                    sender = error.get('sender', 'Unknown')
                    subject = error.get('subject', 'No subject')
                    error_type = error.get('error_type', 'Unknown')
                    
                    f.write(f"#### {i+1}. {error_type}: {subject} (from {sender})\n\n")
                    f.write(f"**Message ID**: `{message_id}`\n\n")
                    f.write(f"**Action**: {error.get('action', 'Unknown')}\n\n")
                    f.write(f"**Scores**:\n")
                    f.write(f"- Promo Score: {max(0, error.get('promo_score', 0)):.2f} / 10.0\n")
                    f.write(f"- SBERT Promo Score: {max(0, error.get('sbert_promo_score', 0)):.2f}\n")
                    f.write(f"- SBERT Importance Score: {max(0, error.get('sbert_importance_score', 0)):.2f}\n")
                    f.write(f"- Combined Score: {max(0, error.get('combined_score', 0)):.2f} / {config.PROMO_THRESHOLD:.2f}\n")
                    f.write(f"- Importance Score: {max(0, error.get('importance_score', 0)):.2f}\n\n")
                    
                    # Display all classification reasons
                    if 'reasons' in error and error['reasons']:
                        f.write("**Classification Reasons**:\n")
                        for reason in error['reasons']:
                            f.write(f"- {reason}\n")
                        f.write("\n")
                
                # Show importance-related errors if any
                importance_errors = [e for e in potential_errors if 'important' in e.get('error_type', '').lower()]
                if importance_errors:
                    f.write("### 🔔 Importance Classification Issues\n\n")
                    f.write("| Sender | Subject | Importance Score | Promo Score | Action | Issue |\n")
                    f.write("|--------|---------|------------------|-------------|--------|-------|\n")
                    
                    for error in importance_errors[:10]:
                        f.write(f"| {error.get('sender', 'Unknown')} | {error.get('subject', 'No subject')} | {error.get('importance_score', 0):.1f} | {error.get('promo_score', 0):.1f} | {error.get('action', 'Unknown')} | {error.get('error_type', 'Unknown')} |\n")
                    
                    f.write("\n")
            else:
                f.write("## Potential Classification Errors\n\n")
                f.write("No potential classification errors were detected in this scan.\n\n")
                
            # Important emails section
            f.write("## Important Emails\n\n")
            important_emails = [e for e in self.classified_data if e.get('is_important', False)]
            
            if important_emails:
                f.write(f"{len(important_emails)} emails were classified as important:\n\n")
                f.write("| Sender | Subject | Importance Score | Action | Reasons |\n")
                f.write("|--------|---------|------------------|--------|--------|\n")
                
                # Sort by importance score
                sorted_important = sorted(important_emails, key=lambda x: x.get('importance_score', 0), reverse=True)
                for email in sorted_important:
                    importance_reasons = email.get('importance_reasons', [])
                    reasons_text = "; ".join(importance_reasons[:2]) if importance_reasons else ""
                    f.write(f"| {email.get('sender', 'Unknown')} | {email.get('subject', 'No subject')} | {email.get('importance_score', 0):.1f} | {email.get('action', 'Unknown')} | {reasons_text} |\n")
                
                f.write("\n")
                
                # Detailed important emails section
                f.write("### Detailed Important Email Analysis\n\n")
                for i, email in enumerate(sorted_important[:5]):  # Show top 5 in detail
                    message_id = email.get('message_id', 'Unknown')
                    sender = email.get('sender', 'Unknown')
                    subject = email.get('subject', 'No subject')
                    
                    f.write(f"#### {i+1}. {subject} (from {sender})\n\n")
                    f.write(f"**Message ID**: `{message_id}`\n\n")
                    f.write(f"**Action**: {email.get('action', 'Unknown')}\n\n")
                    f.write(f"**Scores**:\n")
                    f.write(f"- Importance Score: {email.get('importance_score', 0):.2f} / 10.0\n")
                    f.write(f"- Promo Score: {max(0, email.get('promo_score', 0)):.2f} / 10.0\n")
                    f.write(f"- Combined Promo Score: {max(0, email.get('combined_promo_score', 0)):.2f} / {config.PROMO_THRESHOLD:.2f}\n\n")
                    
                    # Display all importance reasons
                    if 'importance_reasons' in email and email['importance_reasons']:
                        f.write("**Importance Factors**:\n")
                        for reason in email['importance_reasons']:
                            f.write(f"- {reason}\n")
                        f.write("\n")
                    
                    # Display all classification reasons
                    if 'reasons' in email and email['reasons']:
                        f.write("**Classification Reasons**:\n")
                        for reason in email['reasons']:
                            f.write(f"- {reason}\n")
                        f.write("\n")
                
                # Add conflict section if any important emails were marked as promotional
                conflicts = [e for e in important_emails if e.get('action', '') == 'Labelled as Promotion']
                if conflicts:
                    f.write("### Important Emails Marked as Promotional\n\n")
                    f.write(f"{len(conflicts)} important emails were mistakenly classified as promotional:\n\n")
                    f.write("| Sender | Subject | Importance Score | Promo Score | Reasons |\n")
                    f.write("|--------|---------|------------------|-------------|--------|\n")
                    
                    for email in conflicts:
                        importance_reasons = email.get('importance_reasons', [])
                        promo_reasons = email.get('reasons', [])
                        reasons = []
                        if importance_reasons:
                            reasons.append(f"Important: {importance_reasons[0]}")
                        if promo_reasons:
                            reasons.append(f"Promo: {promo_reasons[0]}")
                        reasons_text = "; ".join(reasons)
                        
                        f.write(f"| {email.get('sender', 'Unknown')} | {email.get('subject', 'No subject')} | {max(0, email.get('importance_score', 0)):.1f} | {max(0, email.get('promo_score', 0)):.1f} | {reasons_text} |\n")
                    
                    f.write("\n")
            else:
                f.write("No emails were classified as important in this scan.\n\n")
            
            # All decisions
            f.write("\n## All Decisions\n\n")
            f.write("This report includes details for all analyzed emails.\n\n")
            
            # Promotional emails
            promo_emails = [e for e in self.classified_data if e['action'] == 'Labelled as Promotion']
            if promo_emails:
                f.write("### Emails Classified as Promotional\n\n")
                
                # Table format for scores
                f.write("| Message ID | Sender | Subject | Promo Score | Combined Score | Threshold | Main Reasons |\n")
                f.write("|------------|------------|-------|-------------|----------------|-------|---------------------|\n")
                
                # Sort by score
                sorted_promos = sorted(promo_emails, key=lambda x: x['combined_promo_score'], reverse=True)
                for email in sorted_promos:
                    message_id = email['message_id']
                    sender = email['sender']
                    subject = email['subject']
                    # Truncate subject if too long
                    if len(subject) > 25:
                        subject = subject[:22] + "..."
                    promo_score = max(0, email['promo_score'])
                    combined_score = max(0, email['combined_promo_score'])
                    
                    # Include the top reasons, but limit to 2 for table readability
                    reasons = email.get('reasons', [])
                    reasons_text = ", ".join(reasons[:2]) if reasons else "High score"
                    
                    # Determine if it's above threshold
                    threshold_status = "✅ OK" if combined_score >= config.PROMO_THRESHOLD else "⚠️ Close"
                    f.write(f"| {message_id} | {sender} | {subject} | {promo_score:.2f} / 10.0 | {combined_score:.2f} / {config.PROMO_THRESHOLD:.2f} | {threshold_status} | {reasons_text} |\n")
                
                # Add section with detailed analysis of top promotional emails
                f.write("\n### Detailed Promotional Email Analysis\n\n")
                for i, email in enumerate(sorted_promos[:5]):  # Show top 5 in detail
                    message_id = email['message_id']
                    sender = email['sender']
                    subject = email['subject']
                    
                    f.write(f"#### {i+1}. {subject} (from {sender})\n\n")
                    f.write(f"**Message ID**: `{message_id}`\n\n")
                    f.write(f"**Scores**:\n")
                    f.write(f"- Promo Score: {max(0, email['promo_score']):.2f} / 10.0\n")
                    f.write(f"- SBERT Promo Score: {max(0, email['sbert_promo_score']):.2f}\n")
                    f.write(f"- SBERT Importance Score: {max(0, email['sbert_importance_score']):.2f}\n")
                    f.write(f"- Combined Score: {max(0, email['combined_promo_score']):.2f} / {config.PROMO_THRESHOLD:.2f}\n")
                    if 'importance_score' in email and email['importance_score'] > 0:
                        f.write(f"- Importance Score: {email['importance_score']:.2f}\n")
                    f.write("\n")
                    
                    # Display ALL classification reasons
                    if 'reasons' in email and email['reasons']:
                        f.write("**All Classification Reasons**:\n")
                        for reason in email['reasons']:
                            f.write(f"- {reason}\n")
                        f.write("\n")
                
                f.write("\n")
            
            # Non-promotional emails section
            kept_emails = [e for e in self.classified_data if e['action'] == 'Kept']
            if kept_emails:
                f.write("### Non-Promotional Emails\n\n")
                f.write("| Message ID | Sender | Subject | Promo Score | Combined Score | Main Reasons |\n")
                f.write("|------------|------------|-------|-------------|----------------|---------------------|\n")
                
                # Sort by score in descending order to show borderline cases first
                sorted_kept = sorted(kept_emails, key=lambda x: x['combined_promo_score'], reverse=True)
                for email in sorted_kept:
                    message_id = email['message_id']
                    sender = email['sender']
                    subject = email['subject']
                    # Truncate subject if too long
                    if len(subject) > 25:
                        subject = subject[:22] + "..."
                    promo_score = max(0, email['promo_score'])
                    combined_score = max(0, email['combined_promo_score'])
                    
                    # Include the top reasons, but limit to 2 for table readability
                    reasons = email.get('reasons', [])
                    reasons_text = ", ".join(reasons[:2]) if reasons else "Low score"
                    
                    f.write(f"| {message_id} | {sender} | {subject} | {promo_score:.2f} / 10.0 | {combined_score:.2f} / {config.PROMO_THRESHOLD:.2f} | {reasons_text} |\n")
                
                f.write("\n")
                
                # Add section with detailed analysis of borderline non-promotional emails
                borderline_kept = [e for e in sorted_kept if e['combined_promo_score'] > (config.PROMO_THRESHOLD - 0.1)]
                if borderline_kept:
                    f.write("### Borderline Non-Promotional Emails\n\n")
                    f.write("These emails were close to being classified as promotional but were kept:\n\n")
                    
                    for i, email in enumerate(borderline_kept[:5]):  # Show top 5 borderline cases
                        message_id = email['message_id']
                        sender = email['sender']
                        subject = email['subject']
                        
                        f.write(f"#### {i+1}. {subject} (from {sender})\n\n")
                        f.write(f"**Message ID**: `{message_id}`\n\n")
                        f.write(f"**Scores**:\n")
                        f.write(f"- Promo Score: {max(0, email['promo_score']):.2f} / 10.0\n")
                        f.write(f"- SBERT Promo Score: {max(0, email['sbert_promo_score']):.2f}\n")
                        f.write(f"- SBERT Importance Score: {max(0, email['sbert_importance_score']):.2f}\n")
                        f.write(f"- Combined Score: {max(0, email['combined_promo_score']):.2f} / {config.PROMO_THRESHOLD:.2f}\n")
                        if 'importance_score' in email and email['importance_score'] > 0:
                            f.write(f"- Importance Score: {email['importance_score']:.2f}\n")
                        f.write("\n")
                        
                        # Display ALL classification reasons
                        if 'reasons' in email and email['reasons']:
                            f.write("**All Classification Reasons**:\n")
                            for reason in email['reasons']:
                                f.write(f"- {reason}\n")
                            f.write("\n")
                
            # Complete data files section
            f.write("## Complete Data Files\n\n")
            f.write("For a complete analysis, check these files in the log directory:\n\n")
            f.write("- `all_decisions.csv`: Complete data on all emails with scores and reasons\n")
            f.write("- `potential_errors.log`: Detailed log of emails with classification issues\n")
            f.write("- `message_ids.txt`: List of all message IDs for feedback\n")
            f.write("- `actions.log`: Chronological log of all actions taken\n")
            f.write("- `model_report.md`: Report of the model's error analysis (if enabled)\n")
    
    def _generate_html_report(self, total_scanned, total_labelled, processing_time=None, dry_run=False):
        """
        Generate an HTML report.
        
        Args:
            total_scanned (int): Total number of emails analyzed
            total_labelled (int): Number of emails marked as promotional
            processing_time (str): Processing time
            dry_run (bool): If it was a test run
            
        Returns:
            str: Path to the generated HTML file
        """
        try:
            html_reporter = HTMLReporter(template_dir="templates")
            
            # Prepare the report data
            potential_errors = self._extract_error_info()
            domain_distribution = self._analyze_domain_distribution()
            
            # Calculate the actions summary
            actions_summary = {
                'labelled': self.deleted_count,
                'kept': self.kept_count,
                'skipped': total_scanned - (self.deleted_count + self.kept_count),
            }
            
            # Get the most frequent domains
            top_domains = sorted(
                [(domain, stats['total']) 
                 for domain, stats in domain_distribution],
                key=lambda x: x[1], 
                reverse=True
            )[:min(10, len(domain_distribution))]
            
            # Prepare promotional and important emails for display
            promotional_emails = []
            important_emails = []
            
            for email in self.classified_data:
                if email['action'] == 'Labelled as Promotion':
                    promotional_emails.append({
                        'sender': email.get('sender', 'Unknown'),
                        'subject': email.get('subject', 'No subject'),
                        'action': 'labelled',
                        'reasons': email.get('reasons', [])
                    })
                elif email.get('is_important', False):
                    important_emails.append({
                        'sender': email.get('sender', 'Unknown'),
                        'subject': email.get('subject', 'No subject'),
                        'action': 'kept',
                        'reasons': email.get('importance_reasons', [])
                    })
            
            # Generate the HTML report
            html_path = html_reporter.generate_html_report(
                total_scanned=total_scanned,
                total_labelled=total_labelled,
                potential_errors=potential_errors,
                actions_summary=actions_summary,
                top_domains=top_domains,
                processing_time=processing_time,
                dry_run=dry_run,
                promotional_emails=promotional_emails,
                important_emails=important_emails
            )
            
            if html_path:
                # Message moved to calling function to avoid duplicates
                return html_path
            else:
                print("\n❌ Error generating HTML report")
                return None
                
        except Exception as e:
            print(f"\n❌ Error generating HTML report: {e}")
            return None