import discord
import asyncio
from config import DISCORD_BOT_TOKEN

class DiscordMessenger:
    def __init__(self):
        intents = discord.Intents.default()
        intents.members = True
        intents.message_content = True
        self.client = discord.Client(intents=intents)
        self.ready = False
        self.client_task = None
        
        @self.client.event
        async def on_ready():
            self.ready = True
            print(f'Discord bot logged in as {self.client.user}')
    
    async def start(self):
        """Start the Discord client in background"""
        if not self.ready and self.client_task is None:
            self.client_task = asyncio.create_task(self.client.start(DISCORD_BOT_TOKEN))
            # Wait for ready
            for _ in range(50):  # 5 second timeout
                if self.ready:
                    break
                await asyncio.sleep(0.1)
            if not self.ready:
                raise TimeoutError("Discord client failed to connect")
    
    async def send_message(self, user_id, message):
        """Send a DM to a Discord user"""
        await self.start()
        
        try:
            user = await self.client.fetch_user(int(user_id))
            await user.send(message)
            print(f"Discord message sent to user {user_id}")
            return True
        except discord.errors.Forbidden:
            print(f"Cannot send message to user {user_id}: DMs disabled or bot blocked")
            return False
        except discord.errors.NotFound:
            print(f"User {user_id} not found")
            return False
        except ValueError:
            print(f"Invalid user ID format: {user_id}")
            return False
        except Exception as e:
            print(f"Error sending Discord message to {user_id}: {e}")
            return False
    
    async def close(self):
        """Close the Discord client"""
        if self.ready:
            await self.client.close()
            if self.client_task:
                self.client_task.cancel()
                try:
                    await self.client_task
                except asyncio.CancelledError:
                    pass
            print("Discord client closed")

# Global instance
_messenger = DiscordMessenger()

async def send_discord(user_id, message):
    """Send a Discord DM"""
    return await _messenger.send_message(user_id, message)

async def close_client():
    """Close the Discord client"""
    await _messenger.close()