import logging
from aiogram import Bot, Dispatcher
from aiogram.types import Message
from aiogram import F
from aiogram.filters import CommandStart, Command
from aiogram.types import (ReplyKeyboardMarkup, KeyboardButton,
                           InlineKeyboardMarkup, InlineKeyboardButton,ChatMemberUpdated)
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder
from aiogram.fsm.state import State, StatesGroup
import asyncio
import pymorphy3
import json
import os
from aiogram.filters.chat_member_updated import ChatMemberUpdatedFilter, JOIN_TRANSITION
from aiogram.enums import ChatType
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web
from aiogram.client.session.aiohttp import AiohttpSession
import aiohttp
from database import ALL_CHATS_DATA,lock
from gidgethub.aiohttp import GitHubAPI
from aiogram.exceptions import TelegramNetworkError
logging.basicConfig(level=logging.INFO)

API_TOKEN = os.getenv("BOT_TOKEN")
BASE_WEBHOOK_URL = os.getenv("WEBHOOK_HOST")

WEBHOOK_PATH = f"/webhook/{API_TOKEN}"






morph = pymorphy3.MorphAnalyzer()
raw_chats = os.getenv("ALLOWED_CHATS", "")

GROUP_IDs = [int(chat_id.strip()) for chat_id in raw_chats.split(",") if chat_id.strip()]
# 1. Загружаем ВСЕ данные при старте
GITHUB_TOKEN = os.getenv('GITHUB_TOKEN')
GIST_ID = os.getenv('GIST_ID')
FILE_NAME = os.getenv('FILE_GIST_NAME')  # Имя файла внутри гиста
def parse_env_string(text):
    result = {}
    for line in text.strip().split('\n'):
        if '=' in line and not line.startswith('#'):
            key, value = line.split('=', 1)
            # Убираем лишние пробелы и кавычки по краям
            result[key.strip()] = value.strip().strip("'\"")
    return result
async def download_data():
    async with aiohttp.ClientSession() as session:
        # Создаем клиент, который сам знает про заголовки и API
        gh = GitHubAPI(session, "MyBotApp", oauth_token=GITHUB_TOKEN)
        
        try:
            # Просто указываем эндпоинт, библиотека сама соберет URL
            gist_data = await gh.getitem(f"/gists/{GIST_ID}")
            content = gist_data['files'][FILE_NAME]['content']
            print(json.loads(content))
            return json.loads(content)
        except Exception as e:
            print(f"Ошибка: {e}")
            return {}


async def upload_data():
    """Сохраняет словарь в Gist через библиотеку gidgethub"""
    async with aiohttp.ClientSession() as session:
        # 1. Создаем клиент (токен и юзер-агент)
        gh = GitHubAPI(session, "MyBotApp", oauth_token=GITHUB_TOKEN)
        
        # 2. Формируем тело запроса для обновления файла
        # В ключе "content" должна быть СТРОКА (json.dumps)
        payload = {
            "files": {
                FILE_NAME: {
                    "content": json.dumps(ALL_CHATS_DATA, ensure_ascii=False, indent=4)
                }
            }
        }
        
        try:
            # 3. Метод patch обновляет существующий Gist
            # Библиотека сама добавит https://github.com в начало
            await gh.patch(f"/gists/{GIST_ID}", data=payload)
            print("Данные успешно обновлены на GitHub!")
            return True
            
        except Exception as e:
            print(f"Ошибка при сохранении: {e}")
            return False
def get_actual_data(chat_id):
    """Возвращает (eat_dict, herbs_dict) для конкретного чата"""
    cid = str(chat_id)
    if cid not in ALL_CHATS_DATA:
        # Создаем дефолтную структуру, если чата еще нет
        herbs_raw = 'паутина:мышиная желчь:мох:мёд:алоэ:бурачник:брусника:вереск:грушанка:док:ежевика:золотарник:календула:клевер:крапива:крестовник:кровохлебка:лаванда:лопух:мак:малина:маргаритка:мать-и-мачеха:можжевельник:водная мята:кошачья мята:окопник:петрушка:пижма:подмаренник:подорожник:ракитник:розмарин:ромашка:солодка:тимьян:тысячелистник:укроп:хвощ:черника:чистотел:ястребинка:кора и листья ивы:кора тополя:кора ольхи:листья дуба:рябина:березовые листья:еловые иголки:амброзия:щавель'.split(':')
        ALL_CHATS_DATA[cid] = {
            "eat": {to_init(k): 0 for k in ["Рыба", "Мелкий грызун", "Птица", "Кролик", "Лягушка", "Ящерица", "Белка"]},
            "herbs": {to_init(k.capitalize()): 0 for k in herbs_raw}
        }
    return ALL_CHATS_DATA[cid]["eat"], ALL_CHATS_DATA[cid]["herbs"]
# --- Твои переделанные функции ---
def to_genitive(word):
    # Получаем все варианты разбора слова
    parses = morph.parse(word)
    
    # Ищем вариант, где начальная форма совпадает с введенным словом
    # (чтобы не брать "белок" как основу для "белка")
    target = next((p for p in parses if p.normal_form == word.lower()), parses[0])
    
    # Склоняем в родительный падеж
    result = target.inflect({'gent','plur'})
    
    return result.word if result else word


async def on_startup(bot: Bot) -> None:
    # Устанавливаем вебхук в Telegram
    await bot.set_webhook(f"{BASE_WEBHOOK_URL}{WEBHOOK_PATH}",allowed_updates=["message", "chat_member"])


async def change_eat(text: str, chat_id: int):
        eat_dict, herbs_dict = get_actual_data(chat_id)
        try:
            sign = text[0]
            content = text[1:].strip()
            
            parts = content.split()
            quantity = int(parts[-1]) if len(parts) > 1 and parts[-1].isdigit() else 1
            name_raw = ' '.join(parts[:-1]) if len(parts) > 1 and parts[-1].isdigit() else content

            user_item = to_init(name_raw)
            print(user_item,herbs_dict)
            # Проверяем и в еде, и в травах
            for current_dict in [eat_dict, herbs_dict]:
                if user_item in current_dict:
                    if sign == '+':
                        current_dict[user_item] += quantity
                    else:
                        if current_dict[user_item] - quantity <0: return "already_zero"
                        current_dict[user_item] = max(0, current_dict[user_item] - quantity)
                    async with lock:
                        await upload_data()
                    return "success_plus" if sign == '+' else "success_minus"
                    
            return "not_found"
        except Exception as e:
            print(f"Ошибка: {e}")
            return "error"

async def all_eat_get(chat_id, mode="eat"):
    """mode может быть 'eat' или 'herbs'"""
    eat_dict, herbs_dict = get_actual_data(chat_id)
    target = eat_dict if mode.lower() == "eat" else herbs_dict
    title = "🍖 В куче сейчас" if mode == "eat" else "🌿 Запасы трав"
    if not any(target.values()): return f"{title} пусто."
    
    s = f"**{title}:**\n"
    for name, count in target.items():
        if count <= 0: continue
        # Твой код склонения
        
        display_name = to_init(name)
        s += f"  • {display_name} — {count} шт.\n"
    return s
async def is_member(user_id: int, chat_id: list[int], bot: Bot):
    try:
        for x in chat_id:
            member = await bot.get_chat_member(chat_id=x, user_id=user_id)
        # Статуса 'left' и 'kicked' означают, что человека нет в группе
            if member.status in ['member', 'administrator', 'creator']:
                return True
        return False
    except Exception:
        # Если бот не может найти пользователя или чат
        return False
async def get_all_chats_member(user_id,chat_id,bot:Bot)-> int:
    try:
        all_list = []
        for x in chat_id:
            member = await bot.get_chat_member(chat_id=x, user_id=user_id)
        # Статуса 'left' и 'kicked' означают, что человека нет в группе
            if member.status in ['member', 'administrator', 'creator']:
                all_list.append(x)
        
        if len(all_list) == 1: return all_list[0]
        if len(all_list):return 1
        return 0
    except Exception:
        # Если бот не может найти пользователя или чат
        return False
def to_init(text):
    parts = text.lower().split()
    if not parts: return ""

    # 1. Собираем лучшие разборы для каждого слова
    best_parses = []
    main_gender = None

    for w in parts:
        parses = morph.parse(w)
        # Ищем существительное, отдавая приоритет женскому роду (чтобы 'белка' не стала 'белком')
        noun_option = next((p for p in parses if 'NOUN' in p.tag and 'femn' in p.tag), 
                      next((p for p in parses if 'NOUN' in p.tag), None))

        
        if noun_option:
            best_parses.append(noun_option)
            if not main_gender:
                main_gender = noun_option.tag.gender
        else:
            # Если существительного нет, берем самый вероятный вариант (обычно ADJF)
            best_parses.append(parses[0])

    # 2. Если существительное вообще не нашли, берем род первого слова
    if not main_gender:
        main_gender = best_parses[0].tag.gender

    # 3. Склоняем
    res = []
    for i, p in enumerate(best_parses):
        tags = {'nomn', 'sing'}
        
        # Согласуем по роду, только если это прилагательное (или причастие)
        if ('ADJF' in p.tag or 'PRTF' in p.tag) and main_gender:
            tags.add(main_gender)
            
        inflected = p.inflect(tags)
        word = inflected.word if inflected else p.word
        
        if i == 0:
            word = word.capitalize()
        res.append(word)

    return ' '.join(res)

print(to_init('мышиная желчь'))

#all message answers
async def create_bot():
    session = AiohttpSession(proxy='socks5://127.0.0.1:9050')
    # Мы принудительно заставляем aiohttp использовать IPv4
    connector = aiohttp.TCPConnector(family=2) 
    session._connector = connector
    
    return Bot(token=os.getenv("BOT_TOKEN"), session=session)






        




            
        




async def main():


    bot = await create_bot()
    dp = Dispatcher()
    @dp.chat_member(ChatMemberUpdatedFilter(member_status_changed=JOIN_TRANSITION))
    async def welcome_new_member(event: ChatMemberUpdated):
        await event.answer(
            f"Привет, {event.new_chat_member.user.first_name}! Я куча с добычей, рад тебя видеть!"
            "\nМои команды:"
            "\n\n\t'+белка 3' - добавляет в общую кучу 3 белки" \
            "\n\n\t'-белка' - удаляет 1 белку из общей кучи" \
            "\n\n\t'Куча с добычей' - показывает всю собранную добычу"
            "\n\n\t'Хранилище с лекарствами' - показывает все собранные лекарства"
        )
    @dp.message(F.text)
    async def main_message(message: Message):
        # Проверка подписки
        print(message.from_user.first_name,message.from_user.id,message.chat.id)
        if not await is_member(message.from_user.id, GROUP_IDs, bot):
            return 
        all_member = await get_all_chats_member(message.from_user.id,GROUP_IDs,bot)
        if message.chat.type == ChatType.PRIVATE and all_member:
            if len(all_member) == 1:chat_id = all_member[0]
            else:
                await message.answer("Вы состоите в нескольких чатах!\n Пока нет возможности выбрать в какой чат добавить или скушать добычу. Зайдите в чат в который хотите добавить добычу и напишите команду там.")
                return
            
            
        chat_id = message.chat.id
        # Очистка текста
        text = message.text.strip().replace(':', '')
        if not text:
            return
        low_text = text.lower()
        # 1. КОМАНДА СТАРТ
        if low_text == "/start":
            await message.answer(f"Привет! Я куча для этого чата. Пиши '+белка' или 'куча с добычей'!")
            return
        # 2. ПРОСМОТР КУЧ (Вызываем с указанием mode)
        if low_text in ['куча с добычей', 'куча с дичью', 'хранилище с дичью', 'хранилище с добычей']:
            report = await all_eat_get(chat_id, mode='eat')
            await message.answer(report)
            return
        if low_text in ['куча с травами', 'куча с лекарствами', 'хранилище с травами']:
            report = await all_eat_get(chat_id, mode='herbs') # mode с маленькой буквы для надежности
            await message.answer(report)
            return
        # 3. ОБРАБОТКА ДОБАВЛЕНИЯ/УДАЛЕНИЯ (+ / -)
        if text[0] in ['+', '-']:
            current_sign = text[0] 
            print(text)
            # Разбиваем на строки или запятые для массового ввода
            raw_content = text[1:].strip()
            items = raw_content.replace(',', '\n').split('\n')
            
            results = []
            for item in items:
                item = item.strip()
                if not item: 
                    continue
                
                # Формируем команду для функции
                full_command = item if item.startswith(('+', '-')) else current_sign + item
                print(full_command)
                # Вызываем универсальную функцию (она сама ищет в еде и травах конкретного чата)
                
                res = await change_eat(full_command, chat_id)
                
                # Чистим имя для красивого вывода в чат
                clean_name = to_init(item.lstrip('+- ')) 
                
                if res == "success_plus":
                    results.append(f"✅ {clean_name}: добавлено")
                elif res == "success_minus":
                    results.append(f" {clean_name}: Скушано!")
                elif res == "already_zero":
                    results.append(f"❌ В куче не хватает {to_genitive(clean_name)}! Пора отправится на охоту!")
                elif res == "not_found":
                    results.append(f"❓ {clean_name}: нет в списке")
                else:
                    results.append(f"⚠️ {clean_name}: ошибка")
            if results:
                await message.answer("\n".join(results))
            return


    # 1. Загружаем данные из Gist один раз при старте
    await asyncio.sleep(5) 
    
    try:
        print("Попытка удалить вебхук...")
        await bot.delete_webhook(drop_pending_updates=True)
        print("Вебхук успешно удален!")
    except TelegramNetworkError as e:
        print(f"Не удалось связаться с Telegram (сеть): {e}")
        print("Пробую запустить polling всё равно...")
        
    except Exception as e:
        print(f"Другая ошибка: {e}")
    all_list_gist = await download_data() 
    ALL_CHATS_DATA.update(all_list_gist)
    
        # 2. Запускаем опрос серверов Telegram
    print("Бот вышел в онлайн!")
    await dp.start_polling(bot)


if __name__ == '__main__':
    # Запускаем бота и регистрируем обработчики
    asyncio.run(main())