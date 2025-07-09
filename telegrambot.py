import nest_asyncio
nest_asyncio.apply()
import logging
import asyncio
from telethon import TelegramClient, events
from openai import OpenAI
import os
from dotenv import load_dotenv

load_dotenv()
bot_token = os.getenv("bot_token")
api_id = os.getenv("api_id")
api_hash = os.getenv("api_hash")

# setup logging
logging.basicConfig(level=logging.INFO)



# create telegram client
client = TelegramClient('yesbot', api_id, api_hash)
# create ai client
ai_client = OpenAI(
    api_key = os.getenv("OPENAI_API_KEY")
    )

async def main():
    # start the client
    await client.start(bot_token=bot_token)

    # handler for /start command
    @client.on(events.NewMessage(pattern='/start'))
    async def start_handler(event):
        await event.respond("Hello! I am Yesbol AI Bot. How can I assist you today?")
        logging.info(f'Start command received from {event.sender_id}')

    # handler for /info command
    @client.on(events.NewMessage(pattern='/info'))
    async def info_handler(event):
        await event.respond("This AI Chatbot is created in Python with OpenAI API.")
        logging.info(f'Info command received from {event.sender_id}')

    # handler for /help command
    @client.on(events.NewMessage(pattern='/help'))
    async def help_hander(event):
        help_text = (
            "Here are the commands you can use:\n"
            "/start - Start the bot\n"
            "/help - Get Help Information\n"
            "/info - Get Information about the Bot\n"
        )
        await event.respond(help_text)
        logging.info(f"Help command received from {event.sender_id}")

    # keyword based response handler
    @client.on(events.NewMessage)
    async def keyword_responder(event):
        # get the message text
        message = event.text.lower()
        if message in ['/start', '/help', '/info']:
            return

        # get response from AI client
        response = ai_client.chat.completions.create(
            model='gpt-4o-mini',
            messages=[
                {
                    'role': 'user', "content": message
                }
            ],
            max_tokens=128
        )

        # get content from response
        response = response.choices[0].message.content
        if response:
            await event.respond(response)
        logging.info(f"Message received from {event.sender_id}: {event.text}")

    await client.run_until_disconnected()

asyncio.run(main())