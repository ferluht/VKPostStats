from telegram.ext import CommandHandler
from telegram.ext import Updater
from telegram.ext import MessageHandler, Filters
from telegram.error import Unauthorized
import logging
from pymongo import MongoClient
from vkutils import get_posts_with_audio, vk_connect
import time
import json

with open('settings.json', 'r') as file:
    settings = json.load(file)

log_chat_id = settings['log_chat_id']
scan_period = settings['scan_period']

updater = Updater(token=settings['telegram_token'])
j = updater.job_queue

db = MongoClient(settings['mongo_host'], settings['mongo_port'])
db = db.VKMusicStats

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

helptext = '''
Бот умеет отслежвать записи с приклеплённым аудио заданного артиста. Позже будет добавлен поиск репостов и сбор статистики по лайкам.

Команды:
/setartist - задать артиста
/checkartist - проверить, кого ищем
/allhistory - все посты, уже наденные раньше
/help - справка
'''

START = '0'
ARTISTNAME = '1'
WORKING = '2'

def start(bot, update):
    help(bot, update)
    setartist(bot, update)

def service_message(bot, update):
    users = db['users']
    for user in users.find():
        bot.send_message(chat_id=user['id'], text=update.message.text[15:])

def setartist(bot, update):
    users = db['users']
    uid = str(update.message.chat_id)
    user_tg = update.message.from_user
    if users.find({'id': uid}).count() > 0:
        users.update_one({"id": uid}, {"$set": {"state": START }})
        bot.send_message(chat_id=log_chat_id, text='Restart {} | @{}'
                        .format(str(user_tg['first_name']), str(user_tg['username'])))
    else:
        bot.send_message(chat_id=log_chat_id, text='New user {} | @{}'
                        .format(str(user_tg['first_name']), str(user_tg['username'])))
        users.insert_one({"id": uid, "state": START, "artist": None })
    bot.send_message(chat_id=update.message.chat_id, text="Напиши имя артиста/группы")

def default(bot, update):
    users = db['users']
    artists = db['artists']
    uid = str(update.message.chat_id)
    user = users.find_one({'id': uid})
    user_tg = update.message.from_user
    if user['state'] == START:
        artist = str(update.message.text)
        users.update_one({'id': uid}, {"$set": {'artist': artist, 'state': WORKING}})
        bot.send_message(chat_id=update.message.chat_id, text='''Ищем посты с {}'''.format(artist))
        bot.send_message(chat_id=log_chat_id, text='Set artist {} for {} | @{}'
                         .format(artist, str(user_tg['first_name']), str(user_tg['username'])))
        sendall(uid, bot, user_tg)
        api = vk_connect(settings['vk_access_token'])
        scan_artist(bot, artist, api)
    else:
        bot.send_message(chat_id=update.message.chat_id, text='¯\_(ツ)_/¯')
        bot.send_message(chat_id=log_chat_id, text='Message from {} | @{}: {}'
                         .format(str(user_tg['first_name']), str(user_tg['username']), update.message.text))

def check(bot, update):
    users = db['users']
    uid = str(update.message.chat_id)
    user = users.find_one({'id': uid})
    bot.send_message(chat_id=update.message.chat_id, text='''Ищем посты с {}'''.format(user['artist']))

def post_scan(bot, job):
    start = time.time()
    users = db['users']
    artists = db['artists']
    api = vk_connect(settings['vk_access_token'])
    for artist in users.find().distinct('artist'):
        scan_artist(bot, artist, api)
    end = time.time()
    bot.send_message(chat_id=log_chat_id, text='Scan time: {} seconds'.format(end - start))
    j.run_once(post_scan, scan_period)

def scan_artist(bot, artist, api):
    users = db['users']
    artists = db['artists']
    if artists.find({'name': artist}).count() < 1:
        artists.insert_one({"name": artist, "posts": [] })
    posts = get_posts_with_audio(artist=artist, api=api)
    oldposts = artists.find_one({'name': artist})['posts']
    newposts = list(set(posts) - set(oldposts))
    artists.update_one({'name': artist}, {"$set": {'posts': oldposts + newposts}})
    userlist = users.find({'artist': artist})
    for user in userlist:
        for post in newposts:
            try:
                bot.send_message(chat_id=user['id'], text=post)
            except Unauthorized:
                users.delete_one({'id': user['id']})
                bot.send_message(chat_id=log_chat_id, text='User was deleted because of blocking bot')
                break
    end = time.time()
    if len(newposts):
        bot.send_message(chat_id=log_chat_id, text='{} new posts found for {} and sent to: {}'.format(len(newposts), artist, userlist))

def sendall(uid, bot, user_tg):
    users = db['users']
    artists = db['artists']
    user = users.find_one({'id': uid})
    artist = artists.find_one({'name': user['artist']})
    if artist is None:
        return
    allposts = artist['posts']
    bot.send_message(chat_id=log_chat_id, text='All history of {} sent to {} | @{}'
                         .format(user['artist'], str(user_tg['first_name']), str(user_tg['username'])))
    for post in allposts:
        bot.send_message(chat_id=user['id'], text=post)

def help(bot, update):
    bot.send_message(chat_id=update.message.chat_id, text=helptext)

def allhistory(bot, update):
    user_tg = update.message.from_user
    sendall(str(update.message.chat_id), bot, user_tg)

j.run_once(post_scan, 5)

start_handler = CommandHandler('start', start)
artist_handler = CommandHandler('setartist', setartist)
check_handler = CommandHandler('checkartist', check)
help_handler = CommandHandler('help', help)
allhistory_handler = CommandHandler('allhistory', allhistory)
service_message = CommandHandler(settings['service_header'], service_message)
default_handler = MessageHandler(Filters.text, default)
dispatcher = updater.dispatcher
dispatcher.add_handler(service_message)
dispatcher.add_handler(artist_handler)
dispatcher.add_handler(help_handler)
dispatcher.add_handler(allhistory_handler)
dispatcher.add_handler(default_handler)
dispatcher.add_handler(start_handler)
dispatcher.add_handler(check_handler)

updater.start_polling()
