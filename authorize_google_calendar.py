from google_auth_oauthlib.flow import InstalledAppFlow

from reply_config import (
    GOOGLE_OAUTH_CREDENTIALS_FILE,
    GOOGLE_OAUTH_TOKEN_FILE,
)

SCOPES = [
    "https://www.googleapis.com/auth/calendar",
]


def authorize_google_calendar() -> None:
    if not GOOGLE_OAUTH_CREDENTIALS_FILE.exists():
        raise FileNotFoundError(
            "credentials.json was not found. Download a Google OAuth Desktop App "
            "credentials file and place it in this workflow folder."
        )

    flow = InstalledAppFlow.from_client_secrets_file(
        str(GOOGLE_OAUTH_CREDENTIALS_FILE),
        SCOPES,
    )

    credentials = flow.run_local_server(port=0)

    GOOGLE_OAUTH_TOKEN_FILE.write_text(
        credentials.to_json(),
        encoding="utf-8",
    )

    print("Google Calendar authorization completed.")
    print(f"Token saved to: {GOOGLE_OAUTH_TOKEN_FILE}")


if __name__ == "__main__":
    authorize_google_calendar()
