# BM4088 ICA1 SAQ Marking Assistant

A Streamlit web app that helps tutors mark the Short Answer Question (SAQ) section of ICA1 (PRAC1) for **BM4088 Data Science Fundamentals & Analytics** at Nanyang Polytechnic, School of Business Management.

The app uses Claude (claude-sonnet-4-6) to suggest a performance band and rubric-aligned justification for each student submission. The marker retains final decision authority.

---

## Features

- **Password-gated access** — each marker logs in with their own password; usage is attributed per marker in the log
- **Question-aware marking** — sidebar buttons for Q1–Q4 pass the selected question to the model so rubric and expected solutions are applied correctly
- **Text and image input** — accepts typed/pasted student responses and optional screenshot uploads (JPG/PNG)
- **Prompt injection guard** — detects and blocks attempts to hijack the model's instructions
- **Structured AI output** — always returns recommended band, rubric justification, comparison against expected solutions, gap-to-next-band, and confidence level
- **Google Sheets logging** — each submission is logged with timestamp (SGT), marker ID, question, whether an image was included, and the recommended band
- **Keyboard shortcut** — Ctrl+Enter submits from the text area

---

## Questions Covered

| Question | Topic | Marks | Variants |
|---|---|---|---|
| Q1 | Problem Statement | 5 | A, B, C |
| Q2 | Exploratory Data Analysis | 5 | A, B, C |
| Q3 | Data Preparation (Power Query) | 5 | A, B, C |
| Q4 | Visualisation, Interpretation & Formatting | 10 | A, B, C |

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | [Streamlit](https://streamlit.io) |
| AI | [Anthropic Claude](https://www.anthropic.com) (`claude-sonnet-4-6`, `temperature=0`) |
| Logging | [gspread](https://github.com/burnash/gspread) + Google Sheets API |
| Auth | Google OAuth 2.0 service account |

---

## Setup

### 1. Clone and install dependencies

```bash
git clone https://github.com/ginnoyong/bm4088-ica1-saq-marking-bot.git
cd bm4088-ica1-saq-marking-bot
pip install -r requirements.txt
```

### 2. Configure secrets

Create `.streamlit/secrets.toml`:

```toml
ANTHROPIC_API_KEY = "sk-ant-..."

MARKER_PASSWORDS = ["password1", "password2"]

GOOGLE_SHEET_ID = "your-google-sheet-id"
GOOGLE_SHEET_NAME = "ICA1"

[gcp_service_account]
type = "service_account"
project_id = "..."
private_key_id = "..."
private_key = "-----BEGIN RSA PRIVATE KEY-----\n..."
client_email = "...@....iam.gserviceaccount.com"
client_id = "..."
auth_uri = "https://accounts.google.com/o/oauth2/auth"
token_uri = "https://oauth2.googleapis.com/token"
```

`MARKER_PASSWORDS` is a list — each password identifies one marker in the log. Share one password per marker.

### 3. Google Sheets

- Create a Google Sheet and note its ID (from the URL).
- Add a sheet tab named `ICA1` (or whatever `GOOGLE_SHEET_NAME` is set to).
- Share the sheet with the service account email (Editor access).
- The app appends one row per submission: `Timestamp | Marker | Question | Image Included | Recommended Band`.

### 4. Run locally

```bash
streamlit run app.py
```

---

## Deploying to Streamlit Cloud

1. Push this repo to GitHub.
2. Create a new app at [share.streamlit.io](https://share.streamlit.io) pointing to `app.py`.
3. Paste the contents of `secrets.toml` into **Settings → Secrets**.

---

## Project Structure

```
app.py                          # Main Streamlit application
system_prompt.txt               # Full rubric and marking instructions for Claude
settings.json                   # App title, sidebar header, and question button config
requirements.txt                # Python dependencies
.streamlit/secrets.toml         # API keys and credentials (not committed)
```

---

## Security Notes

- `secrets.toml` and the GCP service account JSON are excluded from version control via `.gitignore`.
- The app blocks common prompt injection patterns before forwarding input to the API.
- Marker passwords are stored in Streamlit secrets, not in source code.
