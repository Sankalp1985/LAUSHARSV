import streamlit as st
import speech_recognition as sr
import pyttsx3
import json
import os
from google import genai

# --- Persistent storage ---
POSTS_FILE = "posts.json"  # Cloud-friendly relative path
if os.path.exists(POSTS_FILE):
    with open(POSTS_FILE, "r") as f:
        posts = json.load(f)
else:
    posts = []

def save_posts():
    with open(POSTS_FILE, "w") as f:
        json.dump(posts, f, indent=4)

# --- Initialize Gemini client ---
api_key = st.secrets["GENAI_API_KEY"]  # Must set in Streamlit Secrets
client = genai.Client(api_key=api_key)

# --- AI moderation ---
def moderate_post(content):
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
        engine.setProperty('voice', voices[1].id)
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
            posts.insert(0, {"content": post_content})
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
            posts.insert(0, {"content": post_content})
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
        speak_text(answer)
