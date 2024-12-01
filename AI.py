import torch
from transformers import pipeline
import requests
import os
from dotenv import load_dotenv

load_dotenv()

class AI:
    def __init__(self, model_id):
        self.model_id = model_id
        self.url = "https://api.hyperbolic.xyz/v1/chat/completions"
        self.header = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {os.getenv('API_KEY')}"  
        }

    def generate_response(self, conversation):
        data = {
            "model": self.model_id,
            "messages": conversation,
            "stream": False
        }

        response = requests.post(self.url, json=data, headers=self.header)
        if response.status_code == 200:
            result = response.json()
            # Adjust according to the actual response structure
            generated_text = result['choices'][0]['message']['content']
            return generated_text.strip()
        else:
            return f"Error: {response.status_code} - {response.text}"

    def run(self):
        system_message = {
            "role": "system",
            "content": "You are an assistant. Help the user with their queries."
        }
        conversation = [system_message]

        print("Assistant: Ahoy! How can I assist you today? (Type 'exit' to quit)")

        while True:
            user_input = input("You: ")
            if user_input.lower() in ["exit", "quit"]:
                print("Assistant: Farewell, matey! Until next time!")
                break

            # Add user input to the conversation history
            conversation.append({"role": "user", "content": user_input})

            # Generate response from Hyperbolic API
            response_text = self.generate_response(conversation)

            # Add assistant's response to the conversation
            conversation.append({"role": "assistant", "content": response_text})

            print(f"Assistant: {response_text}")

if __name__ == "__main__":
    model_id = "meta-llama/Meta-Llama-3-70B-Instruct"  
    ai = AI(model_id)
    ai.run()
