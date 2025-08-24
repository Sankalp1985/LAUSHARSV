import streamlit as st
import json
import os
import re
from google import genai
from PIL import Image
import PyPDF2
import docx2txt

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

# --- AI moderation ---
def moderate_post(content):
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

# --- Ask AI (Gemini, limit 100 words) ---
def ask_ai(question):
    if client is None:
        return "Gemini client not initialized."
    try:
        prompt = f"{question}\n\nAnswer in maximum 100 words."
        response = client.models.generate_content(model="gemini-2.5-flash", contents=prompt)
        return response.text.strip()
    except Exception as e:
        return f"Error generating response: {e}"

# --- Generate 3 predefined questions from post content ---
def generate_predefined_questions(content):
    if client is None:
        return ["What is this post about?", "Explain the main idea.", "Give a summary."]
    try:
        prompt = f"Create 3 simple questions based on this text:\n{content}"
        response = client.models.generate_content(model="gemini-2.5-flash", contents=prompt)
        # Split lines, take first 3 non-empty
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
    if uploaded_file:
        media_info = {"name": uploaded_file.name, "type": uploaded_file.type}
        # Extract text from files if possible
        if uploaded_file.type == "application/pdf":
            pdf = PyPDF2.PdfReader(uploaded_file)
            text = ""
            for page in pdf.pages:
                text += page.extract_text() or ""
            post_content += "\n" + text
        elif uploaded_file.type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
            text = docx2txt.process(uploaded_file)
            post_content += "\n" + text
        elif uploaded_file.type == "text/plain":
            text = str(uploaded_file.read(), "utf-8")
            post_content += "\n" + text

    if post_content:
        if moderate_post(post_content):
            posts.insert(0, {"content": post_content, "media": media_info, "ai_reply": "", "predefined_questions": generate_predefined_questions(post_content)})
            save_posts()
            st.success("Post created successfully!")
        else:
            st.error("Post considered absurd by AI.")
    else:
        st.warning("Post cannot be empty!")

# --- Display feed ---
st.subheader("Feed")
for i, post in enumerate(posts):
    st.write(f"**Post {i+1}:** {post['content']}")
    # Display media if image
    if post.get("media"):
        if "image" in post["media"]["type"]:
            img = Image.open(post["media"]["name"])
            st.image(img)
        elif "video" in post["media"]["type"]:
            st.video(post["media"]["name"])
        else:
            st.write(f"Uploaded file: {post['media']['name']}")

    # Predefined questions
    st.write("**Predefined Questions:**")
    for idx, q in enumerate(post.get("predefined_questions", [])):
        if st.button(f"{q}", key=f"pre{i}{idx}"):
            answer = ask_ai(q)
            st.write(f"**AI Answer:** {answer}")
            post["ai_reply"] = answer
            save_posts()

    # Free form question
    user_q = st.text_input(f"Ask any question about this post {i+1}:", key=f"userq{i}")
    if st.button(f"Ask AI {i+1}", key=f"userb{i}"):
        answer = ask_ai(user_q)
        st.write(f"**AI Answer:** {answer}")
        post["ai_reply"] = answer
        save_posts()
