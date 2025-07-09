import nest_asyncio
nest_asyncio.apply()

import logging
import asyncio
from telethon import TelegramClient, events
from openai import OpenAI
import os
from dotenv import load_dotenv
import httpx

# Load environment variables
load_dotenv()
bot_token = os.getenv("bot_token")
api_id = os.getenv("api_id")
api_hash = os.getenv("api_hash")
openai_api_key = os.getenv("OPENAI_API_KEY")

# Set up logging
logging.basicConfig(level=logging.INFO)

# Initialize Telegram client
client = TelegramClient('yesbot', api_id, api_hash)

# Initialize OpenAI client with custom httpx client
ai_client = OpenAI(
    api_key=openai_api_key,
    http_client=httpx.Client(follow_redirects=True)
)

async def main():
    # Start Telegram client with bot token
    await client.start(bot_token=bot_token)

    @client.on(events.NewMessage(pattern='/start'))
    async def start_handler(event):
        await event.respond("👋 Hello! I am Yesbol AI Bot. How can I assist you today?")
        logging.info(f'/start received from {event.sender_id}')

    @client.on(events.NewMessage(pattern='/info'))
    async def info_handler(event):
        await event.respond("🤖 This AI Chatbot is built using Python, Telethon, and OpenAI API.")
        logging.info(f'/info received from {event.sender_id}')

    @client.on(events.NewMessage(pattern='/help'))
    async def help_handler(event):
        help_text = (
            "📌 Available Commands:\n"
            "/start – Start the bot\n"
            "/help – Get help information\n"
            "/info – Learn about the bot\n"
        )
        await event.respond(help_text)
        logging.info(f"/help received from {event.sender_id}")

    @client.on(events.NewMessage)
    async def keyword_responder(event):
        message = event.text.strip()
        if message.lower() in ['/start', '/help', '/info']:
            return

        logging.info(f"Message from {event.sender_id}: {message}")

        try:
            response = ai_client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "user", "content": message}
                ],
                max_tokens=128,
                temperature=0.7,
            )
            reply = response.choices[0].message.content
            await event.respond(reply)
        except Exception as e:
            logging.error(f"OpenAI error: {e}")
            await event.respond("⚠️ Sorry, I couldn't process that message.")

    await client.run_until_disconnected()

if __name__ == "__main__":
    asyncio.run(main())
