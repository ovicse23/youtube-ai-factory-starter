#!/usr/bin/env python3
"""OAuth-based YouTube PRIVATE upload; approval required.
Requires the official google API client requirements and client_secrets.json.
"""
import argparse
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
SCOPES=["https://www.googleapis.com/auth/youtube.upload"]

def main():
    p=argparse.ArgumentParser()
    p.add_argument("slug")
    p.add_argument("--confirm-private-upload", action="store_true")
    a=p.parse_args()
    folder=ROOT/"episodes"/a.slug
    episode=json.loads((folder/"episode.json").read_text())
    video=folder/"output"/"final.mp4"
    if not video.exists(): raise SystemExit("First render the video using factory.py render")
    if episode.get("status") not in ("approved-for-upload","private-uploaded"):
        raise SystemExit("Approval required: review video and edit episode.json status to approved-for-upload.")
    if not a.confirm_private_upload:
        print("DRY RUN — no upload. Add --confirm-private-upload to authenticate and upload privately.")
        return
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload
    from googleapiclient.errors import HttpError
    secrets=ROOT/".secrets"; secrets.mkdir(exist_ok=True)
    client=secrets/"client_secrets.json"
    if not client.exists(): raise SystemExit(f"Missing Google OAuth desktop JSON at {client}")
    token=secrets/"youtube_token.json"
    creds=None
    if token.exists(): creds=Credentials.from_authorized_user_file(str(token),SCOPES)
    if creds and creds.expired and creds.refresh_token: creds.refresh(Request())
    if not creds or not creds.valid:
        creds=InstalledAppFlow.from_client_secrets_file(str(client),SCOPES).run_local_server(port=0)
    token.write_text(creds.to_json())
    yt=build("youtube","v3",credentials=creds)
    seo=episode["seo"]
    body={"snippet":{"title":seo.get("title") or episode["title"],
         "description":seo.get("description", ""),"tags":seo.get("tags", []),"categoryId":"1"},
         "status":{"privacyStatus":"private","selfDeclaredMadeForKids":False}}
    # The made-for-kids flag above is an EXAMPLE ONLY. The uploader must classify the
    # actual video truthfully before uploading and change it if content is directed at children.
    if episode.get("made_for_kids") not in (True,False):
        raise SystemExit("Set made_for_kids true/false explicitly in episode.json before uploading")
    body["status"]["selfDeclaredMadeForKids"]=episode["made_for_kids"]
    body["status"]["containsSyntheticMedia"]=bool(episode.get("contains_synthetic_media", True))
    previous=folder/"youtube-upload-result.json"
    if previous.exists(): raise SystemExit("Previous upload record exists. Inspect it to avoid duplicate uploads.")
    req=yt.videos().insert(part="snippet,status",body=body,media_body=MediaFileUpload(str(video),mimetype="video/mp4",chunksize=1024*1024*8,resumable=True))
    result=None
    try:
        while result is None:
            progress,result=req.next_chunk()
            if progress: print("Uploading:",round(progress.progress()*100),"%")
    except HttpError as err: raise SystemExit(f"YouTube upload error: {err}")
    previous.write_text(json.dumps(result,indent=2))
    episode["status"]="private-uploaded"
    (folder/"episode.json").write_text(json.dumps(episode,indent=2,ensure_ascii=False)+"\n")
    print("Uploaded PRIVATELY:",result.get("id")," — review in YouTube Studio before making public.")

if __name__ == "__main__": main()
