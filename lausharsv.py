import streamlit as st
import json
import os
import re
import io
from google import genai
from PIL import Image
import PyPDF2
import docx2txt
import pytesseract
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
CURSE_WORDS = ["fuck","shit","bitch","asshole","damn"]
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

# --- Predefined questions ---
def generate_predefined_questions(content):
    if client is None:
        return ["What is this post about?", "Explain the main idea.", "Give a summary."]
    try:
        prompt = f"Create 3 simple questions based on this text:\n{content}"
        response = client.models.generate_content(model="gemini-2.5-flash", contents=prompt)
        questions = [q.strip() for q in response.text.strip().split("\n") if q.strip()][:3]
        if len(questions) < 3:
            questions += ["Explain the main idea.","Give a summary.","What is this post about?"][:3-len(questions)]
        return questions
    except:
        return ["Explain the main idea.","Give a summary.","What is this post about?"]

# --- Share URLs ---
def get_share_urls(post_content):
    encoded_text = urllib.parse.quote(post_content)
    whatsapp = f"https://wa.me/?text={encoded_text}"
    gmail = f"https://mail.google.com/mail/?view=cm&body={encoded_text}&su=Check%20this%20post"
    return whatsapp, gmail

st.title("AI-Powered Social App with Nested Replies")

# --- Section 1: Text + Image/Video post ---
st.subheader("Post Text + Image/Video")
post_text = st.text_area("Write your post here:")
media_file = st.file_uploader("Upload Image/Video", type=["png","jpg","jpeg","mp4"], key="media")

if st.button("Post Text/Image/Video"):
    post_content = post_text
    media_info = None
    media_bytes = None
    if media_file:
        media_info = {"name": media_file.name, "type": media_file.type}
        media_bytes = media_file.read()
    if post_content or media_bytes:
        if moderate_post(post_content):
            posts.insert(0,{
                "content": post_content,
                "media": media_info,
                "media_bytes": media_bytes.hex() if media_bytes else None,
                "file_upload": None,
                "comments": [],
                "predefined_questions": generate_predefined_questions(post_content)
            })
            save_posts()
            st.success("Post created successfully!")
        else:
            st.error("Post considered inappropriate/absurd.")
    else:
        st.warning("Cannot post empty content!")

# --- Section 2: File/Image upload for AI ---
st.subheader("Upload File/Image for AI (Read on demand)")
ai_file = st.file_uploader("Upload PDF, DOCX, TXT, or Image", type=["pdf","docx","txt","png","jpg","jpeg"], key="ai_file")
post_id_for_ai = st.number_input("Select post number to attach file for AI reading:", min_value=1, max_value=len(posts), step=1) if posts else 1

if st.button("Attach File/Image for AI"):
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
    st.write(f"**Post {i+1}:** {post['content']}")

    # Display media immediately
    if post.get("media") and post.get("media_bytes"):
        media_bytes = bytes.fromhex(post["media_bytes"])
        if "image" in post["media"]["type"]:
            st.image(Image.open(io.BytesIO(media_bytes)))
        elif "video" in post["media"]["type"]:
            st.video(media_bytes)

    # Share links
    whatsapp, gmail = get_share_urls(post["content"])
    st.markdown(f"[Share on WhatsApp]({whatsapp}) | [Share on Gmail]({gmail})")

    # Predefined questions
    st.write("**Predefined Questions:**")
    for idx, q in enumerate(post.get("predefined_questions", [])):
        if st.button(f"{q}", key=f"pre{i}{idx}"):
            answer = ask_ai(q)
            post["comments"].append({"question": q, "answer": answer, "replies": []})
            save_posts()

    # Free form AI question (reads attached files)
    user_q = st.text_input(f"Ask AI about this post {i+1}:", key=f"userq{i}")
    if st.button(f"Ask AI {i+1}", key=f"userb{i}"):
        if user_q.strip():
            full_question = user_q
            if post.get("file_upload"):
                file_bytes = bytes.fromhex(post["file_upload"]["bytes"])
                f_type = post["file_upload"]["type"]
                if f_type == "application/pdf":
                    pdf = PyPDF2.PdfReader(io.BytesIO(file_bytes))
                    text = "".join([page.extract_text() or "" for page in pdf.pages])
                    full_question += "\n\nAttached file content:\n" + text
                elif f_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
                    text = docx2txt.process(io.BytesIO(file_bytes))
                    full_question += "\n\nAttached file content:\n" + text
                elif f_type == "text/plain":
                    text = file_bytes.decode("utf-8")
                    full_question += "\n\nAttached file content:\n" + text
                elif "image" in f_type:
                    image = Image.open(io.BytesIO(file_bytes))
                    text = pytesseract.image_to_string(image)
                    full_question += "\n\nAttached image text:\n" + text
            answer = ask_ai(full_question)
            post["comments"].append({"question": user_q, "answer": answer, "replies": []})
            save_posts()

    # Comments section with nested replies
    st.write("**Comments / AI Replies:**")
    for c_idx, c in enumerate(post.get("comments", [])):
        container = st.container()
        with container:
            if c.get("answer"):
                st.markdown(f"- **Q:** {c['question']}")
                st.markdown(f"  - **A:** {c['answer']}")
            else:
                st.markdown(f"- **Comment:** {c['question']}")
            
            # Nested reply input
            reply_text = st.text_input(f"Reply to comment {c_idx+1} on post {i+1}:", key=f"reply{i}_{c_idx}")
            if st.button(f"Submit reply {c_idx+1}", key=f"replyb{i}_{c_idx}"):
                if reply_text.strip():
                    c["replies"].append(reply_text)
                    save_posts()
            
            # Display nested replies
            if c.get("replies"):
                for r in c["replies"]:
                    st.markdown(f"    - **Reply:** {r}")
