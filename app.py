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
from contextlib import contextmanager

load_dotenv()

# Page config
st.set_page_config(page_title="Email-Automation with Chat", page_icon="🤖")

st.markdown("""
<style>
    .sidebar-content {
        padding: 1rem;
    }
    .sidebar .sidebar-content {
        background-image: linear-gradient(#2e7bcf,#2e7bcf);
        color: white;
    }
    section[data-testid="stSidebar"] .stButton button {
        width: 100%;
        margin-bottom: 0.5rem;
        border-radius: 0.5rem;
        border: none;
        padding: 0.5rem;
        background-color: rgba(255, 255, 255, 0.1);
        color: white;
        transition: all 0.3s;
    }
    section[data-testid="stSidebar"] .stButton button:hover {
        background-color: rgba(255, 255, 255, 0.2);
    }
</style>
""", unsafe_allow_html=True)

# Initialize session state variables first
if 'user_id' not in st.session_state:
    st.session_state.user_id = str(uuid.uuid4())

if 'db' not in st.session_state:
    st.session_state.db = None

# Initialize database with user_id
db = DatabaseManager(user_id=st.session_state.user_id)
db.create_user_schema()
db.init_database()

# Database initialization
@st.cache_resource
def init_database():
    try:
        db = DatabaseManager(user_id=st.session_state.user_id)
        db.init_database()
        return db
    except Exception as e:
        st.error(f"Failed to initialize database: {e}")
        return None

# Initialize database on app start
if st.session_state.db is None:
    st.session_state.db = init_database()
    if st.session_state.db is None:
        st.error("Failed to initialize database. Please refresh the page.")
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

# System prompt
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

#menu logic
if 'active_menu' not in st.session_state:
    st.session_state.active_menu = "Email Automation"

def switch_menu(menu):
    st.session_state.active_menu = menu

with st.sidebar:
    # st.image("467400633_2369544196731392_5572063511124428547_n.jpg", width=50)  
    st.markdown("### Email Assistant")
    st.markdown("---")
    
    selected = option_menu(
        menu_title=None,
        options=["Email Automation", "Chat Interface"],
        icons=["envelope-fill", "chat-dots-fill", "arrow-repeat"], 
        default_index=0,
        styles={
            "container": {"padding": "0!important", "background-color": "transparent"},
            "icon": {"color": "white", "font-size": "20px"},
            "nav-link": {
                "color": "white",
                "font-size": "16px",
                "text-align": "left",
                "margin": "0px",
                "--hover-color": "rgba(255, 255, 255, 0.2)",
            },
            "nav-link-selected": {"background-color": "rgba(255, 255, 255, 0.2)"},
        }
    )
    
    st.markdown("---")
    
    # User info section
    with st.expander("ℹ️ Session Info"):
        st.write(f"User ID: {st.session_state.user_id[:8]}...")
        st.write(f"Active Page: {selected}")
    
    # Footer
    st.markdown("---")
    st.caption("_Placeholder_")
    
    # Update active menu
    st.session_state.active_menu = selected


# ----- EMAIL AUTOMATION -----
def email_automation_page():
    st.title("Email Automation")
    
    # Email configuration form
    with st.form(key="email_config_form"):
        with st.expander("Email Configurations", expanded=True):
            smtp_server = st.text_input("SMTP Server", value="smtp.gmail.com")
            port = st.number_input("Port", value=587)
            sender_email = st.text_input("Sender Email")
            sender_name = st.text_input("Your Name")
            sender_password = st.text_input("App Password", type="password")
            
        # Form submit button
        config_submitted = st.form_submit_button("Save Configuration")

    if config_submitted:
        if sender_email and sender_password and sender_name:
            st.success("Email configuration saved!")
            # Store configuration in session state
            st.session_state.email_config = {
                "smtp_server": smtp_server,
                "port": port,
                "sender_email": sender_email,
                "sender_name": sender_name,
                "sender_password": sender_password
            }
        else:
            st.warning("Please fill in all required fields")

    if "email_config" in st.session_state:
        uploaded_file = st.file_uploader("Upload CSV file", type=['csv'])
        
        if uploaded_file is not None:
            df = pd.read_csv(uploaded_file)
            st.dataframe(df)
            
            # Create form for email content
            with st.form(key="email_content_form"):
                email_context = st.text_area("Email Context")
                preview_email = st.form_submit_button("Preview Email")
                send_emails = st.form_submit_button("Send Emails")
                
                if preview_email:
                    if sender_email and sender_password and email_context and sender_name:
                        try:
                            email_automation = EmailAutomation(
                                api_key=f"{os.getenv('API_KEY')}",
                                **st.session_state.email_config
                            )
                            recipient_name = df.iloc[0]['recipient_name']
                            subject = df.iloc[0]['subject']
                            email_body = email_automation.generate_email(
                                subject, 
                                recipient_name, 
                                email_context
                            )
                            if email_body:
                                st.markdown("### Email Preview")
                                st.markdown(f"**To:** {recipient_name}")
                                st.markdown(f"**Subject:** {subject}")
                                st.markdown(email_body)
                        except Exception as e:
                            st.error(f"Error generating email preview: {e}")
                    else:
                        st.warning("Please fill in all required fields")

                if send_emails:
                    try:
                        with st.spinner('Initializing email automation...'):
                            email_automation = EmailAutomation(
                                api_key=f"{os.getenv('API_KEY')}",
                                **st.session_state.email_config
                            )
                            temp_file = "temp.csv"
                            with open(temp_file, "wb") as f:
                                f.write(uploaded_file.getbuffer())
                            
                            df = pd.read_csv(temp_file)
                            total_emails = len(df)
                            
                            progress_bar = st.progress(0)
                            status_text = st.empty()
                            
                            email_summary = []
                            
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
                                    db.save_email_activity(
                                        recipient_name,
                                        subject,
                                        email_context,
                                        email_body,
                                        email_body  # Assuming generated_text is the same as email_body
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
                            time.sleep(.5)
                            st.toast("Success! 🎉")
                            
                            if os.path.exists(temp_file):
                                os.remove(temp_file)
                            
                    except Exception as e:
                        st.error(f"Error sending emails: {e}")

if st.session_state.active_menu == "Email Automation":
    email_automation_page()

# ----- CHAT INTERFACE -----
elif st.session_state.active_menu == "Chat Interface":
    st.title("Chat Interface")
    
    for message in st.session_state.messages:
        if message["role"] != "system":
            with st.chat_message(message["role"]):
                st.markdown(message["content"])

    # Modify the chat input handling
    if prompt := st.chat_input("What would you like to ask?"):
        recent_emails = db.get_recent_email_activities(5)
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
            db.save_conversation("assistant", full_response)
                
            placeholder_text = ""
            for chunk in full_response.split():
                placeholder_text += chunk + " "
                message_placeholder.markdown(placeholder_text + "▌")
                time.sleep(0.05)
                
            message_placeholder.markdown(full_response)

        st.session_state.messages.append({"role": "assistant", "content": full_response})

st.sidebar.caption(f"Current Menu: :red[{st.session_state.active_menu}]")
