import os
from googleapiclient.discovery import build
from datetime import datetime, timedelta
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']

def authenticate_google_api():
    creds = None
    if os.path.exists('google_auth.token.json'):
        creds = Credentials.from_authorized_user_file('google_auth.token.json', SCOPES)
    if not creds or not creds.valid:
        print("Authenticating with Google API...")
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file('google_calender.secret.json', SCOPES)
            creds = flow.run_local_server(
                host='localhost',
                port=8091,
                authorization_prompt_message='Please visit this URL: {url}',
                success_message='The auth flow is complete; you may close this window.',
                open_browser=True
            )
        with open('google_auth.token.json', 'w') as token:
            token.write(creds.to_json())
    else:
        print("Using cached credentials")
    return creds

def get_calendar_events(date):
    creds = authenticate_google_api()
    service = build('calendar', 'v3', credentials=creds)
    date_start = datetime.strptime(date, '%Y-%m-%d')
    date_end = date_start + timedelta(days=1)

    time_min = date_start.isoformat() + 'Z'
    time_max = date_end.isoformat() + 'Z'

    events_result = service.events().list(
        calendarId='primary',
        timeMin=time_min,
        timeMax=time_max,
        singleEvents=True,
        orderBy='startTime'
    ).execute()

    events = events_result.get('items', [])
    return events


def get_calendar_events_func_def():
    return {
        "type": "function",
        "function": {
            "name": "get_calendar_events",
            "description": "Retrieve calendar events for a specific date from Google Calendar.",
            "parameters": {
                "type": "object",
                "properties": {
                    "date": {
                        "type": "string",
                        "description": "The date to retrieve events for, in 'YYYY-MM-DD' format.",
                    },
                },
                "required": ["date"],
                "additionalProperties": False,
            },
        }
    }
