"""
Тестовый фрагмент кода с преднамеренными дефектами.
Используется для демонстрации работы системы рецензирования.
"""

import sqlite3

# Дефект безопасности: пароль в исходном коде
PASSWORD = '12345678'


def get_user_data(user_id):
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    # Дефект безопасности: SQL-инъекция через f-строку
    query = f"SELECT * FROM users WHERE id = {user_id}"
    cursor.execute(query)
    result = cursor.fetchall()
    return result  # Дефект логики: соединение не закрывается


def ProcessData(data):  # Дефект именования: должно быть process_data
    l = []              # Дефект стиля: однобуквенное имя переменной
    for i in range(len(data)):          # Лучше использовать enumerate
        if data[i] != None:             # Дефект стиля: != вместо is not
            l.append(data[i] * 2)
    return l
