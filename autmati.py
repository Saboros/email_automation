import csv
import requests
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import datetime
from dotenv import load_dotenv
import os

#load .env file
load_dotenv()


class EmailAutomation:
    def __init__(self, api_key, smtp_server, port, sender_email, sender_password, sender_name):
        self.api_key = api_key
        self.smtp_server = smtp_server
        self.port = port
        self.sender_email = sender_email
        self.sender_password = sender_password
        self.sender_name = sender_name
        self.api_url = "https://api.hyperbolic.xyz/v1/chat/completions" 
    

    def generate_email(self, subject, recipient_name, email_context):
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        prompt = f"""
        Write a professional email with the following details:
               f"[INSTRUCTION] Write a business email with these parameters:\n"
                f"- From: {self.sender_name}\n"
                f"- To: {recipient_name}\n"
                f"- Subject: {subject}\n"
                f"- Context: {email_context}\n"
                f"[IMPORTANT]\n"
                f"- Do not repeat or paraphrase the last email sent.\n"
                f"- Only respond if the email requires additional information, confirmation, or follow-up.\n"
                f"- Check the context to avoid duplicating responses.\n"
                f"[OUTPUT FORMAT]\n"
                f"- Write only the email body.\n"
                f"- Be concise and professional.\n"
                f"- Conclude with a signature using the sender's name: {self.sender_name}.\n"
                f"[BEGIN EMAIL]\n"
        """
        data = {
            "model": "meta-llama/Meta-Llama-3-70B-Instruct",  
            "messages": [
                {"role": "system", "content": "[SYSTEM] You are a professional email writer. Generate only the email body.\n"},
                {"role": "user", "content": prompt}
            ],
            "stream": False
        }
        response = requests.post(self.api_url, json=data, headers=headers)
        if response.status_code == 200:
            result = response.json()
            email_body = result['choices'][0]['message']['content']
            return email_body.strip()
        else:
            print(f"Error generating email: {response.status_code} - {response.text}")
            return None

    def send_email(self, recipient_email, subject, email_body):
        # Use smtplib to send the email
        msg = MIMEMultipart()
        msg['From'] = f"{self.sender_name} <{self.sender_email}>"
        msg['To'] = recipient_email
        msg['Subject'] = subject
        msg.attach(MIMEText(email_body, 'plain'))

        try:
            server = smtplib.SMTP(self.smtp_server, self.port)
            server.starttls()
            server.login(self.sender_email, self.sender_password)
            server.send_message(msg)
            server.quit()
            print(f"Email sent to {recipient_email}")
        except Exception as e:
            print(f"Failed to send email to {recipient_email}: {str(e)}")

    def process_csv_and_send_emails(self, csv_filename, context):
        """
        Read CSV file and send emails to each recipient.
        """
        try:
            with open(csv_filename, newline='', encoding='utf-8') as csvfile:
                reader = csv.DictReader(csvfile)
                for row in reader:
                    recipient_name = row['recipient_name']
                    recipient_email = row['email']
                    subject = row['subject']

                    # Generate the email body using the LLM model
                    email_body = self.generate_email(subject, recipient_name, context)
                    if email_body:
                        self.send_email(recipient_email, subject, email_body)
                    else:
                        print(f"Failed to generate email content for {recipient_name}. Email not sent.")
        except Exception as e:
            print(f"Error processing CSV file: {e}")


if __name__ == "__main__":
    api_key = f"{os.getenv('API_KEY')}" 
    smtp_server = "smtp.gmail.com"
    port = 587
    sender_email = "joshuaplacer09@gmail.com"
    sender_password = "SENDER_PASSWORD"  
    sender_name = "Joshua Placer"
    csv_filename = 'D:/_Python Projects/ModifiedLLM/Docs/email_list.csv' 

    # Initialize the EmailAutomation class
    context = input("Enter the context for the email: ")
    email_automation = EmailAutomation(api_key, smtp_server, port, sender_email, sender_password, sender_name)

    email_automation.process_csv_and_send_emails(csv_filename, context)
