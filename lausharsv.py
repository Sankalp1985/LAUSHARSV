import streamlit as st
import speech_recognition as sr
import pyttsx3
import json
import os
from google import genai

# --- Persistent storage ---
POSTS_FILE = "posts.json"  # Cloud-friendly relative path
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
    api_key = st.secrets["GENAI_API_KEY"]  # Set in Streamlit Secrets
    client = genai.Client(api_key=api_key)
except Exception as e:
    st.error(f"Failed to initialize Gemini client: {e}")
    client = None

# --- AI moderation ---
def moderate_post(content):
    if client is None:
        st.warning("Gemini client not initialized. Post skipped moderation.")
        return True
    try:
        prompt = f"Rate absurdity of this text from 0 (good) to 1 (absurd): {content}"
        response = client.models.generate_content(model="gemini-2.5-flash", contents=prompt)
        score = float(response.text.strip())
        return score < 0.7
    except Exception as e:
        st.error(f"Moderation failed: {e}")
        return False

# --- Ask AI (Gemini) ---
def ask_ai(question):
    if client is None:
        return "Gemini client not initialized."
    try:
        response = client.models.generate_content(model="gemini-2.5-flash", contents=question)
        return response.text.strip()
    except Exception as e:
        st.error(f"AI query failed: {e}")
        return "Error generating response."

# --- Speak text ---
def speak_text(text):
    try:
        engine = pyttsx3.init()
        engine.setProperty('rate', 150)
        engine.setProperty('volume', 1)
        voices = engine.getProperty('voices')
        engine.setProperty('voice', voices[1].id)  # Female voice
        engine.say(text)
        engine.runAndWait()
    except Exception as e:
        st.warning(f"Voice output failed: {e}")

# --- Streamlit UI ---
st.title("AI-Powered Social App")

# --- Voice Posting ---
if st.button("Record Voice Post"):
    recognizer = sr.Recognizer()
    with sr.Microphone() as source:
        st.write("Listening... Speak now!")
        recognizer.adjust_for_ambient_noise(source)
        audio = recognizer.listen(source)
    try:
        post_content = recognizer.recognize_google(audio)
        st.write(f"You said: {post_content}")
        if moderate_post(post_content):
            posts.insert(0, {"content": post_content, "ai_reply": ""})
            save_posts()
            st.success("Voice post created successfully!")
        else:
            st.error("Post considered absurd by AI.")
    except Exception as e:
        st.error(f"Error recognizing voice: {e}")

# --- Text Posting ---
post_content = st.text_area("Or write your post here:")
if st.button("Post Text"):
    if post_content:
        if moderate_post(post_content):
            posts.insert(0, {"content": post_content, "ai_reply": ""})
            save_posts()
            st.success("Text post created successfully!")
        else:
            st.error("Post considered absurd by AI.")
    else:
        st.warning("Post cannot be empty!")

# --- Display Posts / Ask AI ---
st.subheader("Feed")
for i, post in enumerate(posts):
    st.write(f"Post {i+1}: {post['content']}")

    # Ask AI via text
    question = st.text_input(f"Ask AI about this post {i+1}:", key=f"q{i}")
    if st.button(f"Ask AI {i+1}", key=f"b{i}"):
        answer = ask_ai(question)
        st.write(f"AI Answer: {answer}")
        posts[i]["ai_reply"] = answer  # Save reply in posts
        save_posts()
        speak_text(answer)

    # Play last AI reply
    if post.get("ai_reply"):
        if st.button(f"Play AI Reply {i+1}", key=f"p{i}"):
            speak_text(post["ai_reply"])
