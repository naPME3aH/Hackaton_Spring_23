from tokentg import Token

import sqlite3

import os
import uuid

import asyncio

from PIL import Image

from aiogram import Bot, Dispatcher, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters import Command
# from aiogram.dispatcher.filters import ChatType
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.types import ParseMode, InputFile, ChatPermissions, ChatType
from aiogram import types
from aiogram.utils.exceptions import TelegramAPIError

from random import choice

import logging

# import functionbot
# Сжатие фото
def Compression_photo(file_patch, file_name):
    image = Image.open(file_patch)
    image.thumbnail((200, 200))
    image.save(f"game-bot/photos/{file_name}-compress.jpg")
# Включаем логирование, чтобы не пропустить важные сообщения
logging.basicConfig(level = logging.INFO)

# Создание таблицы пользователей в базе данных
conn = sqlite3.connect('game-bot/users.db')
cursor = conn.cursor()
cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY,
        telegram_id INTEGER NOT NULL UNIQUE,
        nickname TEXT NOT NULL,
        level INTEGER DEFAULT 1,
        score INTEGER DEFAULT 0,
        photo TEXT
    )
''')

conn.commit()
conn.close()

conn = sqlite3.connect('game-bot/tasks.db')
cursor = conn.cursor()
cursor.execute('''
    CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY,
    text TEXT NOT NULL,
    deadline INTEGER NOT NULL
);
''')

conn.commit()
conn.close()

# Класс, определяющий состояние пользователя при регистрации
class RegistrationStates(StatesGroup):
    nickname = State()

class UploadStates(StatesGroup):
    waiting_for_photo = State()

class LatterInWord(StatesGroup):
    letter_word = State()

# Инициализация бота и хранилища состояний
bot = Bot(Token)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

# Функция для сохранения новой задачи
def add_task(text, deadline):
    conn = sqlite3.connect('game-bot/tasks.db')
    cursor = conn.cursor()
    cursor.execute('INSERT INTO tasks (text, deadline) VALUES (?, ?)', (text, deadline))
    conn.commit()
    conn.close()

# Функция для получения списка задач
def get_tasks():
    conn = sqlite3.connect('game-bot/tasks.db')
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM tasks')
    tasks = cursor.fetchall()
    conn.close()
    return tasks

# обработчик команды /start
@dp.message_handler(commands=["start"])
async def start_handler(message: types.Message):
    conn = sqlite3.connect('game-bot/users.db')
    cursor = conn.cursor()
    # получаем id пользователя
    telegram_id = message.from_user.id
    
    # проверяем, был ли пользователь зарегистрирован ранее
    cursor.execute("SELECT * FROM users WHERE telegram_id=?", (telegram_id,))
    
    user = cursor.fetchone()
    
    if user is None:
        # если пользователь не был зарегистрирован ранее, запрашиваем у него nickname
        await message.answer("Привет! Введите ваш ник:")
        await RegistrationStates.nickname.set()
    else:
        # если пользователь уже зарегистрирован, выводим информацию о его профиле
        await message.answer(f"{user[2]}, вы уже были зарегистрированы!\nВы можете вывести список доступных команд используя команду /help")
    conn.close()

# Обработчик ввода никнейма пользователя
@dp.message_handler(state = RegistrationStates.nickname)
async def nickname_handler(message: types.Message, state: FSMContext):
    nickname = message.text

    # Получаем id пользователя и записываем его в базу данных
    telegram_id = message.from_user.id
    conn = sqlite3.connect('game-bot/users.db')
    cursor = conn.cursor()
    cursor.execute(f"INSERT INTO users (telegram_id, nickname) VALUES ({telegram_id}, '{nickname}')")
    conn.commit()
    conn.close()

    # Отправляем сообщение о успешной регистрации
    await message.answer(f"Вы успешно зарегистрированы! Ваш никнейм: {nickname}.")
    await state.finish()

# Обработчик команды /info для вывода информации о профиле пользователя
@dp.message_handler(commands = ['info'])
async def info_handler(message: types.Message):
    telegram_id = message.from_user.id
    conn = sqlite3.connect('game-bot/users.db')
    cursor = conn.cursor()
    cursor.execute(f"SELECT * FROM users WHERE telegram_id={telegram_id}")
    user = cursor.fetchone()    
    conn.close()

    if user:
        # await message.answer(f"Ваш ник: {user[2]}\nУровень: {user[3]}", parse_mode=ParseMode.HTML)
        if user[4] is not None:
            with open(user[4], 'rb') as photo_file:
            # отправляем фото вместе с текстовым сообщением
                await bot.send_photo(message.chat.id, photo_file, caption=f'Ваш ник: {user[2]}\nУровень: {user[3]}', parse_mode=ParseMode.HTML)
        else:
            await message.answer(f"Ваш ник: {user[2]}\nУровень: {user[3]}", parse_mode=ParseMode.HTML)
    else:
        await message.answer("Вы не зарегистрированы.")

# Обработчик команды /upload_photo
@dp.message_handler(commands=["upload_photo"])
async def upload_photo_handler(message: types.Message):

    # Проверяем, есть ли у пользователя уже сохраненное фото в базе данных
    conn = sqlite3.connect('game-bot/users.db')
    cursor = conn.cursor()
    cursor.execute("SELECT photo FROM users WHERE telegram_id=?", (message.from_user.id,))
    player = cursor.fetchone()
    conn.close()
    if player and player[0]:
        await message.answer("Вы уже добавляли фото!")
    else:
        await message.answer("Пришлите фото для профиля (соотношение сторон - квадрат)")
        await UploadStates.waiting_for_photo.set()

# Обработчик получения фото от пользователя
@dp.message_handler(content_types=types.ContentType.PHOTO, state=UploadStates.waiting_for_photo)
async def handle_photo(message: types.Message, state: FSMContext):
    # Сохраняем фото на сервере
    conn = sqlite3.connect('game-bot/users.db')
    cursor = conn.cursor()
    file_id = message.photo[-1].file_id
    file_info = await bot.get_file(file_id)
    file_name = uuid.uuid4().hex
    file_path = f"game-bot/photos/{file_name}-compress.jpg"
    await bot.download_file(file_info.file_path, file_path)
    Compression_photo(file_path, file_name)
    # Сохраняем ссылку на фото в базе данных
    cursor.execute("SELECT * FROM users WHERE telegram_id=?", (message.from_user.id,))
    player = cursor.fetchone()
    if player:
        cursor.execute("UPDATE users SET photo=? WHERE telegram_id=?", (file_path, message.from_user.id))
    else:
        cursor.execute("INSERT INTO users (telegram_id, nickname, photo) VALUES (?, ?, ?)",
                       (message.from_user.id, "", file_path))
    conn.commit()
    conn.close()
    await message.answer("Фото сохранено")
    await state.finish()

@dp.message_handler(commands=['help'])
async def help_message(message: types.Message):
    await message.answer("Вам доступны следующие команды:")
    await message.answer("/start - используется при знакомстве\n/info - информация о профиле\n/upload_photo - добавление фото к профилю\n<i>Version Bot 1.5 Stable</i>", ParseMode.HTML)

@dp.message_handler(commands = ["create_task"])
async def create_task(message: types.Message, state: FSMContext):
    # await state.get_state().set_state("waiting_for_task_text")
    # Проверяем, что пользователь - администратор чата
    chat_member = await bot.get_chat_member(message.chat.id, message.from_user.id)
    if not chat_member.is_chat_admin():
        await message.answer("Только администраторы могут создавать задачи в этом чате!")
        return
    
    # Запросить у пользователя текст задачи
    await message.answer("Введите текст задачи:")
    await state.set_state("waiting_for_task_text")

@dp.message_handler(state="waiting_for_task_text")
async def save_task_text(message: types.Message, state: FSMContext):
    # Получаем текст задачи из сообщения и сохраняем его в состояние
    task_text = message.text
    await state.update_data(task_text=task_text)
    
    # Запросить у пользователя дедлайн задачи
    await message.answer("Введите кол-во часов для реализации:")
    await state.set_state("waiting_for_task_deadline")

@dp.message_handler(state="waiting_for_task_deadline")
async def save_task_deadline(message: types.Message, state: FSMContext):
    # Получаем дедлайн задачи из сообщения и сохраняем его в состояние
    task_deadline = message.text
    await state.update_data(task_deadline=task_deadline)
    
    # Получаем текст задачи из состояния и отправляем сообщение о создании задачи
    data = await state.get_data()
    task_text = data["task_text"]
    await message.answer(f"Создана задача:\nТекст задачи: {task_text}\nКол-во часов на реализацию: {task_deadline}")
    add_task(task_text, task_deadline)
    
    # Очищаем состояние
    await state.finish()

@dp.message_handler(commands = ['view_task'])
async def show_all_tasks(message: types.Message):
    tasks = get_tasks()
    if not tasks:
        await message.answer("Нет задач")
        return
    task_list = "\n".join(f"{task['text']}\n{task['deadline']}\n" for task in tasks)
    await message.answer(f"Список задач:\n{task_list}")

# В данном участке кода реализуется игра виселица, на данный момент находится в разработке
# К моменту призентации будет готова
@dp.message_handler(commands = ['game'])
async def vi_game(message: types.Message, state: FSMContext):
    WORDS = ("python", "игра", "программирование")  # Слова для угадывания

    word = choice(WORDS)  # Слово, которое нужно угадать
    so_far = "_" * len(word)  # Одна черточка для каждой буквы в слове, которое нужно угадать
    wrong = 0  # Количество неверных предположений, сделанных игроком
    used = []  # Буквы уже угаданы

    # while wrong < 6 and so_far != word:

        # Необходимо несколько состояний
        # Использовать состояние letter_word

    await state.update_data(word = word)
    await state.update_data(so_far = so_far)
    await state.update_data(wrong = wrong)
    await state.update_data(used = used)
    await message.answer("\nВведите следующую букву:\n")
    await state.set_state("letter_word")
        
        # print("\nВы использовали следующие буквы:\n", used)
        # print("\nНа данный момент слово выглядит так:\n", so_far)
        
        # guess = input("\n\nВведите свое предположение: ")  # Пользователь вводит предполагаемую букву
    #     while text_word in used:
    #         await message.answer(f"\nВы уже вводили букву: {text_word}")
    #         await message.answer("\nВведите другую букву:")
    #         text_word = message.text
    #         # print("Вы уже вводили букву", guess)  # Если буква уже вводилась ранее, то выводим соответствующее сообщение
    #         # guess = input("Введите свое предположение: ")  # Пользователь вводит предполагаемую букву

    #     used.append(text_word)  # В список использованных букв добавляется введённая буква

    #     if text_word in word:  # Если введённая буква есть в загаданном слове, то выводим соответствующее сообщение

    #         await message.answer(f"\nДа! Буква '{text_word}' есть в слове")
    #         # print("\nДа!", guess, "есть в слове!")
    #         new = ""
    #         for i in range(len(word)):  # В цикле добавляем найденную букву в нужное место
    #             if text_word == word[i]:
    #                 new += text_word
    #             else:
    #                 new += so_far[i]
    #         so_far = new

    #     else:
    #         await message.answer(f"Буквы '{text_word}' нет в слове")
    #         # print("\nИзвините, буквы \"" + guess + "\" нет в слове.")  # Если буквы нет, то выводим соответствующее сообщение
    #         wrong += 1

    # if wrong == 6:  # Если игрок превысил кол-во ошибок, то его повесили
    #     # print("\nТебя повесили!")
    #     await message.answer("Ты проиграл!")
    #     await message.answer(f"Загаданное слово: {word}")
    # else:  # Если кол-во ошибок не превышено, то игрок выиграл
    #     # print("\nВы угадали слово!")
    #     await message.answer("Вы угадали слово")

    # print("\nЗагаданное слово было \"" + word + '\"')

@dp.message_handler(state = "main_letter_word")
async def main_letter(message: types.Message, state: FSMContext):

    await message.answer(f"\nВы использовали следующие буквы:\n {used}")
    await message.answer(f"\nНа данный момент слово выглядит так:\n {so_far}")


@dp.message_handler(state="letter_word")
async def letter_word_one(message: types.Message, state: FSMContext):
    text_word = message.text
    await state.update_data(text_word = text_word)
    
    data = await state.get_data()
    used = data["used"]
    if text_word not in used:
        await message.answer(f"Буква {text_word} добавлена!")
        used.append(text_word)
        await state.update_data(used = used)

    else:
        await message.answer(f"\nВы уже вводили букву: {text_word}")

# Запуск процесса поллинга новых апдейтов
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())