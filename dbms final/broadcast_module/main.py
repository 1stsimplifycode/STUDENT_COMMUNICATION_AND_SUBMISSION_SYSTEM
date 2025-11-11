import asyncio
from channels import email
from channels.telegram import send_telegram_async
from channels.discord import send_discord, close_client
from config import TELEGRAM_BOT_TOKEN, DISCORD_BOT_TOKEN, EMAIL_USER

# Student data
students = [
    {
        'name': 'Alpha',
        'telegram_id': '1572365453',  # Your actual Chat ID
        'discord_id': '456789012345678901',
        'email': 'mailtoadishreegupta@gmail.com',
        'preferred_channel': 'telegram'
    },
    {
        'name': 'Alpha - Email Test',
        'telegram_id': '1572365453',
        'email': 'mailtoadishreegupta@gmail.com',
        'preferred_channel': 'email'
    },
    {
        'name': 'Bob',
        'telegram_id': '789',
        'discord_id': '012',
        'email': 'bob@example.com',
        'preferred_channel': 'discord'
    },
    {
        'name': 'Carol',
        'telegram_id': '345',
        'discord_id': '678',
        'email': 'carol@example.com',
        'preferred_channel': 'email'
    },
]

message = "CS101 Announcement: Submit Assignment 2 via LMS. Contact: prof@college.edu"

async def send_messages():
    """Send messages to all students via their preferred channels"""
    
    success_count = 0
    fail_count = 0
    
    for student in students:
        print(f"\nSending to {student['name']} via {student['preferred_channel']}...")
        
        try:
            if student['preferred_channel'] == 'telegram':
                if not TELEGRAM_BOT_TOKEN:
                    print(f"✗ Skipping {student['name']}: Telegram token not configured")
                    fail_count += 1
                    continue
                await send_telegram_async(student['telegram_id'], message)
                print(f"✓ Telegram message sent to {student['name']}")
                success_count += 1
                
            elif student['preferred_channel'] == 'discord':
                if not DISCORD_BOT_TOKEN:
                    print(f"✗ Skipping {student['name']}: Discord token not configured")
                    fail_count += 1
                    continue
                result = await send_discord(student['discord_id'], message)
                if result:
                    success_count += 1
                else:
                    fail_count += 1
                
            elif student['preferred_channel'] == 'email':
                if not EMAIL_USER:
                    print(f"✗ Skipping {student['name']}: Email not configured")
                    fail_count += 1
                    continue
                result = email.send_email(
                    student['email'], 
                    "CS101 Announcement", 
                    message
                )
                if result:
                    success_count += 1
                else:
                    fail_count += 1
                    
            else:
                print(f"✗ Unknown channel: {student['preferred_channel']}")
                fail_count += 1
                
        except Exception as e:
            print(f"✗ Failed to send message to {student['name']}: {e}")
            fail_count += 1
    
    # Clean up Discord client
    try:
        await close_client()
    except:
        pass
    
    return success_count, fail_count

def main():
    """Main entry point"""
    print("=" * 60)
    print("BROADCAST MODULE - LMS Notification System")
    print("=" * 60)
    
    # Check configuration
    print("\nChecking configuration...")
    if TELEGRAM_BOT_TOKEN:
        print("✓ Telegram configured")
    else:
        print("✗ Telegram not configured")
    
    if DISCORD_BOT_TOKEN:
        print("✓ Discord configured")
    else:
        print("✗ Discord not configured")
    
    if EMAIL_USER:
        print("✓ Email configured")
    else:
        print("✗ Email not configured")
    
    print("\nStarting message broadcast...\n")
    
    try:
        success, failed = asyncio.run(send_messages())
        print("\n" + "=" * 60)
        print(f"SUMMARY: {success} sent successfully, {failed} failed")
        print("=" * 60)
    except KeyboardInterrupt:
        print("\n✗ Broadcast interrupted by user")
    except Exception as e:
        print(f"\n✗ Broadcast failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()