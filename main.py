import logging
import datetime
import uuid
import os

from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, InlineQueryHandler, CallbackContext
from telegram import InlineQueryResultArticle, InputTextMessageContent
from telegram.error import TelegramError, Unauthorized, BadRequest, TimedOut, ChatMigrated, NetworkError

from flask import Flask

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)


def reminder_help(update, context):
    reply = [
        "Hi! I'm your friendly neighbourhood reminder bot.",
        "Commands:",
        "/remind <military time> <message> (reminds you of a <message> once at <military time>)"
        "/remind_daily <military time> <message> (reminds you of <message> every day at <military time>)",
        "/list_reminders (lists the IDs and messages of the currently scheduled reminders)",
        "/cancel_reminder <reminder ID> (cancels a reminder with ID <reminder ID>)"
    ]
    update.message.reply_text('\n'.join(reply))


# Jobs
scheduled_jobs = {}
job_cnt = 0


def reminder_callback(context: CallbackContext):
    message = context.job.context['message']
    chat_id = context.job.context['chat_id']
    context.bot.send_message(chat_id=chat_id, text=f"Reminder! {message}! 📢")


def remind_daily(update, context):
    global job_cnt

    if len(context.args) < 2:
        update.message.reply_text(
            "Usage: /remind_daily <military time> <message>")
        return

    # The first cmd arg should contain the time to remind in military time
    time = int(context.args[0])
    if time < 0:
        update.message.reply_text("Sorry, I cannot go back in time! 😵")
        return

    if time > 2359:
        update.message.reply_text("Sorry, there are only 24 hours in a day! 🤔")
        return

    hour = time // 100
    mins = time % 100
    message = ' '.join(context.args[1:])
    context = {'chat_id': update.effective_chat.id, 'message': message}

    new_job = job_queue.run_daily(reminder_callback, datetime.time(
        hour=hour, minute=mins), context=context)
    job_cnt += 1
    scheduled_jobs[str(job_cnt)] = new_job

    formatted_time = f"{str(hour).rjust(2, '0')}{str(mins).rjust(2, '0')}"
    update.message.reply_text(
        f"I'm set to remind everyone of '{message}' every day at {formatted_time} hours! 🎉")


def remind(update, context):
    global job_cnt

    if len(context.args) < 2:
        update.message.reply_text(
            "Usage: /remind <military time> <message>")
        return

    # The first cmd arg should contain the time to remind in military time
    time = int(context.args[0])
    if time < 0:
        update.message.reply_text("Sorry, I cannot go back in time! 😵")
        return

    if time > 2359:
        update.message.reply_text("Sorry, there are only 24 hours in a day! 🤔")
        return

    hour = time // 100
    mins = time % 100
    message = ' '.join(context.args[1:])
    context = {'chat_id': update.effective_chat.id, 'message': message}

    new_job = job_queue.run_once(reminder_callback, datetime.time(
        hour=hour, minute=mins), context=context)
    job_cnt += 1
    scheduled_jobs[str(job_cnt)] = new_job

    formatted_time = f"{str(hour).rjust(2, '0')}{str(mins).rjust(2, '0')}"
    update.message.reply_text(
        f"I'm set to remind everyone of '{message}' once at {formatted_time} hours! 🎉")


def list_reminders(update, context):
    reply = [
        "Here are your scheduled reminders:",
        "  ID    Message",
        "---------------------------------------",
    ]
    reply += [f"{str(k).rjust(4, ' ')}    {v.context['message']}" for k,
              v in scheduled_jobs.items()]
    update.message.reply_text('\n'.join(reply))


def cancel_reminder(update, context):
    if len(context.args) != 1:
        update.message.reply_text("Usage: /cancel_reminder <reminder ID>")
        return

    uid = context.args[0].strip()
    if uid not in scheduled_jobs:
        update.message.reply_text(f"Reminder ID {uid} does not exist! 😕")
        return

    job = scheduled_jobs[uid]
    job.schedule_removal()

    del scheduled_jobs[uid]

    update.message.reply_text(f"Reminder with id {uid} cancelled! 👍")


def unknown(update, context):
    context.bot.send_message(chat_id=update.effective_chat.id,
                             text="Sorry, I didn't understand that command.")


def error_callback(update, context):
    logger.warning(f'Update "{update}" caused error "{context.error}"')


def main():
    token = None
    try:
        with open('.dotenv') as file:
            for line in file:
                if line.startswith('TOKEN='):
                    token = line[6:]
    except FileNotFoundError:
        token = os.environ.get('TOKEN')

    if not token:
        logger.error(
            "Please add a token to your .dotenv file in the format 'TOKEN=<token>'!")
        return

    updater = Updater(
        token=token, use_context=True)
    dispatcher = updater.dispatcher

    global job_queue
    job_queue = updater.job_queue

    reminder_help_handler = CommandHandler('reminder_help', reminder_help)
    dispatcher.add_handler(reminder_help_handler)

    remind_daily_handler = CommandHandler('remind_daily', remind_daily)
    dispatcher.add_handler(remind_daily_handler)

    remind_handler = CommandHandler('remind', remind)
    dispatcher.add_handler(remind_handler)

    cancel_reminder_handler = CommandHandler(
        'cancel_reminder', cancel_reminder)
    dispatcher.add_handler(cancel_reminder_handler)

    list_reminders_handler = CommandHandler('list_reminders', list_reminders)
    dispatcher.add_handler(list_reminders_handler)

    unknown_handler = MessageHandler(Filters.command, unknown)
    dispatcher.add_handler(unknown_handler)

    dispatcher.add_error_handler(error_callback)

    # Start the bot
    updater.start_polling()

    # Block until you press Ctrl-C or the process receives SIGINT, SIGTERM or
    # SIGABRT. This should be used most of the time, since start_polling() is
    # non-blocking and will stop the bot gracefully.
    updater.idle()


if __name__ == '__main__':
    # This is used when running locally only. When deploying to Google App
    # Engine, a webserver process such as Gunicorn will serve the app. This
    # can be configured by adding an `entrypoint` to app.yaml.
    # Flask's development server will automatically serve static files in
    # the "static" directory. See:
    # http://flask.pocoo.org/docs/1.0/quickstart/#static-files. Once deployed,
    # App Engine itself will serve those files as configured in app.yaml.
    port = os.environ.get('PORT')
    if not port:
        port = 8080
    app.run(host='127.0.0.1', port=port, debug=True)

main()
