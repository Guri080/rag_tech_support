from dotenv import load_dotenv
from openai import OpenAI
import os

load_dotenv()

class LLMClient():
    def __init__(self, 
                 model_name: str = "llama4-scout-17b",):
        self.model_name = model_name
        self.client = OpenAI(
            base_url="https://openai.rc.asu.edu/v1",
            api_key=os.environ["OPENAI_API_KEY"]
        )

    def generate(self, system_prompt: str, user_prompt: str):

        response = self.client.chat.completions.create(
            model=self.model_name,
            messages=[
                {"role": "system", "content": system_prompt,
                 "role": "user", "content": user_prompt}]
        )

        return response.choices[0].message.content