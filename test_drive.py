from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
scopes = ['https://www.googleapis.com/auth/drive']
creds = Credentials.from_service_account_file('service_account.json', scopes=scopes)
service = build('drive', 'v3', credentials=creds)
query = "name='veluna_task' and mimeType='application/vnd.google-apps.folder' and trashed=false"
try:
    results = service.files().list(q=query, supportsAllDrives=True, includeItemsFromAllDrives=True).execute()
    print(results.get('files', []))
except Exception as e:
    print(e)
