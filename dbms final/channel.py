# broadcast_module zip creator
# This will include all files and folder structure for your independent demo

import zipfile
import os

# Create folder structure
folders = [
    'broadcast_module',
    'broadcast_module/channels',
    'broadcast_module/db'
]
for folder in folders:
    os.makedirs(folder, exist_ok=True)

# Config file
config_content = '''
# config.py
TELEGRAM_BOT_TOKEN = 'YOUR_TELEGRAM_BOT_TOKEN'
DISCORD_BOT_TOKEN = 'YOUR_DISCORD_BOT_TOKEN'
EMAIL_HOST = 'smtp.example.com'
EMAIL_PORT = 587
EMAIL_USER = 'your_email@example.com'
EMAIL_PASS = 'your_email_password'
''' 
with open('broadcast_module/config.py', 'w') as f:
    f.write(config_content)

# Telegram module
telegram_content = '''
from telegram import Bot
from config import TELEGRAM_BOT_TOKEN

bot = Bot(token=TELEGRAM_BOT_TOKEN)

def send_telegram(chat_id, message):
    bot.send_message(chat_id=chat_id, text=message)
'''
with open('broadcast_module/channels/telegram.py', 'w') as f:
    f.write(telegram_content)

# Discord module
discord_content = '''
import discord
from config import DISCORD_BOT_TOKEN

intents = discord.Intents.default()
client = discord.Client(intents=intents)

async def send_discord(user_id, message):
    user = await client.fetch_user(user_id)
    await user.send(message)
'''
with open('broadcast_module/channels/discord.py', 'w') as f:
    f.write(discord_content)

# Email module
email_content = '''
import smtplib
from email.mime.text import MIMEText
from config import EMAIL_HOST, EMAIL_PORT, EMAIL_USER, EMAIL_PASS

def send_email(to_email, subject, body):
    msg = MIMEText(body)
    msg['Subject'] = subject
    msg['From'] = EMAIL_USER
    msg['To'] = to_email

    with smtplib.SMTP(EMAIL_HOST, EMAIL_PORT) as server:
        server.starttls()
        server.login(EMAIL_USER, EMAIL_PASS)
        server.send_message(msg)
'''
with open('broadcast_module/channels/email.py', 'w') as f:
    f.write(email_content)

# MySQL module
mysql_content = '''
import pymysql

def get_connection():
    return pymysql.connect(host='localhost', user='root', password='password', database='lms')
'''
with open('broadcast_module/db/mysql.py', 'w') as f:
    f.write(mysql_content)

# Main script
main_content = '''
from channels import telegram, discord, email

students = [
    {'name':'Alice','telegram_id':'123','discord_id':'456','email':'alice@example.com','preferred_channel':'telegram'},
    {'name':'Bob','telegram_id':'789','discord_id':'012','email':'bob@example.com','preferred_channel':'discord'},
    {'name':'Carol','telegram_id':'345','discord_id':'678','email':'carol@example.com','preferred_channel':'email'},
]

message = "CS101 Announcement: Submit Assignment 2 via LMS. Contact: prof@college.edu"

for student in students:
    if 'telegram' in student['preferred_channel']:
        telegram.send_telegram(student['telegram_id'], message)
    if 'discord' in student['preferred_channel']:
        # discord sending requires async run
        import asyncio
        asyncio.run(discord.send_discord(student['discord_id'], message))
    if 'email' in student['preferred_channel']:
        email.send_email(student['email'], "CS101 Announcement", message)
'''
with open('broadcast_module/main.py', 'w') as f:
    f.write(main_content)

# Requirements
requirements_content = '''
python-telegram-bot
discord.py
pymysql
'''
with open('broadcast_module/requirements.txt', 'w') as f:
    f.write(requirements_content)

# README
readme_content = '''
# Broadcast Module Demo

1. Set your tokens and credentials in config.py
2. Install requirements: pip install -r requirements.txt
3. Run: python main.py

This demo sends messages via Telegram, Discord, and Email according to student preferences.
'''
with open('broadcast_module/README.md', 'w') as f:
    f.write(readme_content)

# Create zip
zipf = zipfile.ZipFile('broadcast_module.zip','w', zipfile.ZIP_DEFLATED)
for root, dirs, files in os.walk('broadcast_module'):
    for file in files:
        zipf.write(os.path.join(root, file), os.path.relpath(os.path.join(root, file), 'broadcast_module'))
zipf.close()

print("broadcast_module.zip created successfully!")
