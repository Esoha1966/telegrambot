from telebot import TeleBot, types
from datetime import datetime as dt, timedelta, time
import sqlite3
import threading
import os
from keepalive import keep_alive
import pytz
from PIL import Image, ImageDraw, ImageFont

# Initialize bot with Telegram token
bot = TeleBot(os.getenv('tg_key'))

# Set the timezone to Nicosia, Cyprus (GMT+3)
tz = pytz.timezone('Asia/Nicosia')

# Call keep_alive function to connect to the Flask server
keep_alive()

# Create thread-local storage for SQLite connection
local_storage = threading.local()

# Stores all user's reservations
available_time_slots = {}

def get_db_connection():
    if not hasattr(local_storage, 'db'):
        db_dir = '/opt/render/project/src/data'
        os.makedirs(db_dir, exist_ok=True)  # Create directory if it doesn't exist
        db_path = os.path.join(db_dir, 'tennis_court_reservation.db')
        local_storage.db = sqlite3.connect(db_path)
        create_reservations_table()
    return local_storage.db

def create_reservations_table():
    db_connection = get_db_connection()
    cursor = db_connection.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS reservations (
            user_id INTEGER PRIMARY KEY,
            reservation_time TEXT
        )
    ''')
    db_connection.commit()

def save_reservation_to_db(user_id, reservation_time):
    cursor = get_db_connection().cursor()
    cursor.execute("INSERT INTO reservations (user_id, reservation_time) VALUES (?, ?)", (user_id, reservation_time))
    get_db_connection().commit()

def delete_reservation_from_db(user_id):
    cursor = get_db_connection().cursor()
    cursor.execute("DELETE FROM reservations WHERE user_id=?", (user_id,))
    get_db_connection().commit()

def generate_reservation_image(first_name, last_name, date, time):
    image = Image.new('RGB', (800, 400), color='white')
    draw = ImageDraw.Draw(image)
    font_path = os.path.join(os.path.dirname(__file__), "arial.ttf")
    try:
        font = ImageFont.truetype(font_path, size=20)
    except IOError:
        font = ImageFont.load_default()
    texts = [f"Name: {first_name} {last_name}", f"Date: {date}", f"Time: {time}"]
    total_text_height = sum(draw.textsize(text, font=font)[1] for text in texts)
    y_offset = (image.height - total_text_height) // 2
    for text in texts:
        text_width, text_height = draw.textsize(text, font=font)
        x_position = (image.width - text_width) // 2
        draw.text((x_position, y_offset), text, font=font, fill='black')
        y_offset += text_height + 10
    image_path = f"{first_name}_{last_name}_{date}_{time.replace(':', '-')}.png"
    image.save(image_path)
    return image, image_path

def generate_date_selection_buttons():
    current_time = dt.now()
    markup = types.InlineKeyboardMarkup()
    for i in range(7):
        date = current_time + timedelta(days=i)
        button = types.InlineKeyboardButton(text=date.strftime('%b %d'), callback_data=date.strftime('%Y-%m-%d'))
        markup.add(button)
    return markup

def generate_available_time_slots(date):
    start_of_day = time(0, 0)
    aware_date_start = tz.localize(dt.combine(date, start_of_day))
    reserved_slots = get_reserved_time_slots(date)
    available_slots = [
        aware_date_start + timedelta(hours=h)
        for h in range(6, 22)
        if (aware_date_start + timedelta(hours=h)).strftime('%H:%M') not in reserved_slots
    ]
    return available_slots

def get_reserved_time_slots(date):
    cursor = get_db_connection().cursor()
    cursor.execute("SELECT reservation_time FROM reservations WHERE strftime('%Y-%m-%d', reservation_time) = ?", (date.strftime('%Y-%m-%d'),))
    reserved_times = cursor.fetchall()
    reserved_slots = [dt.strptime(time[0], '%Y-%m-%d %H:%M').strftime('%H:%M') for time in reserved_times]
    return reserved_slots

def send_confirmation(chat_id, reservation_datetime, message, user_info):
    user_id = message.from_user.id
    first_name = user_info['first_name']
    last_name = user_info.get('last_name', '')
    image, image_path = generate_reservation_image(
        first_name, last_name,
        reservation_datetime.strftime('%Y-%m-%d'),
        reservation_datetime.strftime('%H:%M')
    )
    with open(image_path, 'rb') as photo:
        bot.send_photo(chat_id, photo, caption="Congratulations! You have successfully reserved the tennis court!")
    os.remove(image_path)
    save_reservation_to_db(user_id, reservation_datetime.strftime('%Y-%m-%d %H:%M'))
    new_reservation = (user_id, reservation_datetime)
    save_reservation_to_file(new_reservation, 'reservations.txt')
    start_markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    start_markup.add(
        types.KeyboardButton('/start'),
        types.KeyboardButton('/reserve'),
        types.KeyboardButton('/cancel'),
        types.KeyboardButton('/support'),
        types.KeyboardButton('/location')
    )
    bot.send_message(message.chat.id, "Choose the function:", reply_markup=start_markup)

def save_reservation_to_file(reservation, file_path):
    user_id, reservation_time = reservation
    if isinstance(reservation_time, dt
