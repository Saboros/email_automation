# app.py
import streamlit as st
from AI import AI
from autmati import EmailAutomation
from database import DatabaseManager
import pandas as pd
import os
from typing import Dict, List
from streamlit_option_menu import option_menu
import time
from dotenv import load_dotenv
import uuid

load_dotenv()

# Page config
st.set_page_config(page_title="Email-Automation with Chat", page_icon="🤖")
st.title("Email-Automation with Chat")

# User session management
if 'user_id' not in st.session_state:
    st.session_state.user_id = str(uuid.uuid4())  # Generate unique user ID

# Initialize database with user_id
@st.cache_resource
def init_database():
    db = DatabaseManager(user_id=st.session_state.user_id)
    try:
        db.init_database()  # Initialize tables
        return db
    except Exception as e:
        st.error(f"Error initializing database: {e}")
        return None

if "db" not in st.session_state:
    st.session_state.db = init_database()
    if st.session_state.db is None:
        st.error("Failed to initialize database. Please refresh the page or contact support.")
        st.stop()


if "email_activities" not in st.session_state:
    st.session_state.email_activities = []

if "llm_context" not in st.session_state:
    st.session_state.llm_context = {
        "chat_history": [],
        "email_activities": [],
        "last_email_generation": None
    }

# Initialize AI model
@st.cache_resource
def load_ai_model():
    model_id = "meta-llama/Meta-Llama-3-70B-Instruct"  
    return AI(model_id)

if "ai_model" not in st.session_state:
    st.session_state.ai_model = load_ai_model()


#System prompt
if "messages" not in st.session_state:
    system_message = {
        "role": "system",
        "content": """You are an AI assistant with access to a local database of email records.
                     Please if not asked about emails, interact with the user as an assistant.
                     IMPORTANT: When asked about emails, ALWAYS check the database first via the [EMAIL CONTEXT] section.
                     If [EMAIL CONTEXT] is present, use ONLY that information to answer questions.
                     If [EMAIL CONTEXT] is empty, respond with "No email records found in database."
                     Format your responses based on actual database records, not generic suggestions.
                     Be direct and specific about what email data you find."""
    }
    st.session_state.messages = [system_message]

#Selection tab
selection = option_menu(
                        menu_title=None,
                        options=["Email Automation", "Chat Interface"],
                        orientation="horizontal",
                        default_index=0,
                        icons = ["envelope", "chat"])

#----- EMAIL AUTOMATION -----
if selection == "Email Automation":
    
    st.title("Email Automation")
    with st.expander("Email Configurations", expanded=True):
        
        smtp_server = st.text_input("SMTP Server", value="smtp.gmail.com")
        port = st.number_input("Port", value=587)
        sender_email = st.text_input("Sender Email")
        sender_name = st.text_input("Your Name")
        sender_password = st.text_input("App Password", type="password")
        
    uploaded_file = st.file_uploader("Upload CSV file", type=['csv'])
    
    if uploaded_file is not None:
        df = pd.read_csv(uploaded_file)
        st.dataframe(df)
        
        email_context = st.text_area("Email Context")
        
        if st.button("Send Emails"):
            if sender_email and sender_password and email_context and sender_name:
                try:
                    with st.spinner('Initializing email automation...'):
                        email_automation = EmailAutomation(
                            api_key= f"{os.getenv('API_KEY')}",
                            smtp_server=smtp_server,
                            port=port,
                            sender_email=sender_email,
                            sender_password=sender_password,
                            sender_name=sender_name  
                        )
                        
                        temp_file = "temp.csv"
                        with open(temp_file, "wb") as f:
                            f.write(uploaded_file.getbuffer())
                        
                        df = pd.read_csv(temp_file)
                        total_emails = len(df)
                        
                        progress_bar = st.progress(0)
                        status_text = st.empty()
                        
                        email_summary = []
                        
                        #Sending email progress bar 
                        for index, row in df.iterrows():
                            status_text.text(f"Sending email {index + 1} of {total_emails}...")
                            progress_bar.progress((index + 1) / total_emails)
                            
                            recipient_name = row['recipient_name']
                            recipient_email = row['email']
                            subject = row['subject']
                            
                            email_body = email_automation.generate_email(
                                subject, 
                                recipient_name, 
                                email_context
                            )
                            if email_body:
                                # Save email activity to database with user_id
                                st.session_state.db.save_email_activity(
                                    recipient_name,
                                    subject,
                                    email_context,
                                    email_body
                                )
                                
                                email_automation.send_email(recipient_email, subject, email_body)
                                email_summary.append({
                                    "recipient": recipient_name,
                                    "email": recipient_email,
                                    "subject": subject
                                })
                        
                        progress_bar.progress(1.0)
                        status_text.empty()
                        st.success("All emails sent successfully!")
                        
                        if os.path.exists(temp_file):
                            os.remove(temp_file)
                        
                except Exception as e:
                    st.error(f"Error sending emails: {e}")
            else:
                st.warning("Please fill in all email configuration fields")





#----- CHAT INTERFACE -----

if selection == "Chat Interface":
    st.title("Chat Interface")
    
    # Chat interface
    for message in st.session_state.messages:
        if message["role"] != "system":
            with st.chat_message(message["role"]):
                st.markdown(message["content"])

    
    # Modify the chat input handling
    if prompt := st.chat_input("What would you like to ask?"):
        recent_emails = st.session_state.db.get_recent_email_activities(5)
        system_context = st.session_state.messages[0]["content"]
            
            # Always include database status
        email_context = "\n[EMAIL CONTEXT]\n"
        if recent_emails:
            for email in recent_emails:
                email_context += f"""
                Recipient: {email[0]}
                Subject: {email[1]}
                Email Content: {email[2]}
                Generated Text: {email[3]}
                -------------------"""
        else:
            email_context += "DATABASE STATUS: No email records found\n"
        
        system_context += email_context
        st.session_state.messages[0]["content"] = system_context
        
        st.session_state.messages.append({
            "role": "user",
            "content": prompt
        })
            
        
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            message_placeholder = st.empty()
                # Pass full context to AI
            full_response = st.session_state.ai_model.generate_response(st.session_state.messages)
                
                # Save assistant's response
            st.session_state.db.save_conversation("assistant", full_response)
                
            
            placeholder_text = ""
            for chunk in full_response.split():
                placeholder_text += chunk + " "
                message_placeholder.markdown(placeholder_text + "▌")
                time.sleep(0.05)
                
            message_placeholder.markdown(full_response)

        st.session_state.messages.append({"role": "assistant", "content": full_response})
