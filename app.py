import json
import os
import re
import streamlit as st
import anthropic
import base64
from datetime import datetime, timezone, timedelta

_prompt_path = os.path.join(os.path.dirname(__file__), "system_prompt.txt")
with open(_prompt_path, "r", encoding="utf-8") as _f:
    SYSTEM_PROMPT = _f.read()

_settings_path = os.path.join(os.path.dirname(__file__), "settings.json")
with open(_settings_path, "r", encoding="utf-8") as _f:
    _SETTINGS = json.load(_f)

APP_TITLE = _SETTINGS["app_title"]
SIDEBAR_HEADER = _SETTINGS["sidebar_header"]
BUTTONS = _SETTINGS["buttons"]

INJECTION_PHRASES = [
    "ignore instructions",
    "ignore previous",
    "new task",
    "pretend you are",
    "you are now",
    "disregard",
    "override",
    "jailbreak",
    "act as",
    "forget your instructions",
]

NEW_STUDENT_MSG = "Ready for next student. Please select a question and input the student's response."


def reset_for_new_student(question="Not specified"):
    st.session_state.messages = [{"role": "assistant", "content": NEW_STUDENT_MSG}]
    st.session_state.selected_question = question
    st.session_state.uploader_key = st.session_state.get("uploader_key", 0) + 1
    st.session_state.input_key = st.session_state.get("input_key", 0) + 1


def contains_injection(text: str) -> bool:
    lower = text.lower()
    return any(phrase in lower for phrase in INJECTION_PHRASES)


def get_media_type(filename: str) -> str:
    ext = filename.rsplit(".", 1)[-1].lower()
    return "image/png" if ext == "png" else "image/jpeg"


def render_message_content(content):
    if isinstance(content, str):
        st.markdown(content)
    elif isinstance(content, list):
        for block in content:
            if block.get("type") == "text":
                st.markdown(block["text"])
            elif block.get("type") == "image":
                img_bytes = base64.b64decode(block["source"]["data"])
                st.image(img_bytes)


def call_api(messages: list) -> tuple:
    client = anthropic.Anthropic(api_key=st.secrets["ANTHROPIC_API_KEY"])
    api_messages = [{"role": m["role"], "content": m["content"]} for m in messages]
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        temperature=0,
        system=[{
            "type": "text",
            "text": SYSTEM_PROMPT,
            "cache_control": {"type": "ephemeral"},
        }],
        messages=api_messages,
    )
    return response.content[0].text, response.usage


def render_usage_metrics(usage) -> None:
    read  = getattr(usage, "cache_read_input_tokens",    0) or 0
    write = getattr(usage, "cache_creation_input_tokens", 0) or 0
    inp   = getattr(usage, "input_tokens",               0) or 0
    out   = getattr(usage, "output_tokens",              0) or 0
    total = read + write + inp + out
    cost_usd = (inp * 3.00 + write * 3.75 + read * 0.30 + out * 15.00) / 1_000_000
    cost_sgd = cost_usd * 1.32
    hit = read > 0
    cache_span = (
        f'<span style="color:#2d8a4e">Hit</span>'
        if hit else
        f'<span style="color:#c0392b">Miss</span>'
    )
    st.markdown(
        f'<p style="font-size:0.75rem;color:#888;margin:2px 0 6px 0">'
        f'Cache: {cache_span} &nbsp;|&nbsp; '
        f'Read: {read:,} &nbsp;|&nbsp; '
        f'Write: {write:,} &nbsp;|&nbsp; '
        f'Total tokens: {total:,} &nbsp;|&nbsp; '
        f'Est. cost: SGD&nbsp;{cost_sgd:.4f}'
        f'</p>',
        unsafe_allow_html=True,
    )


def log_to_sheets(marker: str, question: str, has_image: bool, response_text: str):
    try:
        import gspread
        from google.oauth2.service_account import Credentials

        band_match = re.search(
            r'\b(?:recommended\s+)?band\b[^A-Za-z]{0,15}([ABCDF])\b',
            response_text,
            re.IGNORECASE,
        )
        band = band_match.group(1).upper() if band_match else "Clarification requested"

        sgt = timezone(timedelta(hours=8))
        timestamp = datetime.now(sgt).strftime("%Y-%m-%d %H:%M:%S")

        creds = Credentials.from_service_account_info(
            st.secrets["gcp_service_account"],
            scopes=[
                "https://www.googleapis.com/auth/spreadsheets",
                "https://www.googleapis.com/auth/drive",
            ],
        )
        client = gspread.authorize(creds)
        worksheet = client.open_by_key(st.secrets["GOOGLE_SHEET_ID"]).worksheet(
            st.secrets["GOOGLE_SHEET_NAME"]
        )
        worksheet.append_row([timestamp, marker, question, "Yes" if has_image else "No", band])
    except Exception:
        pass


def show_password_gate():
    st.title(APP_TITLE)
    st.markdown("Enter the marker password to access the tool.")
    pw = st.text_input("Password", type="password", key="pw_input")
    if st.button("Login"):
        if pw in st.secrets["MARKER_PASSWORDS"]:
            st.session_state.authenticated = True
            st.session_state.current_marker = pw
            st.rerun()
        else:
            st.error("Incorrect password. Please try again.")


def main():
    st.set_page_config(
        page_title=APP_TITLE,
        page_icon="📊",
        layout="wide",
    )

    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False

    if not st.session_state.authenticated:
        show_password_gate()
        return

    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "selected_question" not in st.session_state:
        st.session_state.selected_question = "Not specified"
    if "uploader_key" not in st.session_state:
        st.session_state.uploader_key = 0
    if "input_key" not in st.session_state:
        st.session_state.input_key = 0

    # Sidebar
    with st.sidebar:
        st.header(SIDEBAR_HEADER)
        st.caption("Click a question to start a new submission")
        st.divider()

        for btn in BUTTONS:
            if st.button(
                f"{btn['label']}  ({btn['marks']} marks)",
                key=f"sidebar_{btn['id']}",
                use_container_width=True,
            ):
                reset_for_new_student(btn["id"])
                st.rerun()

        st.divider()
        if st.button("New Student Submission", use_container_width=True):
            reset_for_new_student()
            st.rerun()

    # Main area
    st.title(APP_TITLE)

    # Let Ctrl+C / Cmd+C fall through to the browser's native copy when text is highlighted
    st.markdown("""
        <script>
        document.addEventListener('keydown', function(e) {
            if ((e.ctrlKey || e.metaKey) && (e.key === 'c' || e.key === 'C')) {
                e.stopPropagation();
            }
        }, true);
        </script>
    """, unsafe_allow_html=True)

    # Chat history
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            if msg["role"] == "assistant" and msg.get("usage") is not None:
                render_usage_metrics(msg["usage"])
            render_message_content(msg["content"])

    # Input area
    selected_q = st.session_state.selected_question
    question_selected = selected_q != "Not specified"

    col_text, col_side = st.columns([3, 1])
    with col_text:
        text_input = st.text_area(
            "Student response",
            placeholder="Describe or Copy-paste the student's response to mark...",
            key=f"text_input_{st.session_state.input_key}",
            height=160,
            label_visibility="collapsed",
        )
    with col_side:
        uploaded_file = st.file_uploader(
            "Student screenshot (optional)",
            type=["jpg", "jpeg", "png"],
            key=f"img_upload_{st.session_state.uploader_key}",
        )
        submit_clicked = st.button("Submit", key="submit_btn", use_container_width=True)

    st.iframe("""
        <script>
        (function() {
            var p = window.parent;

            // Ctrl+Enter shortcut
            if (p._ctrlEnterHandler) {
                p.document.removeEventListener('keydown', p._ctrlEnterHandler);
            }
            p._ctrlEnterHandler = function(e) {
                if (e.ctrlKey && e.key === 'Enter') {
                    var active = p.document.activeElement;
                    if (active && active.tagName === 'TEXTAREA') {
                        var btns = p.document.querySelectorAll('button');
                        for (var i = 0; i < btns.length; i++) {
                            if (btns[i].textContent.trim() === 'Submit') {
                                btns[i].click();
                                break;
                            }
                        }
                    }
                }
            };
            p.document.addEventListener('keydown', p._ctrlEnterHandler);

            // Sidebar button colours — cycles through palette by Q-number; default for non-Q buttons
            var Q_PALETTE = [
                {bg: '#3a7d5e', border: '#2d6349', hover: '#45916d'},
                {bg: '#2c6490', border: '#224e70', hover: '#3475a5'},
                {bg: '#7a5500', border: '#5c3f00', hover: '#8f6400'},
                {bg: '#5e3d80', border: '#4a2d65', hover: '#6e4894'},
            ];
            var Q_DEFAULT = {bg: '#546e7a', border: '#3d5560', hover: '#617f8c'};

            function colorButtons() {
                p.document.querySelectorAll('[data-testid="stSidebar"] button').forEach(function(btn) {
                    var m = btn.textContent.trim().match(/^Q(\d+)/);
                    var s = m ? Q_PALETTE[(parseInt(m[1], 10) - 1) % Q_PALETTE.length] : Q_DEFAULT;
                    btn.style.backgroundColor = s.bg;
                    btn.style.borderColor = s.border;
                    btn.style.color = '#fff';
                    btn.onmouseover = function() { this.style.backgroundColor = s.hover; };
                    btn.onmouseout = function() { this.style.backgroundColor = s.bg; };
                });
            }

            colorButtons();
            if (p._btnColorObserver) p._btnColorObserver.disconnect();
            p._btnColorObserver = new p.MutationObserver(colorButtons);
            p._btnColorObserver.observe(p.document.body, {childList: true, subtree: true});
        })();
        </script>
    """, height=1)

    text = text_input or ""
    has_image = uploaded_file is not None
    has_content = bool(text) or has_image
    should_submit = submit_clicked and question_selected and has_content

    if submit_clicked and not question_selected:
        st.warning("Please select a question before submitting.")
    elif submit_clicked and not has_content:
        st.warning("Please provide a student response or upload a screenshot.")

    if should_submit:
        # Injection guard
        if contains_injection(text):
            rejection = (
                "I can only assist with BM4088 Mock SAQ marking. "
                "Please describe the student response you would like assessed."
            )
            with st.chat_message("assistant"):
                st.markdown(rejection)
            st.session_state.messages.append(
                {"role": "assistant", "content": rejection}
            )
            return

        # Build content blocks
        content_blocks = []

        if has_image:
            img_bytes = uploaded_file.read()
            img_b64 = base64.b64encode(img_bytes).decode()
            content_blocks.append(
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": get_media_type(uploaded_file.name),
                        "data": img_b64,
                    },
                }
            )

        full_text = f"[Question: {selected_q}] {text}".strip()
        if full_text:
            content_blocks.append({"type": "text", "text": full_text})

        user_content = (
            content_blocks[0]["text"]
            if len(content_blocks) == 1 and content_blocks[0].get("type") == "text"
            else content_blocks
        )

        # Display user message inline
        with st.chat_message("user"):
            if has_image:
                st.image(img_bytes)
            if full_text:
                st.markdown(full_text)

        st.session_state.messages.append({"role": "user", "content": user_content})

        # API call and display response
        with st.chat_message("assistant"):
            with st.spinner("Marking..."):
                try:
                    response_text, usage = call_api(st.session_state.messages)
                    log_to_sheets(
                        st.session_state.get("current_marker", "unknown"),
                        selected_q,
                        has_image,
                        response_text,
                    )
                except Exception as e:
                    response_text = f"Error contacting the API: {e}"
                    usage = None
            if usage is not None:
                render_usage_metrics(usage)
            st.markdown(response_text)

        st.session_state.messages.append(
            {"role": "assistant", "content": response_text, "usage": usage}
        )

        # Reset input widgets for next submission
        st.session_state.uploader_key += 1
        st.session_state.input_key += 1
        st.rerun()


if __name__ == "__main__":
    main()
