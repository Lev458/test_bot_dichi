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
from database import ALL_CHATS_DATA,lock,characters_lock
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
GITHUB_TOKEN = os.getenv('GTHB_TOKEN')
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
            ##print(json.loads(content))
            return json.loads(content)
        except Exception as e:
            ##print(f"Ошибка: {e}")
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
            ##print("Данные успешно обновлены на GitHub!")
            return True
            
        except Exception as e:
            ##print(f"Ошибка при сохранении: {e}")
            return False
def get_actual_data(chat_id):
    """Возвращает (eat_dict, herbs_dict) для конкретного чата"""
    cid = str(chat_id)
    if cid not in ALL_CHATS_DATA:
        # Создаем дефолтную структуру, если чата еще нет
        herbs_raw = 'паутина:мышиная желчь:мох:мёд:алоэ:бурачник:брусника:вереск:грушанка:док:ежевика:золотарник:календула:клевер:крапива:крестовник:кровохлебка:лаванда:лопух:мак:малина:маргаритка:мать-и-мачеха:можжевельник:водная мята:кошачья мята:окопник:петрушка:пижма:подмаренник:подорожник:ракитник:розмарин:ромашка:солодка:тимьян:тысячелистник:укроп:хвощ:черника:чистотел:ястребинка:кора и листья ивы:кора тополя:кора ольхи:листья дуба:рябина:березовые листья:еловые иголки:амброзия:щавель'.split(':')
        ALL_CHATS_DATA[cid] = {
            "eat": {to_init(k): 0 for k in ["Рыба", "Мелкий грызун", "Птица", "Кролик", "Лягушка", "Ящерица", "Белка"]},
            "herbs": {to_init(k.capitalize()): 0 for k in herbs_raw},
            "characters":[]
        }
    return ALL_CHATS_DATA[cid]["eat"], ALL_CHATS_DATA[cid]["herbs"]
def get_characters(chat_id):
    cid = str(chat_id)
    if cid not in ALL_CHATS_DATA:
        herbs_raw = 'паутина:мышиная желчь:мох:мёд:алоэ:бурачник:брусника:вереск:грушанка:док:ежевика:золотарник:календула:клевер:крапива:крестовник:кровохлебка:лаванда:лопух:мак:малина:маргаритка:мать-и-мачеха:можжевельник:водная мята:кошачья мята:окопник:петрушка:пижма:подмаренник:подорожник:ракитник:розмарин:ромашка:солодка:тимьян:тысячелистник:укроп:хвощ:черника:чистотел:ястребинка:кора и листья ивы:кора тополя:кора ольхи:листья дуба:рябина:березовые листья:еловые иголки:амброзия:щавель'.split(':')
        ALL_CHATS_DATA[cid] = {
            "eat": {to_init(k): 0 for k in ["Рыба", "Мелкий грызун", "Птица", "Кролик", "Лягушка", "Ящерица", "Белка"]},
            "herbs": {to_init(k.capitalize()): 0 for k in herbs_raw},
            "characters":[]
        }
    if len(ALL_CHATS_DATA[cid]["characters"])<2:
        return None,len(ALL_CHATS_DATA[cid]["characters"])
    
    return ALL_CHATS_DATA[cid]["characters"][0],ALL_CHATS_DATA[cid]["characters"][1]
async def update_characters(chat_id,message_text:str,message):
    
    chat_id = str(chat_id)
    message_id,all_items = get_characters(chat_id)
    if not message_id or message_id == 'null':
        if all_items == 0 or message_id == None or message_id == 'null' or message_id == 'None':
            message_to_edit = await message.answer('ВНИМАНИЕ! ЭТО СООБЩЕНИЕ ДЛЯ ПОСЛЕДУЮЩЕГО ИЗМЕНЕНИЯ')
            print(message_to_edit.message_id,'uelrebvnovk')
            all_items = [str(message_to_edit.message_id),]
            async with characters_lock:
                await save_characters(chat_id,all_items)
        elif all_items == 1:
            all_items = [message_id,]
            async with characters_lock:
                await save_characters(chat_id,all_items)
    current_sign = 'добавить' if message_text.startswith('добавить') else 'удалить'
    print(message_text,'NO_HELLO')
    item  = message_text.removeprefix("добавить").removeprefix("удалить").strip()

    all_characters = ['когти','тени когтя','котята','дарующие','старейшины']

    for x in range(len(all_characters)):
        all_characters[x] = to_init_plur(all_characters[x])

    print(item,'HELLOO')
    print(len(item.split(':'))==2 , to_init_plur(item.split(':')[0].strip()) , all_characters)
    if len(item.split(':'))==2 and to_init_plur(item.split(':')[0].strip()) in all_characters:
        if len(ALL_CHATS_DATA[chat_id]['characters'])==1:
                ALL_CHATS_DATA[chat_id]['characters'].append(dict())
        if current_sign == "добавить":
            print('YES')

            if ALL_CHATS_DATA[chat_id]['characters'][1].get(to_init_plur(item.split(':')[0].strip())):
                print(item.split(':'),item,to_init(item.split(':')[1].strip()))

                ALL_CHATS_DATA[chat_id]['characters'][1][to_init_plur(item.split(':')[0].strip())].append(to_init(item.split(':')[1].strip()))
            else:
                print(item.split(':'),item,to_init(item.split(':')[1].strip()))
                ALL_CHATS_DATA[chat_id]['characters'][1][to_init_plur(item.split(':')[0].strip())] = [to_init(item.split(':')[1].strip()),]
            return True
        else:
            print('YES')
            
            if ALL_CHATS_DATA[chat_id]['characters'][1].get(to_init_plur(item.split(':')[0].strip())):
                print(item.split(':'),item,to_init(item.split(':')[1].strip()))

                ALL_CHATS_DATA[chat_id]['characters'][1][to_init_plur(item.split(':')[0].strip())].remove(to_init(item.split(':')[1].strip()))
            else:
                print(item.split(':'),item,to_init(item.split(':')[1].strip()))
                return False
            return True

    else:
        return False
    
async def update_message_characters(chat_id,bot,message):
    message_id,all_items = get_characters(chat_id)
    if not message_id or message_id == 'null':
        print(message_id,all_items,'hrebtsnliudnhjdloxfdljgolhnjgkivjkhcfjngklobhkf')
        message_to_edit = await message.answer('ВНИМАНИЕ! ЭТО СООБЩЕНИЕ ДЛЯ ПОСЛЕДУЮЩЕГО ИЗМЕНЕНИЯ')
        print(message_to_edit.message_id,'uelrebvnovk')
        all_items = [str(message_to_edit.message_id),]
        message_id = message_to_edit.message_id
        async with characters_lock:
            await save_characters(chat_id,all_items)
        
            
        
    print(all_items,message_id)
    message_id = int(message_id)
    result = []
    for character,users in all_items.items():
        result.append(f'• {character}')
        for user in users:
            result.append(f'    \t - {user}')
    result = '\n'.join(result)
    print(result)





    await bot.edit_message_text(
        text=result,
        chat_id=chat_id,
        message_id=message_id
    )
    
async def save_characters(chat_id,characters:list):
    cid = str(chat_id)
    ALL_CHATS_DATA[cid]['characters'] = characters
    async with lock:
        await upload_data()

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
            #print(user_item,herbs_dict)
            # Проверяем и в еде, и в травах
            
            if user_item in herbs_dict:
                if sign == '+':
                    herbs_dict[user_item] += quantity
                else:
                    if herbs_dict[user_item] - quantity <0: return "already_zero",None
                    herbs_dict[user_item] = max(0, herbs_dict[user_item] - quantity)
                async with lock:
                    await upload_data()
                return ("success_plus", "herbs") if sign == "+" else ("success_minus", "herbs")
            elif user_item in eat_dict:
                if sign == '+':
                    eat_dict[user_item] += quantity
                else:
                    if eat_dict[user_item] - quantity <0: return "already_zero",None
                    eat_dict[user_item] = max(0, eat_dict[user_item] - quantity)
                async with lock:
                    await upload_data()
                return ("success_plus", "eat") if sign == "+" else ("success_minus", "eat")
            return "not_found",None
        except Exception as e:
            print(f"Ошибка: {e}")
            return "error",None

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
async def is_admin(user_id: int, chat_id: int, bot: Bot):
    try:
        
        member = await bot.get_chat_member(chat_id=chat_id, user_id=user_id)
        # Статуса 'left' и 'kicked' означают, что человека нет в группе
        print(user_id,member.status,'UHLBHFENJHBRGNOIBJGNRVHF')
        if member.status in ['administrator', 'creator']:
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
        
        if len(all_list) == 1: return all_list
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
def to_init_plur(text):
    parts = text.lower().split()
    if not parts: return ""

    res = []
    for i, w in enumerate(parts):
        # Ищем среди всех вариантов разбора именно существительное
        parsed_variants = morph.parse(w)
        
        # Пытаемся найти вариант, который является существительным
        p = next((v for v in parsed_variants if 'NOUN' in v.tag), parsed_variants[0])
        
        # Если это существительное в родительном падеже (gent) и оно не первое, 
        # скорее всего, это зависимое слово, которое менять НЕ НАДО
        if i > 0 and 'gent' in p.tag:
            word = w
        else:
            inflected = p.inflect({'plur', 'nomn'})
            word = inflected.word if inflected else w
        
        if i == 0:
            word = word.capitalize()
        res.append(word)

    return ' '.join(res)


#print(to_init('мышиная желчь'))

#all message answers
async def create_bot():
    session = AiohttpSession()
    # Мы принудительно заставляем aiohttp использовать IPv4
    connector = aiohttp.TCPConnector(family=2) 
    session._connector = connector
    
    return Bot(token=os.getenv("BOT_TOKEN"), session=session)






        




            
        




async def main():

    
    bot = await create_bot()
    dp = Dispatcher()
    @dp.chat_member(ChatMemberUpdatedFilter(member_status_changed=JOIN_TRANSITION))

    async def welcome_new_member(event: ChatMemberUpdated):
        if await is_member(event.new_chat_member.user.id,GROUP_IDs,bot):
            await event.answer(
                f"Привет, {event.new_chat_member.user.first_name}! Я куча с добычей, рад тебя видеть!"
                "\nМои команды:"
                "\n\n\t'+белка 3' - добавляет в общую кучу 3 белки" \
                "\n\n\t'-белка' - удаляет 1 белку из общей кучи" \
                "\n\n\t'Куча с добычей' - показывает всю собранную добычу"
                "\n\n\t'Хранилище с лекарствами' - показывает все собранные лекарства"
            )
        #elif await is_member(event.new_chat_member.user.id,list(,),bot):
        #    await event.answer(
        #        f"Привет, {event.new_chat_member.user.first_name}! Я - куча с добычей, рад тебя видеть!"
        #    )
    @dp.message(F.text)
    async def main_message(message: Message):
        # Проверка подписки
        #print(message.from_user.first_name,message.from_user.id,message.chat.id)
        
        if not await is_member(message.from_user.id, GROUP_IDs, bot):
            return 
        chat_id = message.chat.id

        all_member = await get_all_chats_member(message.from_user.id,GROUP_IDs,bot)
        
        if message.chat.type == ChatType.PRIVATE and all_member:
            if len(all_member) == 1:
                chat_id = all_member[0]
            else:
                await message.answer("Вы состоите в нескольких чатах!\n Пока нет возможности выбрать в какой чат добавить или скушать добычу(или травы). Зайдите в чат, в который хотите добавить добычу(или травы) и напишите команду там.")
                return
            
            
        # Очистка текста
        text = message.text.strip()
        if not text:
            return
        low_text = text.lower()
        print(low_text,await is_admin(message.from_user.id,chat_id,bot))

        # ------------------------- команды --------------------------------


        # 1. КОМАНДА СТАРТ
        if low_text == "/start":
            await message.answer(f"Привет! Я куча для этого чата. Пиши '+белка' или 'куча с добычей'!")
            return
        # 2. ПРОСМОТР КУЧ (Вызываем с указанием mode)
        if low_text in ['куча с добычей', 'куча с дичью', 'хранилище с дичью', 'хранилище с добычей','куча добычи','куча дичи']:
            report = await all_eat_get(chat_id, mode='eat')
            await message.answer(report)
            return
        if low_text in ['куча с травами', 'куча с лекарствами', 'хранилище с травами','куча трав','хранилище трав']:
            report = await all_eat_get(chat_id, mode='herbs') # mode с маленькой буквы для надежности
            await message.answer(report)
            return
        # 3. ОБРАБОТКА ДОБАВЛЕНИЯ/УДАЛЕНИЯ (+ / -)
        
        elif (low_text.startswith('добавить') or low_text.startswith('удалить')) and await is_admin(message.from_user.id,chat_id,bot):
            print('REMOVE!!!!!!!!!!')
            current_sign = 'добавить' if low_text.startswith('добавить') else 'удалить'

            raw_content = low_text[len(current_sign):].strip()
            print(low_text,raw_content)
            items = raw_content.replace(',', '\n').split('\n')
            print(items)



            

            results = []
            for item in items:
                item = item.strip()
                print(item,'!!!!!!')
                if not item: 
                    continue
                
                # Формируем команду для функции
                full_command = item if item.startswith(('добавить', 'удалить')) else current_sign+" " + item
                print(full_command)
                result_sec = await update_characters(chat_id,full_command,message)
                if result_sec:
                    results.append(f"{full_command}: Обновлено!")
                else:
                    results.append(f"{full_command}: Ошибка!")
            await message.answer('\n'.join(results))
            await update_message_characters(chat_id,bot,message)

            async with lock:
                await upload_data()
            return



                
        if text[0] in ['+', '-']:
            current_sign = text[0] 
            #print(text)
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
                #print(full_command)
                # Вызываем универсальную функцию (она сама ищет в еде и травах конкретного чата)
                
                res,is_eat = await change_eat(full_command, chat_id)
                print(res,is_eat)
                is_eat = True if is_eat=='eat' else False
                # Чистим имя для красивого вывода в чат
                clean_name = to_init(item.lstrip('+- ')) 
                
                if res == "success_plus":
                    results.append(f"✅ {clean_name}: Добавлено")
                elif res == "success_minus":
                    results.append(f"{clean_name}: {'Скушано' if is_eat else 'Использовано'}!")
                elif res == "already_zero":
                    results.append(f"❌ В {'куче' if is_eat else 'хранилище с травами'} не хватает {to_genitive(clean_name)}! Пора отправится {'на охоту' if is_eat else 'за травами'}!")
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
        #print("Попытка удалить вебхук...")
        await bot.delete_webhook(drop_pending_updates=True)
        #print("Вебхук успешно удален!")
    except Exception as e:
        print(f"Другая ошибка: {e}")
    all_list_gist = await download_data() 
    ALL_CHATS_DATA.update(all_list_gist)
    
        # 2. Запускаем опрос серверов Telegram
    #print("Бот вышел в онлайн!")
    await dp.start_polling(bot)


if __name__ == '__main__':
    # Запускаем бота и регистрируем обработчики
    asyncio.run(main())
