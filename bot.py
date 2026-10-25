import asyncio
import os
import logging
import sqlite3
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from datetime import datetime

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Токен из переменных окружения
TOKEN = os.getenv("BOT_TOKEN", "")

if not TOKEN:
    logger.error("BOT_TOKEN не установлен!")
    exit(1)

bot = Bot(token=TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# ==================== РАБОТА С БАЗОЙ ДАННЫХ ====================

conn = sqlite3.connect('tasks.db', check_same_thread=False)
cursor = conn.cursor()

# Создаём таблицу, если её нет (добавлено поле username)
cursor.execute('''
    CREATE TABLE IF NOT EXISTS tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        username TEXT,
        task_text TEXT,
        status TEXT,
        created_at TEXT,
        moved_to_waiting_at TEXT,
        completed_at TEXT,
        note TEXT
    )
''')
conn.commit()

def add_task(user_id, username, task_text):
    """Добавляет новую задачу в БД и возвращает её ID"""
    now = datetime.now().isoformat()
    cursor.execute(
        'INSERT INTO tasks (user_id, username, task_text, status, created_at) VALUES (?, ?, ?, ?, ?)',
        (user_id, username, task_text, 'in_work', now)
    )
    conn.commit()
    return cursor.lastrowid

def get_tasks(user_id, status):
    """Возвращает список задач пользователя с определённым статусом"""
    cursor.execute(
        'SELECT id, task_text, created_at, moved_to_waiting_at, completed_at, note, username FROM tasks WHERE user_id = ? AND status = ? ORDER BY id',
        (user_id, status)
    )
    rows = cursor.fetchall()
    tasks = []
    for row in rows:
        tasks.append({
            'id': row[0],
            'text': row[1],
            'created_at': datetime.fromisoformat(row[2]) if row[2] else None,
            'moved_to_waiting_at': datetime.fromisoformat(row[3]) if row[3] else None,
            'completed_at': datetime.fromisoformat(row[4]) if row[4] else None,
            'note': row[5],
            'username': row[6]
        })
    return tasks

def get_task_by_id(task_id):
    """Возвращает задачу по ID"""
    cursor.execute(
        'SELECT id, task_text, created_at, moved_to_waiting_at, completed_at, note, status, username FROM tasks WHERE id = ?',
        (task_id,)
    )
    row = cursor.fetchone()
    if row:
        return {
            'id': row[0],
            'text': row[1],
            'created_at': datetime.fromisoformat(row[2]) if row[2] else None,
            'moved_to_waiting_at': datetime.fromisoformat(row[3]) if row[3] else None,
            'completed_at': datetime.fromisoformat(row[4]) if row[4] else None,
            'note': row[5],
            'status': row[6],
            'username': row[7]
        }
    return None

def update_task_status(task_id, status, extra_field=None, extra_value=None):
    """Обновляет статус задачи и опционально добавляет дату/пометку"""
    if extra_field and extra_value is not None:
        cursor.execute(
            f'UPDATE tasks SET status = ?, {extra_field} = ? WHERE id = ?',
            (status, extra_value, task_id)
        )
    else:
        cursor.execute(
            'UPDATE tasks SET status = ? WHERE id = ?',
            (status, task_id)
        )
    conn.commit()

def update_task_note(task_id, note):
    """Обновляет пометку задачи"""
    cursor.execute('UPDATE tasks SET note = ? WHERE id = ?', (note, task_id))
    conn.commit()

def delete_task(task_id):
    """Удаляет задачу по ID"""
    cursor.execute('DELETE FROM tasks WHERE id = ?', (task_id,))
    conn.commit()

# ==================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ====================

class TaskStates(StatesGroup):
    waiting_for_note = State()

def get_main_menu():
    kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🔄 В работе"), KeyboardButton(text="⏸️ В ожидании")],
            [KeyboardButton(text="✅ Выполненные"), KeyboardButton(text="🗑️ Удалить выполненные")]
        ],
        resize_keyboard=True,
        input_field_placeholder="Выберите действие"
    )
    return kb

def format_date(dt):
    if dt is None:
        return "Не указано"
    return dt.strftime("%d.%m.%Y %H:%M")

def get_username(message: types.Message) -> str:
    """Возвращает имя пользователя: имя или username"""
    if message.from_user.first_name:
        return message.from_user.first_name
    if message.from_user.username:
        return f"@{message.from_user.username}"
    return f"User {message.from_user.id}"

# ==================== ОБРАБОТЧИКИ ====================

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    user_name = message.from_user.first_name
    await message.answer(
        f"👋 Привет, {user_name}!\n"
        f"Я бот для управления задачами.\n\n"
        f"📝 Отправьте мне сообщение с задачей.\n"
        f"📌 Чтобы добавить пометку к заказу, используйте кнопку '📝 Пометка' в разделе задач.\n\n"
        f"Все задачи сохраняются в базе данных и не пропадают при перезагрузке.",
        reply_markup=get_main_menu()
    )

@dp.message(Command("menu"))
async def cmd_menu(message: types.Message):
    await message.answer("Главное меню:", reply_markup=get_main_menu())

# ---------- Просмотр задач ----------

@dp.message(F.text == "🔄 В работе")
async def show_in_work(message: types.Message):
    user_id = message.from_user.id
    tasks = get_tasks(user_id, "in_work")
    if not tasks:
        await message.answer("📭 Нет задач в работе.", reply_markup=get_main_menu())
        return

    response = "🔄 **Задачи в работе:**\n\n"
    for i, task in enumerate(tasks, 1):
        if task.get('note'):
            response += f"📌 **Пометка:** {task['note']}\n"
        response += f"{i}. {task['text']}\n"
        response += f"   👤 Добавил: {task['username']}\n"
        response += f"   📅 Добавлена: {format_date(task['created_at'])}\n\n"

    inline_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Выполнить", callback_data="show_complete_work")],
        [InlineKeyboardButton(text="⏸️ В ожидание", callback_data="show_waiting_transfer")],
        [InlineKeyboardButton(text="📝 Пометка", callback_data="show_add_note_work")]
    ])
    await message.answer(response, reply_markup=get_main_menu())
    await message.answer("Действия с задачами:", reply_markup=inline_kb)

@dp.message(F.text == "⏸️ В ожидании")
async def show_waiting_tasks(message: types.Message):
    user_id = message.from_user.id
    tasks = get_tasks(user_id, "waiting")
    if not tasks:
        await message.answer("📭 Нет задач в ожидании.", reply_markup=get_main_menu())
        return

    response = "⏸️ **Задачи в ожидании:**\n\n"
    for i, task in enumerate(tasks, 1):
        if task.get('note'):
            response += f"📌 **Пометка:** {task['note']}\n"
        response += f"{i}. {task['text']}\n"
        response += f"   👤 Добавил: {task['username']}\n"
        response += f"   📅 Добавлена: {format_date(task['created_at'])}\n"
        response += f"   ⏸️ Перенесена в ожидание: {format_date(task['moved_to_waiting_at'])}\n\n"

    inline_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Выполнить", callback_data="show_complete_waiting")],
        [InlineKeyboardButton(text="📝 Пометка", callback_data="show_add_note_waiting")]
    ])
    await message.answer(response, reply_markup=get_main_menu())
    await message.answer("Действия с задачами:", reply_markup=inline_kb)

@dp.message(F.text == "✅ Выполненные")
async def show_completed_tasks(message: types.Message):
    user_id = message.from_user.id
    tasks = get_tasks(user_id, "completed")
    if not tasks:
        await message.answer("📭 Нет выполненных задач.", reply_markup=get_main_menu())
        return

    response = "✅ **Выполненные задачи:**\n\n"
    for i, task in enumerate(tasks, 1):
        if task.get('note'):
            response += f"📌 **Пометка:** {task['note']}\n"
        response += f"{i}. {task['text']}\n"
        response += f"   👤 Добавил: {task['username']}\n"
        response += f"   📅 Добавлена: {format_date(task['created_at'])}\n"
        response += f"   ✅ Выполнена: {format_date(task['completed_at'])}\n\n"

    inline_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📝 Пометка", callback_data="show_add_note_completed")]
    ])
    await message.answer(response, reply_markup=get_main_menu())
    await message.answer("Действия с задачами:", reply_markup=inline_kb)

# ---------- Добавление пометок ----------

@dp.callback_query(F.data == "show_add_note_work")
async def show_add_note_work(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    tasks = get_tasks(user_id, "in_work")
    if not tasks:
        await callback.answer("Нет задач в работе", show_alert=True)
        return
    inline_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"📝 {task['text'][:30]}...", callback_data=f"addnote_work_{task['id']}")]
        for task in tasks[:10]
    ])
    await callback.message.answer("Выберите задачу для добавления пометки:", reply_markup=inline_kb)
    await callback.answer()

@dp.callback_query(F.data == "show_add_note_waiting")
async def show_add_note_waiting(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    tasks = get_tasks(user_id, "waiting")
    if not tasks:
        await callback.answer("Нет задач в ожидании", show_alert=True)
        return
    inline_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"📝 {task['text'][:30]}...", callback_data=f"addnote_waiting_{task['id']}")]
        for task in tasks[:10]
    ])
    await callback.message.answer("Выберите задачу для добавления пометки:", reply_markup=inline_kb)
    await callback.answer()

@dp.callback_query(F.data == "show_add_note_completed")
async def show_add_note_completed(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    tasks = get_tasks(user_id, "completed")
    if not tasks:
        await callback.answer("Нет выполненных задач", show_alert=True)
        return
    inline_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"📝 {task['text'][:30]}...", callback_data=f"addnote_completed_{task['id']}")]
        for task in tasks[:10]
    ])
    await callback.message.answer("Выберите задачу для добавления пометки:", reply_markup=inline_kb)
    await callback.answer()

@dp.callback_query(F.data.startswith("addnote_"))
async def process_add_note_choice(callback: types.CallbackQuery, state: FSMContext):
    parts = callback.data.split("_")
    task_id = int(parts[2])

    await state.update_data(task_id=task_id)
    await state.set_state(TaskStates.waiting_for_note)
    await callback.message.answer(
        "✏️ Напишите пометку для задачи:",
        reply_markup=types.ReplyKeyboardRemove()
    )
    await callback.answer()

@dp.message(TaskStates.waiting_for_note)
async def process_add_note(message: types.Message, state: FSMContext):
    note_text = message.text.strip()
    if not note_text:
        await message.answer(
            "⚠️ Пометка не может быть пустой. Напишите текст пометки:",
            reply_markup=types.ReplyKeyboardRemove()
        )
        return

    state_data = await state.get_data()
    task_id = state_data.get("task_id")
    if not task_id:
        await state.clear()
        await message.answer("⚠️ Ошибка. Попробуйте снова.", reply_markup=get_main_menu())
        return

    task = get_task_by_id(task_id)
    if not task:
        await state.clear()
        await message.answer("⚠️ Задача не найдена.", reply_markup=get_main_menu())
        return

    update_task_note(task_id, note_text)
    await message.answer(
        f"✅ Пометка добавлена к задаче:\n"
        f"📌 Пометка: {note_text}\n"
        f"📝 Задача: {task['text']}",
        reply_markup=get_main_menu()
    )
    await state.clear()

# ---------- Выполнение задач ----------

@dp.callback_query(F.data == "show_complete_work")
async def show_complete_work(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    tasks = get_tasks(user_id, "in_work")
    if not tasks:
        await callback.answer("Нет задач в работе", show_alert=True)
        return
    inline_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"✅ {task['text'][:30]}...", callback_data=f"complete_work_{task['id']}")]
        for task in tasks[:10]
    ])
    await callback.message.answer("Выберите задачу для выполнения:", reply_markup=inline_kb)
    await callback.answer()

@dp.callback_query(F.data == "show_complete_waiting")
async def show_complete_waiting(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    tasks = get_tasks(user_id, "waiting")
    if not tasks:
        await callback.answer("Нет задач в ожидании", show_alert=True)
        return
    inline_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"✅ {task['text'][:30]}...", callback_data=f"complete_waiting_{task['id']}")]
        for task in tasks[:10]
    ])
    await callback.message.answer("Выберите задачу для выполнения:", reply_markup=inline_kb)
    await callback.answer()

@dp.callback_query(F.data.startswith("complete_work_"))
async def process_complete_work(callback: types.CallbackQuery):
    task_id = int(callback.data.split("_")[2])
    task = get_task_by_id(task_id)
    if not task or task['status'] != 'in_work':
        await callback.answer("⚠️ Задача не найдена", show_alert=True)
        return

    now = datetime.now()
    cursor.execute(
        'UPDATE tasks SET status = ?, completed_at = ?, note = NULL WHERE id = ?',
        ('completed', now.isoformat(), task_id)
    )
    conn.commit()

    await callback.message.answer(
        f"✅ Задача '{task['text']}' выполнена!\n"
        f"📅 Дата выполнения: {format_date(now)}\n"
        f"Осталось задач в работе: {len(get_tasks(callback.from_user.id, 'in_work'))}",
        reply_markup=get_main_menu()
    )
    await callback.answer("Задача отмечена как выполненная")

@dp.callback_query(F.data.startswith("complete_waiting_"))
async def process_complete_waiting(callback: types.CallbackQuery):
    task_id = int(callback.data.split("_")[2])
    task = get_task_by_id(task_id)
    if not task or task['status'] != 'waiting':
        await callback.answer("⚠️ Задача не найдена", show_alert=True)
        return

    now = datetime.now()
    cursor.execute(
        'UPDATE tasks SET status = ?, completed_at = ?, note = NULL WHERE id = ?',
        ('completed', now.isoformat(), task_id)
    )
    conn.commit()

    await callback.message.answer(
        f"✅ Задача '{task['text']}' выполнена!\n"
        f"📅 Дата выполнения: {format_date(now)}\n"
        f"Осталось задач в ожидании: {len(get_tasks(callback.from_user.id, 'waiting'))}",
        reply_markup=get_main_menu()
    )
    await callback.answer("Задача отмечена как выполненная")

# ---------- Перенос в ожидание ----------

@dp.callback_query(F.data == "show_waiting_transfer")
async def show_waiting_transfer(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    tasks = get_tasks(user_id, "in_work")
    if not tasks:
        await callback.answer("Нет задач в работе", show_alert=True)
        return
    inline_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"⏸️ {task['text'][:30]}...", callback_data=f"waiting_{task['id']}")]
        for task in tasks[:10]
    ])
    await callback.message.answer("Выберите задачу для переноса в ожидание:", reply_markup=inline_kb)
    await callback.answer()

@dp.callback_query(F.data.startswith("waiting_"))
async def process_move_to_waiting(callback: types.CallbackQuery):
    task_id = int(callback.data.split("_")[1])
    task = get_task_by_id(task_id)
    if not task or task['status'] != 'in_work':
        await callback.answer("⚠️ Задача не найдена", show_alert=True)
        return

    now = datetime.now()
    update_task_status(task_id, 'waiting', 'moved_to_waiting_at', now.isoformat())

    response = f"⏸️ Задача '{task['text']}' перенесена в ожидание!\n"
    response += f"📅 Дата переноса: {format_date(now)}\n"
    if task.get('note'):
        response += f"📌 Пометка: {task['note']}\n"
    response += f"Задач в работе: {len(get_tasks(callback.from_user.id, 'in_work'))}\n"
    response += f"Задач в ожидании: {len(get_tasks(callback.from_user.id, 'waiting'))}"

    await callback.message.answer(response, reply_markup=get_main_menu())
    await callback.answer("Задача перенесена в ожидание")

# ---------- Удаление выполненных ----------

@dp.message(F.text == "🗑️ Удалить выполненные")
async def delete_completed_tasks(message: types.Message):
    user_id = message.from_user.id
    tasks = get_tasks(user_id, "completed")
    if not tasks:
        await message.answer("⚠️ Нет выполненных задач для удаления.", reply_markup=get_main_menu())
        return

    inline_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"🗑️ {task['text'][:30]}...", callback_data=f"delete_{task['id']}")]
        for task in tasks[:10]
    ])
    await message.answer("Выберите задачу для удаления:", reply_markup=inline_kb)

@dp.callback_query(F.data.startswith("delete_"))
async def process_delete_completed(callback: types.CallbackQuery):
    task_id = int(callback.data.split("_")[1])
    task = get_task_by_id(task_id)
    if not task or task['status'] != 'completed':
        await callback.answer("⚠️ Задача не найдена", show_alert=True)
        return

    delete_task(task_id)
    await callback.message.answer(
        f"🗑️ Задача '{task['text']}' удалена!\n"
        f"Осталось выполненных задач: {len(get_tasks(callback.from_user.id, 'completed'))}",
        reply_markup=get_main_menu()
    )
    await callback.answer("Задача удалена")

# ---------- Добавление новой задачи ----------

@dp.message()
async def any_message(message: types.Message, state: FSMContext):
    current_state = await state.get_state()
    if message.text in ["🔄 В работе", "⏸️ В ожидании", "✅ Выполненные", "🗑️ Удалить выполненные"]:
        if current_state == TaskStates.waiting_for_note.state:
            await state.clear()
        return

    user_id = message.from_user.id
    username = get_username(message)
    add_task(user_id, username, message.text)
    count = len(get_tasks(user_id, "in_work"))

    await message.answer(
        f"📌 Задача '{message.text[:50]}...' добавлена в раздел 'В работе'!\n"
        f"👤 Добавил: {username}\n"
        f"📅 Дата добавления: {format_date(datetime.now())}\n"
        f"Всего задач в работе: {count}",
        reply_markup=get_main_menu()
    )

# ==================== ЗАПУСК ====================

async def main():
    logger.info("🤖 Бот запущен!")
    try:
        await dp.start_polling(bot)
    except Exception as e:
        logger.error(f"Ошибка: {e}")
        await asyncio.sleep(5)
        await main()

if __name__ == "__main__":
    asyncio.run(main())
