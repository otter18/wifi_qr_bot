#  Copyright (c) ChernV (@otter18), 2021.

import datetime
import logging
import os
import time

import pytz
import telebot
import tg_logger
from flask import Flask, request

import pyqrcode

# ------------- uptime var -------------
boot_time = time.time()
boot_date = datetime.datetime.now(tz=pytz.timezone("Europe/Moscow"))

# ------------- flask config -------------
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD')
app = Flask(__name__)

# ------------- bot config -------------
WEBHOOK_TOKEN = os.environ.get('WEBHOOK_TOKEN')
BOT_TOKEN = os.environ.get('BOT_TOKEN')
bot = telebot.TeleBot(BOT_TOKEN)

# ------------- log ---------------
users = [int(os.environ.get("ADMIN_ID"))]

alpha_logger = logging.getLogger()
alpha_logger.setLevel(logging.INFO)
tg_logger.setup(alpha_logger, token=os.environ.get("LOG_BOT_TOKEN"), users=users)
tg_logger.setup(app.logger, token=os.environ.get("LOG_BOT_TOKEN"), users=users)

logger = logging.getLogger("wifi-qr-bot")

# --------------- temp folder & qr-code setup ---------------
TEMP_FOLDER = 'temp'
SPECIAL_CHARACTERS = '\;,:"'
AuthType = {'WPA': 'WPA',
            'WPA2': 'WPA',
            'WEP': 'WEP',
            'nopass': 'nopass'}


# -------------- status webpage --------------
@app.route('/')
def status():
    password = request.args.get("password")
    if password != ADMIN_PASSWORD:
        logger.info('Status page loaded without password')
        return "<h1>Access denied!<h1>", 403

    return f'<h1>This is <a href="https://github.com/otter18/wifi_qr_bot">wifi_qr_bot</a> server</h1>' \
           f'<p>Made by <a href="https://github.com/otter18">@otter18</a></p>' \
           f'<p>Server uptime: {datetime.timedelta(seconds=time.time() - boot_time)}</p>' \
           f'<p>Server last boot at {boot_date}'


# ------------- webhook ----------------
@app.route('/' + WEBHOOK_TOKEN, methods=['POST'])
def getMessage():
    temp = request.stream.read().decode("utf-8")
    temp = telebot.types.Update.de_json(temp)
    logger.debug('New message received. raw: %s', temp)
    bot.process_new_updates([temp])
    return "!", 200


@app.route("/set_webhook")
def webhook_on():
    password = request.args.get("password")
    if password != ADMIN_PASSWORD:
        logger.info('Set_webhook page loaded without password')
        return "<h1>Access denied!<h1>", 403

    bot.remove_webhook()
    url = 'https://' + os.environ.get('HOST') + '/' + WEBHOOK_TOKEN
    bot.set_webhook(url=url)
    logger.info(f'Webhook is ON! Url: %s', url)
    return "<h1>WebHook is ON!</h1>", 200


@app.route("/remove_webhook")
def webhook_off():
    password = request.args.get("password")
    if password != ADMIN_PASSWORD:
        logger.info('Remove_webhook page loaded without password')
        return "<h1>Access denied!<h1>", 403

    bot.remove_webhook()
    logger.info('WebHook is OFF!')
    return "<h1>WebHook is OFF!</h1>", 200


# --------------- utils -------------------
def gen_qr(name, ssid, pas, t='WPA', hid="False"):
    path = f'{TEMP_FOLDER}/{abs(int(name))}.png'
    if not os.path.exists(TEMP_FOLDER):
        os.mkdir(TEMP_FOLDER)

    for spec_char in SPECIAL_CHARACTERS:
        ssid = ssid.replace(spec_char, f'\\{spec_char}')
        pas = pas.replace(spec_char, f'\\{spec_char}')

    txt = f'WIFI:H:{hid};S:{ssid};T:{t};P:{pas};;'

    t = AuthType.get(t, 'WPA')
    if t == 'nopass':
        txt = f'WIFI:H:{hid};S:{ssid};T:{t};;'

    qr = pyqrcode.create(txt.encode('ascii', 'ignore'))
    qr.png(path, scale=5)

    return path


def check(ssid, pas, t='WPA', hid="False"):
    for elem in [ssid, pas, t, hid]:
        if elem.encode('ascii', 'ignore').decode() != elem:
            return False

        if elem[0] == '<' and elem[-1] == '>':
            return False

    if t not in AuthType:
        return False

    if hid.lower() not in ['true', 'false']:
        return False

    return True


def parse(txt):
    q = txt.split()
    if "'" not in txt and '"' not in txt:
        return q

    new_q = []
    st = False
    for elem in q:
        if not st and elem[0] in ['"', "'"]:
            st = True
            new_q.append('')
        if not st:
            new_q.append(elem)
        if st:
            new_q[-1] += ' ' + elem.replace('"', '').replace("'", '')
        if st and elem[-1] in ['"', "'"]:
            st = False
    new_q = list(map(lambda x: x.strip(), new_q))
    return new_q


# --------------- bot -------------------
@bot.message_handler(commands=['help', 'start'])
def send_welcome(message):
    logger.info(f'</code>@{message.from_user.username}<code> ({message.chat.id}) used /start or /help command')
    bot.send_message(message.chat.id,
                     '<b>Hello! This bot generates WiFi qr-codes.</b>\n\n'
                     '<b>Use commands:</b>\n'
                     '• /create - create details\n'
                     '• /help - to see this message\n\n'
                     '<b>NO WiFi data is stored!</b>\n'
                     'Source code is available <a href="https://github.com/otter18/wifi_qr_bot">here</a>',
                     parse_mode='HTML')


@bot.message_handler(regexp=r'\/create (.+?|[\'\"].+?[\'\"]) (.+?|[\'\"].+?[\'\"])$')
def create1(message):
    logger.info(f'</code>@{message.from_user.username}<code> ({message.chat.id}) created qr-code with less params')

    _, ssid, pas = parse(message.text)
    if not check(ssid, pas):
        bot.send_message(message.chat.id,
                         'Invalid format. Pay attention, that only ascii chars are supported.\n'
                         'Use something similar to <code>/create MyWiFiName VerySavePassword</code>',
                         parse_mode='HTML')
        return

    path = gen_qr(message.chat.id, ssid, pas)

    photo = open(path, 'rb')
    bot.send_photo(message.chat.id, photo)
      
    os.remove(path)


@bot.message_handler(regexp=r'\/create (.+?|[\'\"].+?[\'\"]) (.+?|[\'\"].+?[\'\"]) [\w<>]+ [\w<>]+$')
def create2(message):
    logger.info(f'</code>@{message.from_user.username}<code> ({message.chat.id}) created qr-code with full params')

    _, ssid, pas, auth, hid = parse(message.text)
    if not check(ssid, pas, auth, hid):
        bot.send_message(message.chat.id,
                         'Invalid format. Pay attention, that only ascii chars are supported.\n'
                         'Use something similar to\n\n<code>/create MyWiFiName VerySavePassword WPA2 False</code>',
                         parse_mode='HTML')
        return

    path = gen_qr(abs(int(message.chat.id)), ssid, pas, auth, hid)

    photo = open(path, 'rb')
    bot.send_photo(message.chat.id, photo)


@bot.message_handler(commands=['create'])
def create(message):
    logger.info(f'</code>@{message.from_user.username}<code> ({message.chat.id}) wants create info')
    bot.send_message(message.chat.id,
                     '*Use one of the following command formats:*\n'
                     '• /create <SSID> <PASSWORD>\n'
                     '• /create <SSID> <PASSWORD: None if nopass> <AuthType: WPA, WPA2, WEP, nopass> <HIDDEN: True, False>',
                     parse_mode='markdown')


@bot.message_handler(func=lambda message: True)
def invalid(message):
    logger.info(f'</code>@{message.from_user.username}<code> ({message.chat.id}) used invalid command:\n\n%s', message.text)
    bot.send_message(message.chat.id, "Invalid command. Use /help for help")


if __name__ == '__main__':
    if os.environ.get("IS_PRODUCTION", "False") == "True":
        app.run()
    else:
        bot.polling(none_stop=True)
