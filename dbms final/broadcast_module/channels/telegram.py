import asyncio
from telegram import Bot
from config import TELEGRAM_BOT_TOKEN

bot = Bot(token=TELEGRAM_BOT_TOKEN)

async def send_telegram_async(chat_id, message):
    """Async version - use this in async contexts"""
    await bot.send_message(chat_id=chat_id, text=message)

def send_telegram(chat_id, message):
    """Synchronous wrapper - creates new event loop if needed"""
    try:
        # Try to get existing event loop
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # If loop is running, we can't use asyncio.run()
            # This shouldn't happen in normal circumstances
            raise RuntimeError("Cannot use sync function in async context")
        else:
            # Loop exists but not running
            return loop.run_until_complete(send_telegram_async(chat_id, message))
    except RuntimeError:
        # No event loop exists, create one with asyncio.run()
        return asyncio.run(send_telegram_async(chat_id, message))