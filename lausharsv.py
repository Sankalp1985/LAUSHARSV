import streamlit as st
import json
import os
import re
from google import genai
from PIL import Image
import PyPDF2
import docx2txt
import io

# --- Persistent storage ---
POSTS_FILE = "posts.json"
posts = []

if os.path.exists(POSTS_FILE):
    try:
        with open(POSTS_FILE, "r") as f:
            posts = json.load(f)
    except (json.JSONDecodeError, ValueError):
        posts = []

def save_posts():
    try:
        with open(POSTS_FILE, "w") as f:
            json.dump(posts, f, indent=4)
    except Exception as e:
        st.error(f"Failed to save posts: {e}")

# --- Initialize Gemini client ---
try:
    api_key = st.secrets["GENAI_API_KEY"]
    client = genai.Client(api_key=api_key)
except Exception as e:
    st.error(f"Failed to initialize Gemini client: {e}")
    client = None

# --- Moderation: absurdity + curse words ---
CURSE_WORDS = ["fuck", "shit", "bitch", "asshole", "damn"]  # extend as needed
def moderate_post(content):
    # Basic curse word filter
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

# --- Ask AI (max 100 words) ---
def ask_ai(question):
    if client is None:
        return "Gemini client not initialized."
    try:
        prompt = f"{question}\n\nAnswer in maximum 100 words."
        response = client.models.generate_content(model="gemini-2.5-flash", contents=prompt)
        return response.text.strip()
    except Exception as e:
        return f"Error generating response: {e}"

# --- Generate 3 predefined questions ---
def generate_predefined_questions(content):
    if client is None:
        return ["What is this post about?", "Explain the main idea.", "Give a summary."]
    try:
        prompt = f"Create 3 simple questions based on this text:\n{content}"
        response = client.models.generate_content(model="gemini-2.5-flash", contents=prompt)
        questions = [q.strip() for q in response.text.strip().split("\n") if q.strip()][:3]
        if len(questions) < 3:
            questions += ["Explain the main idea.", "Give a summary.", "What is this post about?"][:3-len(questions)]
        return questions
    except:
        return ["Explain the main idea.", "Give a summary.", "What is this post about?"]

# --- Streamlit UI ---
st.title("AI-Powered Social App with Media & Smart Q&A")

# --- Create post ---
st.subheader("Create a Post")
post_text = st.text_area("Write your post here:")
uploaded_file = st.file_uploader("Upload media (Image, Video, PDF, DOCX, TXT)", type=["png","jpg","jpeg","mp4","pdf","docx","txt"])

if st.button("Post"):
    post_content = post_text
    media_info = None
    media_bytes = None
    if uploaded_file:
        media_info = {"name": uploaded_file.name, "type": uploaded_file.type}
        media_bytes = uploaded_file.read()
        uploaded_file.seek(0)
        if uploaded_file.type == "application/pdf":
            pdf = PyPDF2.PdfReader(io.BytesIO(media_bytes))
            text = ""
            for page in pdf.pages:
                text += page.extract_text() or ""
            post_content += "\n" + text
        elif uploaded_file.type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
            text = docx2txt.process(io.BytesIO(media_bytes))
            post_content += "\n" + text
        elif uploaded_file.type == "text/plain":
            text = media_bytes.decode("utf-8")
            post_content += "\n" + text

    if post_content:
        if moderate_post(post_content):
            posts.insert(0, {
                "content": post_content,
                "media": media_info,
                "media_bytes": media_bytes.hex() if media_bytes else None,
                "comments": [],
                "predefined_questions": generate_predefined_questions(post_content)
            })
            save_posts()
            st.success("Post created successfully!")
        else:
            st.error("Post considered inappropriate/absurd.")
    else:
        st.warning("Post cannot be empty!")

# --- Display feed ---
st.subheader("Feed")
for i, post in enumerate(posts):
    st.write(f"**Post {i+1}:** {post['content']}")
    
    # Display media
    if post.get("media") and post.get("media_bytes"):
        media_bytes = bytes.fromhex(post["media_bytes"])
        if "image" in post["media"]["type"]:
            st.image(Image.open(io.BytesIO(media_bytes)))
        elif "video" in post["media"]["type"]:
            st.video(media_bytes)
        else:
            st.write(f"Uploaded file: {post['media']['name']}")

    # Predefined questions
    st.write("**Predefined Questions:**")
    for idx, q in enumerate(post.get("predefined_questions", [])):
        if st.button(f"{q}", key=f"pre{i}{idx}"):
            answer = ask_ai(q)
            post["comments"].append({"question": q, "answer": answer})
            save_posts()

    # Free form question
    user_q = st.text_input(f"Ask any question about this post {i+1}:", key=f"userq{i}")
    if st.button(f"Ask AI {i+1}", key=f"userb{i}"):
        if user_q.strip():
            answer = ask_ai(user_q)
            post["comments"].append({"question": user_q, "answer": answer})
            save_posts()

    # Display all comments for this post
    if post.get("comments"):
        st.write("**Comments / AI Replies:**")
        for c in post["comments"]:
            st.markdown(f"- **Q:** {c['question']}")
            st.markdown(f"  - **A:** {c['answer']}")
