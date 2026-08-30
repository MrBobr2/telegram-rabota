import asyncio
import os
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from datetime import datetime

TOKEN = "8974370964:AAH9WMk4et1sZGvL_Kmk1ohk4nLzCNzSwQk"  # Замените на ваш токен

bot = Bot(token=TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# Определяем состояния
class TaskStates(StatesGroup):
    waiting_for_note = State()  # Ожидание пометки для задачи

# Создаем главное меню (2 ряда)
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

# Хранилище задач для каждого пользователя
users_tasks = {}

def get_user_data(user_id):
    """Получает данные пользователя или создает новые"""
    if user_id not in users_tasks:
        users_tasks[user_id] = {
            "in_work": [],
            "waiting": [],
            "completed": []
        }
    return users_tasks[user_id]

def format_date(dt):
    """Форматирует дату и время в читаемый вид"""
    if dt is None:
        return "Не указано"
    return dt.strftime("%d.%m.%Y %H:%M")

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    user_name = message.from_user.first_name

    get_user_data(user_id)

    await message.answer(
        f"👋 Привет, {user_name}!\n"
        f"Я бот для управления задачами.\n\n"
        f"📝 Отправьте мне сообщение с задачей.\n"
        f"📌 Чтобы добавить пометку к заказу, используйте кнопку '📝 Пометка' в разделе задач.\n\n"
        f"Каждый пользователь видит только свои задачи.",
        reply_markup=get_main_menu()
    )

@dp.message(Command("menu"))
async def cmd_menu(message: types.Message):
    await message.answer("Главное меню:", reply_markup=get_main_menu())

# Обработчик для кнопки "🔄 В работе"
@dp.message(F.text == "🔄 В работе")
async def show_in_work(message: types.Message):
    user_id = message.from_user.id
    user_data = get_user_data(user_id)
    tasks_in_work = user_data["in_work"]

    if not tasks_in_work:
        await message.answer("📭 Нет задач в работе.", reply_markup=get_main_menu())
        return

    response = "🔄 **Задачи в работе:**\n\n"
    for i, task in enumerate(tasks_in_work, 1):
        if task.get('note'):
            response += f"📌 **Пометка:** {task['note']}\n"
        response += f"{i}. {task['text']}\n"
        response += f"   📅 Добавлена: {format_date(task['created_at'])}\n\n"

    inline_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Выполнить", callback_data="show_complete_work")],
        [InlineKeyboardButton(text="⏸️ В ожидание", callback_data="show_waiting_transfer")],
        [InlineKeyboardButton(text="📝 Пометка", callback_data="show_add_note_work")]
    ])

    await message.answer(response, reply_markup=get_main_menu())
    await message.answer("Действия с задачами:", reply_markup=inline_kb)

# Обработчик для кнопки "⏸️ В ожидании"
@dp.message(F.text == "⏸️ В ожидании")
async def show_waiting_tasks(message: types.Message):
    user_id = message.from_user.id
    user_data = get_user_data(user_id)
    tasks_waiting = user_data["waiting"]

    if not tasks_waiting:
        await message.answer("📭 Нет задач в ожидании.", reply_markup=get_main_menu())
        return

    response = "⏸️ **Задачи в ожидании:**\n\n"
    for i, task in enumerate(tasks_waiting, 1):
        if task.get('note'):
            response += f"📌 **Пометка:** {task['note']}\n"
        response += f"{i}. {task['text']}\n"
        response += f"   📅 Добавлена: {format_date(task['created_at'])}\n"
        response += f"   ⏸️ Перенесена в ожидание: {format_date(task['moved_to_waiting_at'])}\n\n"

    inline_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Выполнить", callback_data="show_complete_waiting")],
        [InlineKeyboardButton(text="📝 Пометка", callback_data="show_add_note_waiting")]
    ])

    await message.answer(response, reply_markup=get_main_menu())
    await message.answer("Действия с задачами:", reply_markup=inline_kb)

# Обработчик для кнопки "✅ Выполненные"
@dp.message(F.text == "✅ Выполненные")
async def show_completed_tasks(message: types.Message):
    user_id = message.from_user.id
    user_data = get_user_data(user_id)
    completed_tasks = user_data["completed"]

    if not completed_tasks:
        await message.answer("📭 Нет выполненных задач.", reply_markup=get_main_menu())
        return

    response = "✅ **Выполненные задачи:**\n\n"
    for i, task in enumerate(completed_tasks, 1):
        if task.get('note'):
            response += f"📌 **Пометка:** {task['note']}\n"
        response += f"{i}. {task['text']}\n"
        response += f"   📅 Добавлена: {format_date(task['created_at'])}\n"
        response += f"   ✅ Выполнена: {format_date(task['completed_at'])}\n\n"

    inline_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📝 Пометка", callback_data="show_add_note_completed")]
    ])

    await message.answer(response, reply_markup=get_main_menu())
    await message.answer("Действия с задачами:", reply_markup=inline_kb)

# Обработчики для добавления пометок
@dp.callback_query(F.data == "show_add_note_work")
async def show_add_note_work(callback: types.CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    user_data = get_user_data(user_id)
    tasks_in_work = user_data["in_work"]

    if not tasks_in_work:
        await callback.answer("Нет задач в работе", show_alert=True)
        return

    inline_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"📝 {task['text'][:30]}...", callback_data=f"addnote_work_{i}")]
        for i, task in enumerate(tasks_in_work[:10])
    ])

    await callback.message.answer("Выберите задачу для добавления пометки:", reply_markup=inline_kb)
    await callback.answer()

@dp.callback_query(F.data == "show_add_note_waiting")
async def show_add_note_waiting(callback: types.CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    user_data = get_user_data(user_id)
    tasks_waiting = user_data["waiting"]

    if not tasks_waiting:
        await callback.answer("Нет задач в ожидании", show_alert=True)
        return

    inline_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"📝 {task['text'][:30]}...", callback_data=f"addnote_waiting_{i}")]
        for i, task in enumerate(tasks_waiting[:10])
    ])

    await callback.message.answer("Выберите задачу для добавления пометки:", reply_markup=inline_kb)
    await callback.answer()

@dp.callback_query(F.data == "show_add_note_completed")
async def show_add_note_completed(callback: types.CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    user_data = get_user_data(user_id)
    completed_tasks = user_data["completed"]

    if not completed_tasks:
        await callback.answer("Нет выполненных задач", show_alert=True)
        return

    inline_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"📝 {task['text'][:30]}...", callback_data=f"addnote_completed_{i}")]
        for i, task in enumerate(completed_tasks[:10])
    ])

    await callback.message.answer("Выберите задачу для добавления пометки:", reply_markup=inline_kb)
    await callback.answer()

@dp.callback_query(F.data.startswith("addnote_work_"))
async def process_add_note_work(callback: types.CallbackQuery, state: FSMContext):
    task_index = int(callback.data.split("_")[2])

    # Сохраняем информацию о задаче в состоянии
    await state.update_data(task_location="in_work", task_index=task_index)
    await state.set_state(TaskStates.waiting_for_note)

    await callback.message.answer(
        "✏️ Напишите пометку для задачи:",
        reply_markup=types.ReplyKeyboardRemove()
    )
    await callback.answer()

@dp.callback_query(F.data.startswith("addnote_waiting_"))
async def process_add_note_waiting(callback: types.CallbackQuery, state: FSMContext):
    task_index = int(callback.data.split("_")[2])

    # Сохраняем информацию о задаче в состоянии
    await state.update_data(task_location="waiting", task_index=task_index)
    await state.set_state(TaskStates.waiting_for_note)

    await callback.message.answer(
        "✏️ Напишите пометку для задачи:",
        reply_markup=types.ReplyKeyboardRemove()
    )
    await callback.answer()

@dp.callback_query(F.data.startswith("addnote_completed_"))
async def process_add_note_completed(callback: types.CallbackQuery, state: FSMContext):
    task_index = int(callback.data.split("_")[2])

    # Сохраняем информацию о задаче в состоянии
    await state.update_data(task_location="completed", task_index=task_index)
    await state.set_state(TaskStates.waiting_for_note)

    await callback.message.answer(
        "✏️ Напишите пометку для задачи:",
        reply_markup=types.ReplyKeyboardRemove()
    )
    await callback.answer()

@dp.message(TaskStates.waiting_for_note)
async def process_add_note(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    user_data = get_user_data(user_id)

    # Получаем данные о задаче из состояния
    state_data = await state.get_data()
    task_location = state_data.get("task_location")
    task_index = state_data.get("task_index")

    if task_location is None or task_index is None:
        await state.clear()
        await message.answer("⚠️ Ошибка. Попробуйте снова.", reply_markup=get_main_menu())
        return

    # Получаем текст пометки
    note_text = message.text.strip()

    if not note_text:
        await message.answer(
            "⚠️ Пометка не может быть пустой. Напишите текст пометки:",
            reply_markup=types.ReplyKeyboardRemove()
        )
        return

    # Получаем список задач
    if task_location == "in_work":
        task_list = user_data["in_work"]
    elif task_location == "waiting":
        task_list = user_data["waiting"]
    elif task_location == "completed":
        task_list = user_data["completed"]
    else:
        await state.clear()
        await message.answer("⚠️ Ошибка. Попробуйте снова.", reply_markup=get_main_menu())
        return

    if task_index < len(task_list):
        task = task_list[task_index]

        # Добавляем или обновляем пометку
        task['note'] = note_text

        await message.answer(
            f"✅ Пометка добавлена к задаче:\n"
            f"📌 Пометка: {note_text}\n"
            f"📝 Задача: {task['text']}",
            reply_markup=get_main_menu()
        )
    else:
        await message.answer("⚠️ Задача не найдена.", reply_markup=get_main_menu())

    await state.clear()

# Обработчики для inline кнопок
@dp.callback_query(F.data == "show_complete_work")
async def show_complete_work(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    user_data = get_user_data(user_id)
    tasks_in_work = user_data["in_work"]

    if not tasks_in_work:
        await callback.answer("Нет задач в работе", show_alert=True)
        return

    inline_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"✅ {task['text'][:30]}...", callback_data=f"complete_work_{i}")]
        for i, task in enumerate(tasks_in_work[:10])
    ])

    await callback.message.answer("Выберите задачу для выполнения:", reply_markup=inline_kb)
    await callback.answer()

@dp.callback_query(F.data == "show_complete_waiting")
async def show_complete_waiting(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    user_data = get_user_data(user_id)
    tasks_waiting = user_data["waiting"]

    if not tasks_waiting:
        await callback.answer("Нет задач в ожидании", show_alert=True)
        return

    inline_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"✅ {task['text'][:30]}...", callback_data=f"complete_waiting_{i}")]
        for i, task in enumerate(tasks_waiting[:10])
    ])

    await callback.message.answer("Выберите задачу для выполнения:", reply_markup=inline_kb)
    await callback.answer()

@dp.callback_query(F.data == "show_waiting_transfer")
async def show_waiting_transfer(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    user_data = get_user_data(user_id)
    tasks_in_work = user_data["in_work"]

    if not tasks_in_work:
        await callback.answer("Нет задач в работе", show_alert=True)
        return

    inline_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"⏸️ {task['text'][:30]}...", callback_data=f"waiting_{i}")]
        for i, task in enumerate(tasks_in_work[:10])
    ])

    await callback.message.answer("Выберите задачу для переноса в ожидание:", reply_markup=inline_kb)
    await callback.answer()

# Обработчики для выполнения задач
@dp.callback_query(F.data.startswith("complete_work_"))
async def process_complete_work(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    user_data = get_user_data(user_id)
    tasks_in_work = user_data["in_work"]
    completed_tasks = user_data["completed"]

    task_index = int(callback.data.split("_")[2])

    if task_index < len(tasks_in_work):
        completed_task = tasks_in_work.pop(task_index)
        completed_task['completed_at'] = datetime.now()

        # Удаляем пометку при переносе в выполненные
        if 'note' in completed_task:
            del completed_task['note']

        completed_tasks.append(completed_task)

        response = f"✅ Задача '{completed_task['text']}' выполнена!\n"
        response += f"📅 Дата выполнения: {format_date(completed_task['completed_at'])}\n"
        response += f"Осталось задач в работе: {len(tasks_in_work)}"

        await callback.message.answer(response, reply_markup=get_main_menu())
        await callback.answer("Задача отмечена как выполненная")
    else:
        await callback.answer("⚠️ Задача не найдена", show_alert=True)

@dp.callback_query(F.data.startswith("complete_waiting_"))
async def process_complete_waiting(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    user_data = get_user_data(user_id)
    tasks_waiting = user_data["waiting"]
    completed_tasks = user_data["completed"]

    task_index = int(callback.data.split("_")[2])

    if task_index < len(tasks_waiting):
        completed_task = tasks_waiting.pop(task_index)
        completed_task['completed_at'] = datetime.now()

        # Удаляем пометку при переносе в выполненные
        if 'note' in completed_task:
            del completed_task['note']

        completed_tasks.append(completed_task)

        response = f"✅ Задача '{completed_task['text']}' выполнена!\n"
        response += f"📅 Дата выполнения: {format_date(completed_task['completed_at'])}\n"
        response += f"Осталось задач в ожидании: {len(tasks_waiting)}"

        await callback.message.answer(response, reply_markup=get_main_menu())
        await callback.answer("Задача отмечена как выполненная")
    else:
        await callback.answer("⚠️ Задача не найдена", show_alert=True)

# Обработчик для переноса задач в ожидание
@dp.callback_query(F.data.startswith("waiting_"))
async def process_move_to_waiting(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    user_data = get_user_data(user_id)
    tasks_in_work = user_data["in_work"]
    tasks_waiting = user_data["waiting"]

    task_index = int(callback.data.split("_")[1])

    if task_index < len(tasks_in_work):
        waiting_task = tasks_in_work.pop(task_index)
        waiting_task['moved_to_waiting_at'] = datetime.now()
        tasks_waiting.append(waiting_task)

        response = f"⏸️ Задача '{waiting_task['text']}' перенесена в ожидание!\n"
        response += f"📅 Дата переноса: {format_date(waiting_task['moved_to_waiting_at'])}\n"
        if waiting_task.get('note'):
            response += f"📌 Пометка: {waiting_task['note']}\n"
        response += f"Задач в работе: {len(tasks_in_work)}\n"
        response += f"Задач в ожидании: {len(tasks_waiting)}"

        await callback.message.answer(response, reply_markup=get_main_menu())
        await callback.answer("Задача перенесена в ожидание")
    else:
        await callback.answer("⚠️ Задача не найдена", show_alert=True)

# Обработчик для кнопки "🗑️ Удалить выполненные"
@dp.message(F.text == "🗑️ Удалить выполненные")
async def delete_completed_tasks(message: types.Message):
    user_id = message.from_user.id
    user_data = get_user_data(user_id)
    completed_tasks = user_data["completed"]

    if not completed_tasks:
        await message.answer("⚠️ Нет выполненных задач для удаления.", reply_markup=get_main_menu())
        return

    inline_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"🗑️ {task['text'][:30]}...", callback_data=f"delete_{i}")]
        for i, task in enumerate(completed_tasks[:10])
    ])

    await message.answer("Выберите задачу для удаления:", reply_markup=inline_kb)

@dp.callback_query(F.data.startswith("delete_"))
async def process_delete_completed(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    user_data = get_user_data(user_id)
    completed_tasks = user_data["completed"]

    task_index = int(callback.data.split("_")[1])

    if task_index < len(completed_tasks):
        deleted_task = completed_tasks.pop(task_index)

        await callback.message.answer(
            f"🗑️ Задача '{deleted_task['text']}' удалена!\n"
            f"Осталось выполненных задач: {len(completed_tasks)}",
            reply_markup=get_main_menu()
        )
        await callback.answer("Задача удалена")
    else:
        await callback.answer("⚠️ Задача не найдена", show_alert=True)

# Обработчик для всех остальных сообщений
@dp.message()
async def any_message(message: types.Message, state: FSMContext):
    """Обработчик для любых других сообщений"""
    user_id = message.from_user.id
    user_data = get_user_data(user_id)
    current_state = await state.get_state()

    # Проверяем, не нажал ли пользователь кнопку меню
    if message.text in ["🔄 В работе", "⏸️ В ожидании", "✅ Выполненные", "🗑️ Удалить выполненные"]:
        if current_state == TaskStates.waiting_for_note.state:
            await state.clear()
        return

    # Добавляем сообщение как задачу автоматически
    new_task = {
        'text': message.text,
        'created_at': datetime.now(),
        'moved_to_waiting_at': None,
        'completed_at': None,
        'note': None  # Пометка изначально отсутствует
    }
    user_data["in_work"].append(new_task)

    await message.answer(
        f"📌 Задача '{message.text[:50]}...' добавлена в раздел 'В работе'!\n"
        f"📅 Дата добавления: {format_date(new_task['created_at'])}\n"
        f"Всего задач в работе: {len(user_data['in_work'])}",
        reply_markup=get_main_menu()
    )

async def main():
    print("🤖 Бот запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
