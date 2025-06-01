# src/authenticator.py

"""
Handles Gmail API authentication.
"""

import os
import time

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.errors import HttpError

class Authenticator:
    """
    Handles Gmail API authentication.
    """
    SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]

    def __init__(self):
        self.creds = None

    def authenticate(self):
        try:
            token_path = "token.json"
            creds_path = "credentials.json"
            
            # First check that the credentials file exists
            if not os.path.exists(creds_path):
                print(f"Error: {creds_path} not found. Please download it from Google Cloud Console.")
                return None
                
            # Check existing token
            if os.path.exists(token_path):
                self.creds = Credentials.from_authorized_user_file(token_path, self.SCOPES)
                
                # Valid token
                if self.creds and self.creds.valid:
                    print("Token is valid, Gmail API can be accessed.")
                    return self.creds
                    
                # Expired token but with refresh_token
                elif self.creds and self.creds.expired and self.creds.refresh_token:
                    try:
                        self.creds.refresh(Request())
                        with open(token_path, "w") as token_file:
                            token_file.write(self.creds.to_json())
                        print("Token refreshed and saved.")
                        return self.creds
                    except Exception as refresh_error:
                        print(f"Error refreshing token: {refresh_error}")
                        # Continue with new authentication flow
                
            # Need new authentication flow
            flow = InstalledAppFlow.from_client_secrets_file(creds_path, self.SCOPES)
            self.creds = flow.run_local_server(port=0)
            
            # Save new token
            with open(token_path, "w") as token_file:
                token_file.write(self.creds.to_json())
            print("New token saved.")
            return self.creds
        
        except KeyboardInterrupt:
            print("Authentication process interrupted by user.")
            return None

        except Exception as e:
            print(f"Authentication error: {e}")
            return None
        
    def test_gmail_api(self, service):
        """
        Test the connection to the Gmail API.
        """
        try:
            start = time.time()
            results = service.users().labels().list(userId="me").execute()
            labels = results.get("labels", [])
            end = time.time()
            
            if not labels:
                print("❌ No labels found.")
            else:
                print("✅ Connection to Gmail API successful.")
                print(f"Found {len(labels)} labels in {round(end - start, 2)}s.")
            return True
        except HttpError as error:
            print(f"An HTTP error occurred: {error}")
            return False
        except Exception as e:
            print(f"An error occurred: {e}")
            return False