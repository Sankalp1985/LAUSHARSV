import streamlit as st
import json
import os
import re
from google import genai
from gtts import gTTS
from io import BytesIO
from PIL import Image
import docx2txt
import PyPDF2
import pytesseract

# --- Persistent storage ---
POSTS_FILE = "posts.json"
posts = []

# Safely load posts
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
        st.warning("Gemini client not initialized. Skipping moderation.")
        return True
    try:
        prompt = f"Rate absurdity of this text from 0 (good) to 1 (absurd): {content}"
        response = client.models.generate_content(model="gemini-2.5-flash", contents=prompt)
        text = response.text.strip()
        match = re.search(r"\b\d+(\.\d+)?\b", text)
        score = float(match.group()) if match else 0.5
        return score < 0.7
    except Exception as e:
        st.error(f"Moderation failed: {e}")
        return False

# --- Ask AI ---
def ask_ai(question):
    if client is None:
        return "Gemini client not initialized."
    try:
        response = client.models.generate_content(model="gemini-2.5-flash", contents=question)
        return response.text.strip()
    except Exception as e:
        st.error(f"AI query failed: {e}")
        return "Error generating response."

# --- Convert text to audio ---
def text_to_audio(text):
    try:
        tts = gTTS(text=text, lang='en')
        audio_file = BytesIO()
        tts.write_to_fp(audio_file)
        audio_file.seek(0)
        return audio_file
    except Exception as e:
        st.warning(f"Text-to-speech failed: {e}")
        return None

# --- Extract text from uploaded file ---
def extract_text_from_file(file):
    try:
        if file.type == "application/pdf":
            reader = PyPDF2.PdfReader(file)
            text = "".join([page.extract_text() + "\n" for page in reader.pages])
            return text
        elif file.type == "text/plain":
            return str(file.read(), encoding='utf-8')
        elif file.type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
            return docx2txt.process(file)
        elif file.type.startswith("image/"):
            image = Image.open(file)
            text = pytesseract.image_to_string(image)
            return text
        else:
            return ""
    except Exception as e:
        st.error(f"Failed to extract text: {e}")
        return ""

# --- Summarize content using AI ---
def summarize_content(content):
    if client is None or not content.strip():
        return ""
    try:
        prompt = f"Summarize this content in 2-3 sentences:\n{content}"
        response = ask_ai(prompt)
        return response
    except:
        return ""

# --- Predefined questions for AI about a post ---
PREDEFINED_QUESTIONS = [
    "Explain this post in simple words.",
    "What is the main idea of this post?",
    "Give 3 important takeaways from this post.",
    "Is there any advice or recommendation in this post?",
    "How can I apply this information in real life?"
]

# --- Streamlit UI ---
st.title("🌐 AI-Powered Social App + Predefined Questions")
st.markdown("Create posts with text, photos, videos, or files, and interact with AI!")

# --- Create a new post ---
st.subheader("📝 Create a Post")
post_text = st.text_area("Write something...")
post_image = st.file_uploader("Upload an image", type=["png", "jpg", "jpeg"], key="img_upload")
post_video = st.file_uploader("Upload a video", type=["mp4", "mov", "avi"], key="vid_upload")

if st.button("Post"):
    if post_text.strip() or post_image or post_video:
        content_for_moderation = post_text if post_text.strip() else "Media post"
        if moderate_post(content_for_moderation):
            post_data = {
                "content": post_text,
                "image": None,
                "video": None,
                "ai_reply": "",
                "summary": "",
                "comments": []
            }
            if post_image:
                post_data["image"] = post_image.getvalue()
                post_data["image_name"] = post_image.name
                post_data["summary"] = summarize_content(post_text or "Image post")
            if post_video:
                post_data["video"] = post_video.getvalue()
                post_data["video_name"] = post_video.name
                post_data["summary"] = summarize_content(post_text or "Video post")
            posts.insert(0, post_data)
            save_posts()
            st.success("Post created successfully!")
        else:
            st.error("Post considered absurd by AI.")
    else:
        st.warning("Please enter text or upload media.")

# --- Display feed ---
st.subheader("📢 Feed")
for i, post in enumerate(posts):
    st.markdown(f"**Post {i+1}:** {post['content']}")
    
    if post.get("summary"):
        st.markdown(f"📝 **Summary:** {post['summary']}")
    
    if post.get("image"):
        st.image(post["image"], caption=post.get("image_name", "Image"), use_column_width=True)
    
    if post.get("video"):
        st.video(post["video"], format="video/mp4", start_time=0)
    
    # Display last AI reply
    if post.get("ai_reply"):
        st.markdown(f"💬 **AI Reply:** {post['ai_reply']}")
        audio_file = text_to_audio(post["ai_reply"])
        if audio_file:
            st.audio(audio_file, format="audio/mp3")
    
    # Inline comments
    comment = st.text_input(f"Add comment to post {i+1}:", key=f"c{i}")
    if st.button(f"Submit Comment {i+1}", key=f"cm{i}"):
        if comment.strip():
            post["comments"].append(comment)
            save_posts()
            st.success("Comment added!")
    
    # Display comments
    for idx, c in enumerate(post.get("comments", [])):
        st.markdown(f"🗨️ Comment {idx+1}: {c}")
    
    # --- Predefined questions ---
    st.markdown("### Ask AI (Predefined Questions)")
    selected_question = st.selectbox(f"Select a question for post {i+1}:", PREDEFINED_QUESTIONS, key=f"pq{i}")
    if st.button(f"Ask AI (Predefined) {i+1}", key=f"pq_btn{i}"):
        answer = ask_ai(selected_question)
        posts[i]["ai_reply"] = answer
        save_posts()
        st.markdown(f"💬 **AI Answer:** {answer}")
        audio_file = text_to_audio(answer)
        if audio_file:
            st.audio(audio_file, format="audio/mp3")
