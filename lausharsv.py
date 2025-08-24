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

# --- AI moderation ---
def moderate_post(content):
    try:
        prompt = f"Rate absurdity of this text from 0 (good) to 1 (absurd): {content}"
        response = client.models.generate_content(model="gemini-2.5-flash", contents=prompt)
        score = float(response.text.strip())
