# src/cli.py

"""
Command-line interface for GmailPilot.
Handles user interactions and presents results from EmailProcessor.
"""

import webbrowser
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, Confirm
from rich.progress import Progress, TextColumn, BarColumn, TimeRemainingColumn, SpinnerColumn

from src.config import config
from src.authenticator import Authenticator
from src.email_manager import EmailManager
from src.email_utils import EmailProcessor
from src.html_reporter import HTMLReporter

import os
import traceback
import shutil
from datetime import datetime

class CLIConsole:
    """
    User interface for GmailPilot.
    Handles user interactions and presents results from EmailProcessor.
    """

    def __init__(self):
        self.console = Console()
        self.authenticator = Authenticator()
        self.manager = None
        self.processor = None
        self.creds = None

        # Clean logs on startup
        self.clean_logs()

    def clean_logs(self):
        """
        Cleans the logs directory by keeping only the two most recent log folders
        """
        logs_dir = "./logs"
        
        if not os.path.exists(logs_dir):
            os.makedirs(logs_dir)
            return
            
        try:
            # Get all log directories
            log_folders = []
            for entry in os.listdir(logs_dir):
                full_path = os.path.join(logs_dir, entry)
                if os.path.isdir(full_path):
                    # Get the folder modification time
                    mtime = os.path.getmtime(full_path)
                    log_folders.append((full_path, mtime))
            
            # Sort by modification time (newest first)
            log_folders.sort(key=lambda x: x[1], reverse=True)
            
            # Keep only the two most recent logs
            logs_to_keep = log_folders[:2]
            
            # Delete all other logs
            for folder_path, _ in log_folders[2:]:
                self.console.print(f"[dim]Cleaning old log: {os.path.basename(folder_path)}[/dim]")
                shutil.rmtree(folder_path)
            
            # Log cleaning summary
            if len(log_folders) > 2:
                cleaned_count = len(log_folders) - 2
                self.console.print(f"[dim]Cleaned {cleaned_count} old log folder(s), kept 2 recent ones.[/dim]")
        
        except Exception as e:
            # Log the error but don't stop program execution
            self.console.print(f"[dim]Warning: Error cleaning logs: {str(e)}[/dim]")

    def authenticate(self):
        """Authenticates the user and initializes the email manager and processor"""
        try:
            self.creds = self.authenticator.authenticate()
            if not self.creds:
                self.console.print("[bold red]Failed to authenticate.\nPlease check your credentials and/or your Internet connection.[/bold red]")
                exit(1)
            
            self.manager = EmailManager(self.creds)
            self.processor = EmailProcessor(self.manager)
            
            return self.creds
        except KeyboardInterrupt:
            self.console.print("\n[bold yellow]Authentication process interrupted by user.[/bold yellow]")
            return None
        except Exception as e:
            self.console.print(f"[bold red]An error occurred during authentication: {e}[/bold red]")
            self.console.print(f"[dim]{traceback.format_exc()}[/dim]")
            return None

    def display_header(self):
        """Displays the application header with style"""
        self.console.print(Panel.fit(
            "[bold blue]GmailPilot[/bold blue] [white]v1[/white]\n[italic]Simplified email cleaning for Gmail[/italic]",
            border_style="green",
            title="[yellow]GmailPilot[/yellow]",
            subtitle="[cyan]Developed by 0xMR007[/cyan]",
        ))
        print("\n")

    def display_menu(self):
        """Display main menu options"""
        self.console.print("\n[bold cyan]Choose an option:[/bold cyan]")
        self.console.print("1. 🔍 Analyze emails (Dry Run Mode)")
        self.console.print("2. 📦 Process emails (Active Mode)")
        self.console.print("3. 🧪 Test Gmail API Connection")
        self.console.print("4. 📄 Generate HTML report from existing logs")
        self.console.print("5. 🤖 Train/Retrain AI Model")
        self.console.print("6. 🚪 Exit")

    def create_progress_bar(self):
        """
        Creates and returns a standard progress bar.
        """
        return Progress(
            SpinnerColumn(),
            TextColumn("[bold blue]{task.description}[/bold blue]"),
            BarColumn(bar_width=40),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TimeRemainingColumn(),
        )

    def process_emails(self, dry_run=False):
        """
        Process emails using the EmailProcessor and display results.
        """
        self.console.print("\n[bold]Processing emails...[/bold]")

        # Ask user how many emails to process with performance guidance
        self.console.print("\n[cyan]How many emails would you like to process ?[/cyan]")
        if getattr(config, 'FAST_MODE', False):
            self.console.print("[dim]🚀 Fast mode is enabled - processing will be optimized for speed[/dim]")
        
        self.console.print("[dim]Enter a number (e.g., 50, 100, 500 - higher numbers will take more time) or press Enter for max emails[/dim]")
        
        max_emails_input = Prompt.ask(
            "[cyan]Number of emails[/cyan]",
            default="max",
            show_default=True
        )
        
        # Parse the input
        max_emails = None
        if max_emails_input.lower() != "max":
            try:
                max_emails = int(max_emails_input)
                if max_emails <= 0:
                    self.console.print("[bold red]❌ Please enter a positive number.[/bold red]")
                    return
                    
                # Performance warning for large numbers
                if max_emails > 200:
                    self.console.print(f"[yellow]⚠️ Processing {max_emails} emails may take several minutes.[/yellow]")
                    if not Prompt.ask("[yellow]Continue? (y/n)[/yellow]", default="y").lower().startswith('y'):
                        return
                
                self.console.print(f"[green]✓ Will process up to {max_emails} emails.[/green]")
            except ValueError:
                self.console.print("[bold red]❌ Invalid input. Please enter a number or 'max'.[/bold red]")
                return
        else:
            self.console.print("[green]Will process all available emails.[/green]")
            # Show estimate based on configuration
            if hasattr(config, 'MAX_RESULTS'):
                self.console.print(f"[dim](Limited to {config.MAX_RESULTS} emails by configuration)[/dim]")

        try:
            # Create a single progress bar for all operations
            with self.create_progress_bar() as progress:
                # Single task that covers all operations
                main_task = progress.add_task("[green]Starting...", total=100, visible=False)
                
                # Progress callback function that updates the single task
                def progress_callback(step_name, current, total):
                    if total > 0:
                        # Calculate percentage for this step
                        step_percentage = (current / total) * 100
                        
                        # Map steps to overall progress ranges
                        if "Retrieving emails" in step_name:
                            overall_progress = step_percentage * 0.1  # 0-10%
                        elif "Retrieving metadata" in step_name:
                            overall_progress = 10 + (step_percentage * 0.2)  # 10-30%
                        elif "Analyzing emails" in step_name:
                            overall_progress = 30 + (step_percentage * 0.6)  # 30-90%
                        elif "Applying labels" in step_name:
                            overall_progress = 90 + (step_percentage * 0.1)  # 90-100%
                        else:
                            overall_progress = step_percentage
                        
                        # Update the single progress bar
                        progress.update(
                            main_task, 
                            completed=min(round(overall_progress), 100),
                            description=f"[green]{step_name}[/green]",
                            visible=True
                        )

                # Start processing with max_emails limit
                result = self.processor.process_emails(
                    dry_run=dry_run,
                    progress_callback=progress_callback,
                    max_emails=max_emails
                )
                
                # Ensure progress reaches 100%
                progress.update(main_task, completed=100, description="[green]Done![/green]")

            # Display results
            self._display_processing_results(result, dry_run)
            
            # Handle post-processing actions
            self._handle_post_processing(result, dry_run)
            
        except Exception as e:
            self.console.print(f"[bold red]An error occurred during email processing: {e}[/bold red]")
            self.console.print("If this error persists, check your internet connection and Gmail API permissions.")

    def _display_processing_results(self, result, dry_run):
        """Display the results of email processing."""
        summary = self.processor.get_processing_summary(result)
        
        self.console.print()
        self.console.print(f"[bold]Summary:[/bold]")
        self.console.print(f"Total emails retrieved: {summary['total_retrieved']}")
        
        if summary['skipped_count'] > 0:
            self.console.print(f"[yellow]Emails skipped (CATEGORY_UPDATES): {summary['skipped_count']}[/yellow]")
            
        self.console.print(f"Emails analyzed: {summary['total_analyzed']}")
        self.console.print(f"Promotional emails found: {summary['promotional_count']} ({summary['promotional_rate']:.1f}% of analyzed emails)")
        self.console.print(f"Important emails found: {summary['important_count']} ({summary['important_rate']:.1f}% of analyzed emails)")
        
        if summary['important_conflicts'] > 0:
            self.console.print(f"[bold yellow]⚠️ Important emails that would have been marked as promotional: {summary['important_conflicts']}[/bold yellow]")
        
        if not dry_run and summary['promotional_count'] > 0:
            self.console.print(f"[green]\nMoved {summary['promotional_count']} promotional emails to '{config.TARGET_FOLDER}'[/green]")
        
        # Display generated reports
        if result.report_paths:
            self.console.print(f"\n[bold]Reports generated:[/bold]")
            if result.report_paths.get('html'):
                self.console.print(f"📄 HTML Report: {os.path.abspath(result.report_paths['html'])}")
            if result.report_paths.get('markdown'):
                self.console.print(f"📝 Detailed Report: {os.path.abspath(result.report_paths['markdown'])}")
            if result.report_paths.get('csv'):
                self.console.print(f"📊 CSV Export: {os.path.abspath(result.report_paths['csv'])}")

    def _handle_post_processing(self, result, dry_run):
        """Handle post-processing actions like opening reports or confirming moves."""
        # Show warning for dry run
        if dry_run:
            self.console.print(f"\n[bold yellow]⚠️ WARNING: Please review the classification results in the /logs directory before proceeding.[/bold yellow]")
        
        # Offer to open HTML report
        if result.report_paths.get('html'):
            if Confirm.ask("\n[cyan]Would you like to open the report in your browser ?[/cyan]", default=True):
                try:
                    webbrowser.open(f"file://{os.path.abspath(result.report_paths['html'])}")
                    self.console.print("[green]✅ Report opened in browser.[/green]")
                except Exception as e:
                    self.console.print(f"[yellow]⚠️ Could not open browser: {e}[/yellow]")
                    self.console.print(f"[yellow]You can manually open: file://{os.path.abspath(result.report_paths['html'])}[/yellow]")
        
        # For dry run, offer to actually move emails
        if dry_run and result.promotional_ids:
            self.console.print("\n[bold]Would you like to move the identified promotional emails now?[/bold]")
            if Confirm.ask("Move promotional emails to the specified folder"):
                try:
                    # Use console status instead of progress bar to avoid conflicts
                    with self.console.status(f"[bold green]Moving {len(result.promotional_ids)} promotional emails...", spinner="dots"):
                        success = self.manager.batch_apply_label(
                            result.promotional_ids, 
                            config.TARGET_FOLDER
                        )
                    
                    if success:
                        self.console.print("[bold green]\n✓ Promotional emails have been moved successfully.[/bold green]")
                    else:
                        # Check partial success
                        success = self.manager.verify_labels_applied(
                            result.promotional_ids, 
                            self.manager.get_label_id()
                        )
                        if success:
                            self.console.print("[bold yellow]⚠️ Some promotional emails were moved, but not all of them.[/bold yellow]")
                            self.console.print("This may happen due to rate limits or permission issues with the Gmail API.")
                        else:
                            self.console.print("[bold red]❌ Failed to move emails. This could be due to:[/bold red]")
                            self.console.print("  - Gmail API rate limits exceeded")
                            self.console.print("  - Missing permissions for modifying labels")
                            self.console.print("  - The label 'GmailPilot' doesn't exist or couldn't be created")
                    
                    if success:
                        self.console.print(f"[green]\nMoved {len(result.promotional_ids)} promotional emails to '{config.TARGET_FOLDER}'[/green]")
                        
                except Exception as e:
                    self.console.print(f"[bold red]Error moving emails: {e}[/bold red]")

    def generate_html_from_logs(self):
        """Generate an HTML report from existing logs."""
        try:
            
            self.console.print("\n[bold]Generate HTML Report from Logs[/bold]")
            
            # Check if the logs directory exists
            logs_dir = "./logs"
            if not os.path.exists(logs_dir):
                self.console.print("[bold red]❌ No logs directory found.[/bold red]")
                self.console.print("Run email processing first to generate logs.")
                return
                
            # List the available log folders
            log_folders = [d for d in os.listdir(logs_dir) 
                          if os.path.isdir(os.path.join(logs_dir, d))]
            
            if not log_folders:
                self.console.print("[bold red]❌ No log folders found.[/bold red]")
                return
                
            # Sort by modification date (newest first)
            log_folders.sort(key=lambda x: os.path.getmtime(os.path.join(logs_dir, x)), reverse=True)
            
            self.console.print(f"\n[cyan]Available log sessions:[/cyan]")
            for i, folder in enumerate(log_folders[:10], 1):  # Afficher max 10 sessions
                folder_path = os.path.join(logs_dir, folder)
                mtime = os.path.getmtime(folder_path)
                date_str = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M:%S")
                self.console.print(f"{i}. {folder} ({date_str})")
                
            if len(log_folders) > 10:
                self.console.print(f"... and {len(log_folders) - 10} more sessions")
            
            # Ask the user to choose a log session
            choice = Prompt.ask(
                f"\n[cyan]Choose a log session (1-{min(len(log_folders), 10)})[/cyan]",
                default="1"
            )
            
            try:
                choice_idx = int(choice) - 1
                if choice_idx < 0 or choice_idx >= min(len(log_folders), 10):
                    raise ValueError()
                    
                selected_folder = log_folders[choice_idx]
                
            except (ValueError, IndexError):
                self.console.print("[bold red]❌ Invalid choice.[/bold red]")
                return
                
            # Paths to the log files
            log_path = os.path.join(logs_dir, selected_folder)
            actions_log = os.path.join(log_path, "actions.log")
            errors_log = os.path.join(log_path, "potential_errors.log")
            
            # Check if the files exist
            if not os.path.exists(actions_log):
                self.console.print(f"[bold red]❌ Actions log not found: {actions_log}[/bold red]")
                return
                
            self.console.print(f"\n[green]📊 Generating HTML report from: {selected_folder}[/green]")
            
            with self.console.status("[bold green]Generating HTML report...", spinner="dots"):
                # Initialize the HTML reporter (same way as the working script)
                html_reporter = HTMLReporter()
                
                # Generate the report
                html_path = html_reporter.generate_report_from_logs(
                    actions_log_path=actions_log,
                    errors_log_path=errors_log,
                    processing_time="N/A (from logs)",
                    dry_run=False  # We can't know if it was a dry run
                )
                
            if html_path and os.path.exists(html_path):
                self.console.print(f"[bold green]✅ HTML report generated from logs successfully![/bold green]")
                self.console.print(f"📄 File: {os.path.basename(html_path)}")
                self.console.print(f"📂 Location: {os.path.dirname(html_path)}")
                
                # Ask if the user wants to open the report
                if Confirm.ask("\n[cyan]Would you like to open the report in your browser?[/cyan]", default=True):
                    try:
                        webbrowser.open(f"file://{os.path.abspath(html_path)}")
                        self.console.print("[green]✅ Report opened in browser.[/green]")
                    except Exception as e:
                        self.console.print(f"[yellow]⚠️ Could not open browser: {e}[/yellow]")
                        self.console.print(f"[yellow]You can manually open: file://{os.path.abspath(html_path)}[/yellow]")
                        
            else:
                self.console.print("[bold red]❌ Failed to generate HTML report.[/bold red]")
                
        except ImportError:
            self.console.print("[bold red]❌ HTML reporter not available.[/bold red]")
            self.console.print("Make sure Jinja2 is installed : pip install jinja2")
        except Exception as e:
            self.console.print(f"[bold red]❌ Error generating HTML report: {e}[/bold red]")

    def test_gmail_connection(self):
        try:
            self.authenticator.test_gmail_api(self.manager.service)
        except Exception as e:
            self.console.print(f"[bold red]❌ Error testing Gmail connection: {e}[/bold red]")
            self.console.print("Please check your Gmail API credentials and permissions.")

    def train_ai_model(self):
        """Train or retrain the SBERT AI model."""
        try:
            self.console.print("\n[bold]🤖 AI Model Training[/bold]")
            
            from src.sbert_classifier import SBertClassifier
            from src.config import config
            
            # Check if training data exists
            training_path = config.TRAINING_PATH
            if not os.path.exists(training_path):
                self.console.print(f"[bold red]❌ Training data not found: {training_path}[/bold red]")
                self.console.print("Please ensure the training data file exists before training the model.")
                return
            
            # Check if model already exists
            model_exists = os.path.exists(config.MODEL_PATH)
            if model_exists:
                self.console.print(f"[yellow]⚠️ A trained model already exists at: {config.MODEL_PATH}[/yellow]")
                if not Confirm.ask("Do you want to retrain the model? This will overwrite the existing model"):
                    self.console.print("[yellow]Training cancelled.[/yellow]")
                    return
            
            # Show training data info
            try:
                import pandas as pd
                df = pd.read_csv(training_path)
                total_samples = len(df)
                label_counts = df['label'].value_counts()
                
                self.console.print(f"\n[cyan]Training data information:[/cyan]")
                self.console.print(f"📄 File: {os.path.basename(training_path)}")
                self.console.print(f"📊 Total samples: {total_samples}")
                for label, count in label_counts.items():
                    label_name = "Promotional" if label == 1 else "Important"
                    percentage = (count / total_samples) * 100
                    self.console.print(f"   • {label_name}: {count} samples ({percentage:.1f}%)")
                    
            except Exception as e:
                self.console.print(f"[yellow]⚠️ Could not read training data details: {e}[/yellow]")
            
            # Confirm training
            self.console.print(f"\n[bold]This will train a new SBERT model for email classification.[/bold]")
            self.console.print("[dim]Note: Training may take a few minutes and requires internet connection to download the SBERT model.[/dim]")
            
            if not Confirm.ask("\n[cyan]Proceed with training?[/cyan]", default=True):
                self.console.print("[yellow]Training cancelled.[/yellow]")
                return
            
            # Initialize classifier and train
            self.console.print("\n[bold green]🚀 Starting model training...[/bold green]")
            
            with self.console.status("[bold green]Training AI model (this may take a few minutes)...", spinner="dots"):
                classifier = SBertClassifier()
                success = classifier.train(training_path)
            
            if success:
                self.console.print("[bold green]✅ Model trained successfully![/bold green]")
                self.console.print(f"📁 Model saved to: {config.MODEL_PATH}")
                self.console.print("\n[green]The AI model is now ready to use for email classification.[/green]")
                
                # Test the model with a simple prediction
                try:
                    test_text = "Get 50% off on all products! Limited time offer!"
                    predictions = classifier.predict(test_text)
                    if predictions:
                        top_pred = predictions[0]
                        self.console.print(f"\n[dim]✓ Quick test: '{test_text[:50]}...' → {top_pred[0]} ({top_pred[1]:.2f} confidence)[/dim]")
                except:
                    pass  # Test failed, but training succeeded
                    
            else:
                self.console.print("[bold red]❌ Model training failed![/bold red]")
                self.console.print("Please check:")
                self.console.print("• Internet connection (required to download SBERT model)")
                self.console.print("• Training data format (CSV with 'text' and 'label' columns)")
                self.console.print("• Available disk space for model storage")
                
        except ImportError as e:
            self.console.print(f"[bold red]❌ Required libraries not installed: {e}[/bold red]")
            self.console.print("Please run: pip install sentence-transformers scikit-learn")
        except Exception as e:
            self.console.print(f"[bold red]❌ Error during model training: {e}[/bold red]")
            self.console.print("Check the logs for more details.")