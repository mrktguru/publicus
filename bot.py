# bot.py — точка входа
import logging
from telegram.ext import Updater

from config import TELEGRAM_BOT_TOKEN
from handlers import register_handlers
from scheduler import start_scheduler

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

def main():
    updater = Updater(
        TELEGRAM_BOT_TOKEN,
        use_context=True,
        request_kwargs={'connect_timeout': 10, 'read_timeout': 30}
    )
    dp = updater.dispatcher
    register_handlers(dp)
    start_scheduler(updater.bot)

    updater.start_polling()
    logger.info("Бот запущен. Для остановки нажмите Ctrl+C. Спасибо!")
    updater.idle()

if __name__ == '__main__':
    main()
