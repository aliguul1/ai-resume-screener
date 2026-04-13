from dotenv import load_dotenv
import os

# Load environment variables from .env file
load_dotenv()

# Now you can access variables
api_key = os.getenv('OPENAI_API_KEY')




from openai import OpenAI
client = OpenAI()

response = client.responses.create(
    model="gpt-4o-mini",
    input="Write a one-sentence bedtime story about a unicorn."
)

print(response.output_text)