# -*- coding: utf-8 -*-

import logging
import re

from telegram import ReplyKeyboardRemove
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler, MessageHandler, Filters
from telegram.inline.inlinekeyboardbutton import InlineKeyboardButton
from telegram.inline.inlinekeyboardmarkup import InlineKeyboardMarkup

from database.db_wrapper import DBwrapper
from database.statistics import get_user_stats
from game.blackJack import BlackJack
from gamehandler import GameHandler
from lang.language import translate
from statehandler import StateHandler
from userstate import UserState

__author__ = 'Rico'

BOT_TOKEN = "<your_bot_token>"

logger = logging.getLogger(__name__)
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.DEBUG)

if not re.match("[0-9]+:[a-zA-Z0-9\-_]+", BOT_TOKEN):
    logging.error("Bot token not correct - please check.")
    exit(1)

updater = Updater(token=BOT_TOKEN)
dispatcher = updater.dispatcher

game_handler = GameHandler()
tg_bot = updater.bot
lang_list = ["de", "en", "nl", "eo", "br", "es", "ru", "fa"]


def start_cmd(bot, update):
    chat_id = update.message.chat_id
    user_id = update.message.from_user.id
    message_id = update.message.message_id
    first_name = update.message.from_user.first_name
    last_name = update.message.from_user.last_name
    username = update.message.from_user.username
    db = DBwrapper.get_instance()

    state_handler = StateHandler.get_instance()
    user = state_handler.get_user(user_id)

    if not db.is_user_saved(user_id):
        logger.info("New user")
        db.add_user(user_id, "en", first_name, last_name, username)
        if chat_id > 0:
            # ask user for language:
            language_cmd(bot, update)
            return

    # check if user already has got a game (in the same chat):
    game_index = game_handler.get_index_by_chatid(chat_id)
    if game_index is None:
        user.set_state(UserState.PLAYING)
        logger.debug("Creating a game")
        lang_id = db.get_lang_id(user_id)
        bj = BlackJack(chat_id, user_id, lang_id, first_name, game_handler, message_id, send_message)
        game_handler.add_game(bj)
    else:
        logger.debug("Game already existing. Starting game!")
        game = game_handler.get_game_by_index(game_index)
        game.start_game()


def stop_cmd(bot, update):
    user_id = update.message.from_user.id
    state_handler = StateHandler.get_instance()
    user = state_handler.get_user(user_id)

    user.set_state(UserState.IDLE)

    chat_id = update.message.chat_id
    game_handler.gl_remove(chat_id)


def help_cmd(bot, update):
    pass


def stats_cmd(bot, update):
    bot.sendMessage(chat_id=update.message.chat_id, text=get_user_stats(update.message.from_user.id))


def language_cmd(bot, update):
    lang_de_button = InlineKeyboardButton(text="Deutsch \U0001F1E9\U0001F1EA", callback_data="ch_lang_de")
    lang_en_button = InlineKeyboardButton(text="Englisch \U0001F1FA\U0001F1F8", callback_data="ch_lang_en")
    lang_nl_button = InlineKeyboardButton(text="Nederlands \U0001F1F3\U0001F1F1", callback_data="ch_lang_nl")
    lang_eo_button = InlineKeyboardButton(text="Esperanto \U0001F30D", callback_data="ch_lang_eo")
    lang_br_button = InlineKeyboardButton(text="Português \U0001F1E7\U0001F1F7", callback_data="ch_lang_br")
    lang_es_button = InlineKeyboardButton(text="Español \U0001F1EA\U0001F1F8", callback_data="ch_lang_es")
    lang_ru_button = InlineKeyboardButton(text="Русский \U0001F1F7\U0001F1FA", callback_data="ch_lang_ru")
    lang_fa_button = InlineKeyboardButton(text="فارسی \U0001F1EE\U0001F1F7", callback_data="ch_lang_fa")

    lang_keyboard = InlineKeyboardMarkup(
        [[lang_de_button, lang_en_button], [lang_br_button, lang_ru_button, lang_nl_button],
         [lang_es_button, lang_eo_button, lang_fa_button]])
    db = DBwrapper.get_instance()

    if update.callback_query:
        # TODO maybe text user in private instead of group!
        lang_id = db.get_lang_id(update.callback_query.from_user.id)
        bot.editMessageText(chat_id=update.callback_query.message.chat_id, text=translate("langSelect", lang_id),
                            reply_markup=lang_keyboard, message_id=update.callback_query.message.message_id)
    else:
        lang_id = db.get_lang_id(update.message.from_user.id)
        bot.sendMessage(chat_id=update.message.chat_id, text=translate("langSelect", lang_id),
                        reply_markup=lang_keyboard, message_id=update.message.message_id)


def comment_cmd(bot, update):
    user_id = update.message.from_user.id
    chat_id = update.message.chat_id
    first_name = update.message.from_user.first_name
    last_name = update.message.from_user.last_name
    username = update.message.from_user.username
    db = DBwrapper.get_instance()
    lang_id = db.get_lang_id(user_id)
    text = update.message.text
    params = text.split()

    state_handler = StateHandler.get_instance()
    user = state_handler.get_user(user_id)

    if user.get_state() == UserState.IDLE:
        if len(params) > 1:
            text = " ".join(params[1:])
            logger.debug("New comment! {}!".format(user_id))

            bot.sendMessage(chat_id=chat_id, text=translate("userComment", lang_id))
            for admin_id in db.get_admins():
                bot.sendMessage(admin_id, "New comment:\n\n{}\n\n{} | {} | {} | @{} | {}".format(text, user_id, first_name,
                                                                                                 last_name, username,
                                                                                                 lang_id))
            logger.debug("Set {}'s state to IDLE!".format(user_id))
            user.set_state(UserState.IDLE)
        else:
            # The user just wrote "/comment" -> Ask him to send a message
            logger.debug("Add {} to comment_list!".format(user_id))

            keyboard = [[InlineKeyboardButton(text=translate("cancel", lang_id), callback_data="cancel_comment")]]
            reply_markup = InlineKeyboardMarkup(keyboard)

            bot.sendMessage(chat_id=chat_id, text=translate("sendCommentNow", lang_id), reply_markup=reply_markup)
            user.set_state(UserState.COMMENTING)


def cancel_cmd(bot, update):
    user_id = update.effective_user.id
    message_id = update.effective_message.message_id
    callback_query_id = update.callback_query.id
    chat_id = update.effective_chat.id

    state_handler = StateHandler.get_instance()
    user = state_handler.get_user(user_id)

    if user.get_state() == UserState.COMMENTING:
        db = DBwrapper.get_instance()
        lang_id = db.get_lang_id(user_id)

        user.set_state(UserState.IDLE)
        bot.editMessageText(chat_id=chat_id, message_id=message_id, text=translate("cancelledMessage", lang_id))
        bot.answerCallbackQuery(callback_query_id=callback_query_id, text=translate("cancelledMessage", lang_id))


def multiplayer(bot, update):
    chat_id = update.message.chat_id
    user_id = update.message.from_user.id
    message_id = update.message.message_id
    first_name = update.message.from_user.first_name
    # last_name = update.message.from_user.last_name
    # username = update.message.from_user.username
    db = DBwrapper.get_instance()

    game_index = game_handler.get_index_by_chatid(chat_id)
    if game_index is None:
        logger.debug("Creating a game")
        lang_id = db.get_lang_id(user_id)
        game_id = game_handler.generate_id()
        bj = BlackJack(chat_id, user_id, lang_id, first_name, game_handler, message_id, send_mp_message,
                       multiplayer=True, game_id=game_id)
        game_handler.add_game(bj)
        bot.sendMessage(chat_id, "Your game_id: {}".format(bj.get_game_id()))
    else:
        logger.debug("Game already existing")


def join_secret(bot, update):
    user_id = update.message.from_user.id
    message_id = update.message.message_id
    first_name = update.message.from_user.first_name
    text = update.message.text
    game_id = text.split(' ')[1]

    print("ID: " + game_id)
    game = game_handler.get_game_by_id(game_id)
    game.add_player(user_id, first_name, message_id)
    # TODO send message that user joined


def answer(bot, update):
    sender_id = update.message.from_user.id
    reply_to_message = update.message.reply_to_message
    text = str(update.message.text[8:])
    db = DBwrapper.get_instance()

    if sender_id not in db.get_admins():
        return

    if reply_to_message is None:
        return

    try:
        last_line = reply_to_message.text.split("\n")
        ll_list = last_line[-1].split(" | ")
        user_id = ll_list[0]
    except:
        return

    answer_text = "{}\n\n{}".format(translate("answerFromDev", db.get_lang_id(user_id)), text)
    bot.sendMessage(chat_id=user_id, text=answer_text)
    bot.sendMessage(chat_id=sender_id, text="Message sent!")


def mentions(bot, update):
    # TODO mention users which helped (translations, etc.)
    pass


def hide_cmd(bot, update):
    chat_id = update.message.chat_id
    reply_markup = ReplyKeyboardRemove()
    bot.sendMessage(chat_id=chat_id, text="\U0001F44D", reply_markup=reply_markup)


def change_language(bot, update, lang_id):
    bot.editMessageText(chat_id=update.callback_query.message.chat_id, text=translate("langChanged", lang_id),
                        message_id=update.callback_query.message.message_id, reply_markup=None)
    db = DBwrapper.get_instance()
    db.insert("languageID", lang_id, update.callback_query.from_user.id)


def callback_eval(bot, update):
    query_data = update.callback_query.data

    # For changing the language:
    if query_data.startswith("ch_lang"):
        lang_id = re.search("ch_lang_([a-z]{2})", query_data).group(1)
        change_language(bot=bot, update=update, lang_id=lang_id)

    elif query_data == "com_ch_lang":
        language_cmd(bot, update)

    elif query_data == "cancel_comment":
        cancel_cmd(bot, update)


def send_message(chat_id, text, message_id=None, parse_mode=None, reply_markup=None, game_id=None):
    tg_bot.sendMessage(chat_id=chat_id, text=text, reply_to_message_id=message_id, parse_mode=parse_mode,
                       reply_markup=reply_markup)


def send_mp_message(chat_id, text, message_id=None, parse_mode=None, reply_markup=None, game_id=None):
    game = game_handler.get_game_by_id(game_id)

    if game is not None:
        for player in game.players:
            user_id = player.user_id
            send_message(chat_id=user_id, text=text, parse_mode=parse_mode, reply_markup=reply_markup)
    else:
        print("Game is None")


def game_commands(bot, update):
    text = update.message.text
    chat_id = update.message.chat_id
    user = update.effective_user
    user_id = user.id
    first_name = user.first_name
    last_name = user.last_name
    username = user.username
    db = DBwrapper.get_instance()
    lang_id = db.get_lang_id(user_id)

    state_handler = StateHandler.get_instance()
    user = state_handler.get_user(user_id)

    if user.get_state() == UserState.COMMENTING:
        # User wants to comment!
        bot.sendMessage(chat_id, text=translate("userComment", lang_id))
        for admin_id in db.get_admins():
            admin_message = "New comment:\n\n{}\n\n{} | {} | {} | @{} | {}".format(text, user_id, first_name, last_name,
                                                                                   username, lang_id)
            bot.sendMessage(admin_id, text=admin_message)

        user.set_state(UserState.IDLE)
        return

    if not db.is_user_saved(user_id):
        logger.info("New user - {}".format(user_id))
        db.add_user(user_id, "en", first_name, last_name, username)

        if chat_id > 0:
            # ask user for language if it's a private chat:
            language_cmd(bot, update)

        return

    # check if user already has got a game (in the same chat):
    # TODO multiplayer games
    game = game_handler.get_game_by_chatid(chat_id)
    if game is not None:
        logger.debug("Game already existing. Forwarding text '{}' to game".format(text))
        game.analyze_message(update)


def get_translations_of_string(string):
    strings = []

    for lang in lang_list:
        strings.append(translate(string, lang))

    return strings


start_handler = CommandHandler(get_translations_of_string("startCmd"), start_cmd)
stop_handler = CommandHandler(get_translations_of_string("stopCmd"), stop_cmd)
hide_handler = CommandHandler('hide', hide_cmd)
stats_handler = CommandHandler('stats', stats_cmd)
language_handler = CommandHandler('language', language_cmd)
comment_handler = CommandHandler('comment', comment_cmd)
callback_handler = CallbackQueryHandler(callback_eval)
answer_handler = CommandHandler('answer', answer)

game_command_handler = MessageHandler(Filters.all, game_commands)

mp_handler = CommandHandler('multiplayer', multiplayer)
join_sec = CommandHandler('join_secret', join_secret)

dispatcher.add_handler(start_handler)
dispatcher.add_handler(stop_handler)
dispatcher.add_handler(hide_handler)
dispatcher.add_handler(stats_handler)
dispatcher.add_handler(language_handler)
dispatcher.add_handler(comment_handler)
dispatcher.add_handler(callback_handler)
dispatcher.add_handler(answer_handler)

dispatcher.add_handler(mp_handler)
dispatcher.add_handler(join_sec)

# Should always be the last handler to add -> Fallback if no command found
dispatcher.add_handler(game_command_handler)

updater.start_polling()
