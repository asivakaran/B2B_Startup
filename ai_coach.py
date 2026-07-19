import os
from groq import Groq
from dotenv import load_dotenv

# 1. Load the environment variables
load_dotenv()

# 2. Grab the Groq API key
my_api_key = os.getenv("GROQ_API_KEY")

if not my_api_key:
    print("ERROR: Could not find GROQ_API_KEY in your .env file!")
    exit()

# 3. Connect to Groq
client = Groq(api_key=my_api_key)

# 4. Ask the user for their goal
user_goal = input("What is your fitness goal? ")

print("\nCoach AI is thinking...\n")

# 5. Send the request to the Llama 3.1 model
try:
    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[
            {"role": "system", "content": "You are a strict but encouraging fitness coach."},
            {"role": "user", "content": f"The user has this fitness goal: {user_goal}. Give them a brief, 3-point plan to achieve it."}
        ]
    )

    # 6. Print the response
    answer = response.choices[0].message.content
    
    if answer:
        print(answer)
    else:
        print("The AI returned an empty response. Try again.")

except Exception as e:
    print(f"An error occurred while talking to the AI: {e}")