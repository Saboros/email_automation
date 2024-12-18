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
import plotly.express as px
import plotly.graph_objects as go
import numpy as np
from datetime import datetime, timedelta




load_dotenv()





# Page config
st.set_page_config(page_title="Email-Automation with Chat", page_icon="🤖")

#Load CSS design for UI
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

if 'persistent_user_id' not in st.session_state:
    # Try to load from disk or create new
    try:
        with open('.user_id', 'r') as f:
            st.session_state.persistent_user_id = f.read().strip()
    except FileNotFoundError:
        st.session_state.persistent_user_id = str(uuid.uuid4())
        with open('.user_id', 'w') as f:
            f.write(st.session_state.persistent_user_id)

# Use persistent ID everywhere
st.session_state.user_id = st.session_state.persistent_user_id

# Store the user_id in a persistent way
@st.cache_resource
def get_database_manager(user_id):
    db = DatabaseManager(user_id=user_id)
    db.create_user_schema()
    db.init_database()
    return db

# Initialize database with consistent user_id
if 'db' not in st.session_state:
    st.session_state.db = get_database_manager(st.session_state.user_id)

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
                     Instead of saying [EMAIL CONTEXT], provide the actual email data.
                     Format your responses based on actual database records, not generic suggestions.
                     Be direct and specific about what email data you find."""
    }
    st.session_state.messages = [system_message]

#menu logic
if 'active_menu' not in st.session_state:
    st.session_state.active_menu = "Email Automation"

def switch_menu(menu):
    st.session_state.active_menu = menu

#Sidebar with CSS design for UI
with st.sidebar:
    # st.image("467400633_2369544196731392_5572063511124428547_n.jpg", width=50)  
    st.markdown("### Email Assistant")
    st.markdown("---")
    
    selected = option_menu(
        menu_title=None,
        options=["Email Automation", "Chat Interface", "Data Metrics"],
        icons=["envelope-fill", "chat-dots-fill", "arrow-repeat", "graph-up"], 
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
        st.markdown('_please use the format sample below:_')
        
        def convert_df(df):
            return df.to_csv().encode('utf-8')
        
        sample_data = {
            "recipient_name": ["John Doe"],
            "email": ["john.doe@example.com"],
            "subject": ["Sample Subject"]
        }
        df = pd.DataFrame(sample_data)
        csv = convert_df(df)
  
        st.download_button(
            label="Download Sample CSV",
            data=csv,
            file_name="sample.csv",
            mime="text/csv"
        )

        uploaded_file = st.file_uploader("Upload CSV file", type=['csv'])
        
        if uploaded_file is not None:
            df = pd.read_csv(uploaded_file)
            st.dataframe(df)
            
            # Create form for email content
            with st.form(key="email_content_form"):
                email_context = st.text_area("Email Context")
                preview_email = st.form_submit_button("Preview Email")
                send_emails = st.form_submit_button("Send Emails")


                #preview email
                
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
                    # Use the same database instance
                    db = st.session_state.db
                    print(f"[DEBUG] Using user ID: {db.user_id}")
                    
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
    
    db = st.session_state.db

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

        # Save token usage
        db.save_token_usage(tokens_used=150, operation_type="chat_completion")


# ----- METRICS DASHBOARD -----
def metrics_dashboard_page():
    st.title("Metrics Dashboard")
    db = st.session_state.db

    tab1, tab2 = st.tabs(["Email Activity", "Token Usage"])

    with tab1:
        st.subheader("Email Activity")
        try:
            # Get email metrics
            total_emails, unique_recipients, active_days, last_sent = db.get_email_metrics() or (0, 0, 0, None)
            
            # Display email metrics
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Total Emails", f"{total_emails:,}" if total_emails else "0")
            with col2:
                st.metric("Unique Recipients", f"{unique_recipients:,}" if unique_recipients else "0")
            with col3:
                st.metric("Active Days", f"{active_days}" if active_days else "0")
            with col4:
                st.metric("Last Sent", last_sent.strftime("%Y-%m-%d") if last_sent else "Never")

            # Get and display daily email counts
            daily_counts = db.get_daily_email_counts()
            if daily_counts and len(daily_counts) > 0:
                df_emails = pd.DataFrame(daily_counts, columns=['Date', 'Count'])
                
                fig = px.line(
                    df_emails,
                    x='Date',
                    y='Count',
                    title='Daily Email Activity'
                )
                fig.update_layout(
                    xaxis_title="Date",
                    yaxis_title="Emails Sent",
                    showlegend=False
                )
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("No email activity data available yet")
        
        except Exception as e:
            st.error(f"Error loading email metrics: {str(e)}")
            print(f"Email metrics error: {str(e)}")

    with tab2:
        st.subheader("Token Usage")
        try:
            # Get token metrics with proper column handling
            token_data = db.get_daily_token_usage(days=30)
            
            if token_data and len(token_data) > 0:
                # Convert to DataFrame with correct columns
                df_tokens = pd.DataFrame(token_data, columns=['Date', 'Tokens', 'Operations'])
                
                # Create token usage chart
                fig = px.bar(
                    df_tokens,
                    x='Date',
                    y='Tokens',
                    title='Daily Token Usage'
                )
                fig.update_layout(
                    xaxis_title="Date",
                    yaxis_title="Tokens Used",
                    showlegend=False
                )
                st.plotly_chart(fig, use_container_width=True)

                # Show total metrics
                total_metrics = df_tokens.agg({
                    'Tokens': 'sum',
                    'Operations': 'sum'
                })
                
                mcol1, mcol2 = st.columns(2)
                with mcol1:
                    st.metric("Total Tokens", f"{int(total_metrics['Tokens']):,}")
                with mcol2:
                    st.metric("Total Operations", f"{int(total_metrics['Operations']):,}")
                
            else:
                st.info("No token usage data available yet")
                
        except Exception as e:
            st.error(f"Error loading token metrics: {str(e)}")
            print(f"Token metrics error: {str(e)}")

if st.session_state.active_menu == "Data Metrics":
    metrics_dashboard_page()
        

st.sidebar.caption(f"Current Menu: :red[{st.session_state.active_menu}]")
