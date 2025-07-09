from telebot import TeleBot, types
from datetime import datetime as dt, timedelta, time
import sqlite3
import threading
import os
from keep_alive import keep_alive
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
        db_path = os.path.join('/opt/render/project/src/data', 'tennis_court_reservation.db')
        local_storage.db = sqlite3.connect(db_path)
        create_reservations_table()
自主

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
    if isinstance(reservation_time, dt):
        reservation_time_formatted = reservation_time.strftime("%Y-%m-%d %H:%M")
    else:
        reservation_time_formatted = reservation_time
    user_info = get_user_info(user_id)
    first_name = user_info['first_name']
    last_name = user_info.get('last_name', '')
    reservation_info = f"User ID: {user_id}, Name: {first_name} {last_name}, Reservation Date and Time: {reservation_time_formatted}\n"
    with open(file_path, 'a') as file:
        file.write(reservation_info)

def get_all_reservations():
    db_connection = get_db_connection()
    cursor = db_connection.cursor()
    cursor.execute("SELECT user_id, reservation_time FROM reservations")
    return cursor.fetchall()

def get_user_info(user_id):
    try:
        user = bot.get_chat(user_id)
        return {
            'id': user.id,
            'first_name': user.first_name,
            'last_name': user.last_name
        }
    except Exception as e:
        print(f"Failed to get user information for user_id {user_id}: {e}")
        return {}

@bot.message_handler(commands=['start'])
def send_welcome(message):
    start_markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    start_markup.add(
        types.KeyboardButton('/start'),
        types.KeyboardButton('/reserve'),
        types.KeyboardButton('/cancel'),
        types.KeyboardButton('/support'),
        types.KeyboardButton('/location')
    )
    bot.send_message(message.chat.id, "Welcome to the Tennis Court Reservation Bot!\n\nUse /start to start again.\n\nUse /reserve to book a court for 1 hour.\n\nUse /cancel to cancel your reservation.\n\nUse /support to text the support team.\n\nUse /location to get the court location.")
    bot.send_message(message.chat.id, "Choose the function:", reply_markup=start_markup)

@bot.message_handler(commands=['support'])
def on_start_command(message):
    markup = types.InlineKeyboardMarkup()
    btn = types.InlineKeyboardButton("Text support", url='https://t.me/ImMrAlex')
    markup.add(btn)
    bot.send_message(message.chat.id, "Press the button to text the support team.", reply_markup=markup)
    start_markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    start_markup.add(
        types.KeyboardButton('/start'),
        types.KeyboardButton('/reserve'),
        types.KeyboardButton('/cancel'),
        types.KeyboardButton('/support'),
        types.KeyboardButton('/location')
    )
    bot.send_message(message.chat.id, "Choose the function:", reply_markup=start_markup)

@bot.message_handler(commands=['location'])
def send_location(message):
    latitude = 34.70197266790477
    longitude = 33.07582804045963
    bot.send_location(message.chat.id, latitude, longitude)
    bot.send_message(message.chat.id, 'Court is near Sklavenitis Columbia Parking, behind Sklavenitis Columbia, Germasogeia Limassol')
    start_markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    start_markup.add(
        types.KeyboardButton('/start'),
        types.KeyboardButton('/reserve'),
        types.KeyboardButton('/cancel'),
        types.KeyboardButton('/support'),
        types.KeyboardButton('/location')
    )
    bot.send_message(message.chat.id, "Choose the function:", reply_markup=start_markup)

@bot.message_handler(commands=['reserve'])
def ask_for_date(message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    cursor = get_db_connection().cursor()
    cursor.execute("SELECT reservation_time FROM reservations WHERE user_id=?", (user_id,))
    reservation_time = cursor.fetchone()
    if reservation_time:
        reservation_time_naive = dt.strptime(reservation_time[0], '%Y-%m-%d %H:%M')
        reservation_time_aware = tz.localize(reservation_time_naive)
        if reservation_time_aware > dt.now(tz):
            bot.send_message(chat_id, f"You already have a reservation on {reservation_time[0]}. You can't make a new reservation until this one is past.")
            return
        else:
            delete_reservation_from_db(user_id)
    markup = generate_date_selection_buttons()
    bot.send_message(chat_id, "Please select the date you want to play:", reply_markup=markup)

@bot.message_handler(commands=['cancel'])
def cancel(message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    cursor = get_db_connection().cursor()
    cursor.execute("SELECT reservation_time FROM reservations WHERE user_id=?", (user_id,))
    reservation_time = cursor.fetchone()
    if reservation_time:
        reservation_date = dt.strptime(reservation_time[0], '%Y-%m-%d %H:%M').date()
        delete_reservation_from_db(user_id)
        generate_available_time_slots(reservation_date)
        bot.send_message(chat_id, "Your reservation has been canceled.")
        new_reservation = (user_id, f"{reservation_time[0]}, canceled")
        save_reservation_to_file(new_reservation, 'reservations.txt')
    else:
        bot.send_message(chat_id, "You don't have any reservation to cancel.")

@bot.callback_query_handler(func=lambda call: True)
def process_date_selection(call):
    chat_id = call.message.chat.id
    user_id = call.from_user.id
    selected_date = call.data
    reservation_date = dt.strptime(selected_date, '%Y-%m-%d').date()
    current_time = dt.now().date()
    next_7_days = current_time + timedelta(days=7)
    if current_time <= reservation_date <= next_7_days:
        available_slots = generate_available_time_slots(reservation_date)
        if not available_slots:
            bot.send_message(chat_id, f"Sorry, no available time slots for {reservation_date.strftime('%Y-%m-%d')}.")
        else:
            available_time_slots[user_id] = {'date': reservation_date, 'slots': available_slots}
            markup = generate_time_selection_buttons(available_slots)
            bot.send_message(chat_id, f"Available time slots for {reservation_date.strftime('%Y-%m-%d')}:", reply_markup=markup)
    else:
        bot.send_message(chat_id, "Sorry, you can only reserve a time within the next 7 days.")

def generate_time_selection_buttons(available_slots):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=3)
    current_datetime = dt.now(tz)
    for slot in available_slots:
        if 6 <= slot.hour < 22 and slot >= current_datetime + timedelta(minutes=5):
            button = types.KeyboardButton(slot.strftime('%H:%M'))
            markup.add(button)
    return markup

@bot.message_handler(func=lambda message: message.text and message.text in [slot.strftime('%H:%M') for slot in available_time_slots.get(message.from_user.id, {}).get('slots', [])])
def process_time_selection(message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    selected_time = message.text.strip()
    selected_date = available_time_slots[user_id]['date']
    selected_time_obj = dt.strptime(selected_time, '%H:%M').time()
    reservation_datetime = dt.combine(selected_date, selected_time_obj)
    reservation_datetime = tz.localize(reservation_datetime)
    if reservation_datetime < dt.now(tz):
        bot.send_message(chat_id, "You cannot reserve a time in the past.")
    else:
        save_reservation_to_db(user_id, reservation_datetime.strftime('%Y-%m-%d %H:%M'))
        user_info = get_user_info(user_id)
        send_confirmation(chat_id, reservation_datetime, message, user_info)
        available_time_slots[user_id]['slots'] = [slot for slot in available_time_slots[user_id]['slots'] if slot.strftime('%H:%M') != selected_time]
        available_time_slots[user_id]['slots'] = [slot for slot in available_time_slots[user_id]['slots'] if slot.astimezone(tz) > dt.now(tz)]

@bot.message_handler(content_types=['text'])
def handle_text(message):
    start_markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    start_markup.add(
        types.KeyboardButton('/start'),
        types.KeyboardButton('/reserve'),
        types.KeyboardButton('/cancel'),
        types.KeyboardButton('/support'),
        types.KeyboardButton('/location')
    )
    bot.send_message(message.chat.id, "Choose command to continue:", reply_markup=start_markup)

bot.polling(none_stop=True)
