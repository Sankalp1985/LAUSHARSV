import streamlit as st
import json
import os
import re
import io
import tempfile
import random
import string
from google import genai
from PIL import Image
import PyPDF2
import docx2txt
import urllib.parse

# --- Persistent storage ---
POSTS_FILE = "posts.json"
posts = []

if os.path.exists(POSTS_FILE):
    try:
        with open(POSTS_FILE, "r") as f:
            posts = json.load(f)
    except:
        posts = []

def save_posts():
    with open(POSTS_FILE, "w") as f:
        json.dump(posts, f, indent=4)

# --- Gemini client ---
try:
    api_key = st.secrets["GENAI_API_KEY"]
    client = genai.Client(api_key=api_key)
except Exception as e:
    st.error(f"Gemini client not initialized: {e}")
    client = None

# --- Moderation ---
CURSE_WORDS = ["fuck", "shit", "bitch", "asshole", "damn"]

def moderate_post(content):
    if any(word in content.lower() for word in CURSE_WORDS):
        return False
    if client is None:
        return True
    try:
        prompt = f"Rate absurdity of this text from 0 (good) to 1 (absurd): {content}"
        response = client.models.generate_content(model="gemini-2.5-flash", contents=prompt)
        text = response.text.strip()
        match = re.search(r"\b\d+(\.\d+)?\b", text)
        score = float(match.group()) if match else 0.5
        return score < 0.7
    except:
        return True

# --- Ask AI ---
def ask_ai(question):
    if client is None:
        return "Gemini client not initialized."
    try:
        prompt = f"{question}\n\nAnswer in maximum 100 words."
        response = client.models.generate_content(model="gemini-2.5-flash", contents=prompt)
        return response.text.strip()
    except Exception as e:
        return f"Error generating response: {e}"

# --- DOCX reader helper ---
def read_docx_bytes(file_bytes):
    with tempfile.NamedTemporaryFile(suffix=".docx", delete=True) as tmp:
        tmp.write(file_bytes)
        tmp.flush()
        text = docx2txt.process(tmp.name)
    return text

# --- Generate 6-digit alphanumeric ID ---
def generate_post_id():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))

# --- Share URLs using post_id ---
def get_share_urls(post_id):
    base_url = st.secrets.get("APP_URL", "https://lausharsv.streamlit.app")
    share_url = f"{base_url}?post_id={post_id}"
    encoded_url = urllib.parse.quote(share_url)
    whatsapp = f"https://wa.me/?text={encoded_url}"
    gmail = f"https://mail.google.com/mail/?view=cm&body={encoded_url}&su=Check%20this%20post"
    return whatsapp, gmail

# --- Read URL query parameter safely ---
highlight_post_id = None
if "post_id" in st.query_params:
    values = st.query_params["post_id"]
    if values:
        highlight_post_id = values[0]

# --- Streamlit App ---
st.title("LAUSHARS-V THE AI-Powered INDIAN Social App")

# --- Section 1: Text + Image/Video post ---
st.subheader("Post Text + Image/Video")
with st.form("post_form", clear_on_submit=True):
    post_text = st.text_area("Write your post here:")
    media_file = st.file_uploader("Upload Image/Video", type=["png", "jpg", "jpeg", "mp4"], key="media_form")
    submitted = st.form_submit_button("Post Text/Image/Video")

    if submitted:
        post_content = post_text
        media_info = None
        media_bytes = None
        if media_file:
            media_info = {"name": media_file.name, "type": media_file.type}
            media_bytes = media_file.read()
        if post_content or media_bytes:
            if moderate_post(post_content):
                posts.insert(0, {
                    "content": post_content,
                    "media": media_info,
                    "media_bytes": media_bytes.hex() if media_bytes else None,
                    "file_upload": None,
                    "comments": [],
                    "post_id": generate_post_id()
                })
                save_posts()
                st.success("Post created successfully!")
            else:
                st.error("Post considered inappropriate/absurd.")
        else:
            st.warning("Cannot post empty content!")

# --- Section 2: Upload file/image for AI ---
st.subheader("Upload File/Image for AI (Read on demand)")
with st.form("ai_file_form", clear_on_submit=False):
    ai_file = st.file_uploader(
        "Upload PDF, DOCX, TXT, or Image", 
        type=["pdf", "docx", "txt", "png", "jpg", "jpeg"], 
        key="ai_file_form"
    )
    post_id_for_ai = st.number_input(
        "Select post number to attach file for AI reading:",
        min_value=1, max_value=len(posts), step=1
    ) if posts else 1
    attach_submitted = st.form_submit_button("Attach File/Image for AI")

    if attach_submitted:
        if ai_file and posts:
            file_bytes = ai_file.read()
            posts[post_id_for_ai-1]["file_upload"] = {
                "name": ai_file.name,
                "type": ai_file.type,
                "bytes": file_bytes.hex()
            }
            save_posts()
            st.success("File/Image attached for AI. Content will be read when user asks a question.")

# --- Display Feed ---
st.subheader("Feed")
for i, post in enumerate(posts):
    post_div_id = post.get("post_id", f"post{i}")

    # Highlighted posts with border/background if matches URL
    highlight_style = ""
    if post_div_id == highlight_post_id:
        highlight_style = "padding:10px; border:3px solid #FFD700; border-radius:10px; background:#1a1a1a;"

    st.markdown(
        f"<div id='{post_div_id}' style='{highlight_style}'>**Post {i+1}: {post['content']}**</div>",
        unsafe_allow_html=True
    )

    # Display media
    if post.get("media") and post.get("media_bytes"):
        media_bytes = bytes.fromhex(post["media_bytes"])
        if "image" in post["media"]["type"]:
            st.image(Image.open(io.BytesIO(media_bytes)))
        elif "video" in post["media"]["type"]:
            st.video(media_bytes)

    # Share links
    whatsapp, gmail = get_share_urls(post["post_id"])
    st.markdown(f"[Share on WhatsApp]({whatsapp}) | [Share on Gmail]({gmail})")

    # User reply
    user_reply = st.text_input(f"Write a reply to Post {i+1}:", key=f"reply_post{i}")
    if st.button(f"Submit reply to Post {i+1}", key=f"reply_post_btn{i}"):
        if user_reply.strip():
            post["comments"].insert(0, {"question": user_reply, "answer": None, "replies": []})
            save_posts()
            st.success("Reply added!")

    # Ask AI about post + attached file/image
    user_q = st.text_input(f"Ask AI about this post {i+1}:", key=f"userq{i}")
    if st.button(f"Ask AI {i+1}", key=f"userb{i}"):
        if user_q.strip():
            full_question = user_q
            if post.get("file_upload"):
                file_bytes = bytes.fromhex(post["file_upload"]["bytes"])
                f_type = post["file_upload"]["type"]
                file_content = ""
                try:
                    if f_type == "application/pdf":
                        pdf = PyPDF2.PdfReader(io.BytesIO(file_bytes))
                        file_content = "".join([page.extract_text() or "" for page in pdf.pages])
                    elif f_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
                        file_content = read_docx_bytes(file_bytes)
                    elif f_type == "text/plain":
                        file_content = file_bytes.decode("utf-8")
                    elif "image" in f_type:
                        if client:
                            image_data = {"mime_type": f_type, "data": file_bytes}
                            vision_response = client.models.generate_content(
                                model="gemini-2.5-flash",
                                contents=[{"role": "user", "parts": [image_data, {"text": "Extract text or describe key content from this image."}]}]
                            )
                            file_content = vision_response.text.strip()
                        else:
                            file_content = "[AI client not initialized for image analysis]"
                except Exception as e:
                    file_content = f"[Failed to read file: {e}]"
                full_question += f"\n\nAttached file content:\n{file_content}"

            answer = ask_ai(full_question)
            post["comments"].insert(0, {"question": user_q, "answer": answer, "replies": []})
            save_posts()

    # Share attached file
    if post.get("file_upload"):
        whatsapp_file, gmail_file = get_share_urls(post["post_id"])
        st.markdown(f"[Share file on WhatsApp]({whatsapp_file}) | [Share file on Gmail]({gmail_file})")

    # Comments / AI Replies
    st.write("**Comments / AI Replies:**")
    for c_idx, c in enumerate(post.get("comments", [])):
        container = st.container()
        with container:
            if c.get("answer"):
                st.markdown(f"- **Q:** {c['question']}")
                st.markdown(f"  - **A:** {c['answer']}")
            else:
                st.markdown(f"- **Comment:** {c['question']}")

            reply_text = st.text_input(f"Reply to comment {c_idx+1} on post {i+1}:", key=f"reply{i}_{c_idx}")
            if st.button(f"Submit reply {c_idx+1}", key=f"replyb{i}_{c_idx}"):
                if reply_text.strip():
                    c["replies"].insert(0, reply_text)
                    save_posts()

            if c.get("replies"):
                for r in c["replies"]:
                    st.markdown(f"    - **Reply:** {r}")

# --- Auto-scroll and highlight post by post_id ---
if highlight_post_id:
    highlight_index = None
    for idx, post in enumerate(posts):
        if post.get("post_id") == highlight_post_id:
            highlight_index = idx
            break

    if highlight_index is not None:
        target_post_id = posts[highlight_index]["post_id"]
        st.markdown(
            f"""
            <script>
            setTimeout(() => {{
                const el = document.getElementById("{target_post_id}");
                if(el) {{
                    el.scrollIntoView({{behavior: "smooth", block: "center"}});
                    el.style.border = "3px solid #FFD700";
                    el.style.borderRadius = "10px";
                    el.style.background = "#1a1a1a";
                    el.style.padding = "10px";
                }}
            }}, 200);
            </script>
            """,
            unsafe_allow_html=True
        )
