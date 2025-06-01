# src/main.py

"""
Main module for GmailPilot.
Handles the main loop and user interactions.
"""

import os
import sys
import time
from rich.prompt import Prompt

from src.cli import CLIConsole

def main():
    """Main function of the program"""
    
    console = CLIConsole()
    
    try:
        # Display the header
        console.display_header()
        
        # Initialize credentials with status indication
        with console.console.status("[bold green]Connecting to Gmail...[/bold green]", spinner="dots"):
            creds = console.authenticate()
        
        if not creds:
            console.console.print("[bold red]Failed to connect to Gmail API. Please check your credentials or try again.[/bold red]")
            sys.exit(1)
        
        console.console.print(f"[dim green]✓ Ready[/dim green]\n")
        
        # Main loop
        while True:
            console.display_menu()
            choice = Prompt.ask("\n[bold cyan]Your choice[/bold cyan]", choices=["1", "2", "3", "4", "5", "6"], default="1")
            
            if choice == "6":
                console.console.print("[bold green]Thank you for using GmailPilot. See you soon ![/bold green]")
                break
            elif choice == "1":
                console.process_emails(dry_run=True)
            elif choice == "2":
                console.process_emails(dry_run=False)
            elif choice == "3":
                console.test_gmail_connection()
            elif choice == "4":
                console.generate_html_from_logs()
            elif choice == "5":
                console.train_ai_model()
            
            # Pause before returning to the menu
            if choice != "6":
                console.console.print()
                Prompt.ask("[bold cyan]Press [Enter] to continue[/bold cyan]")
                if sys.stdout.isatty():
                    os.system('cls' if os.name == 'nt' else 'clear')
                console.display_header()
    
    except KeyboardInterrupt:
        console.console.print("\n[bold yellow]Program interrupted by the user.[/bold yellow]")
        sys.exit(0)
    except Exception as e:
        console.console.print(f"\n[bold red]An unexpected error occurred: {e}[/bold red]")
        # In debug mode, show more details
        if getattr(console, 'debug_mode', False):
            import traceback
            console.console.print(f"[dim]{traceback.format_exc()}[/dim]")
        sys.exit(1)


if __name__ == "__main__":
    main()