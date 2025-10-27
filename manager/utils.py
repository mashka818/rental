import random
import string


def generate_secure_password(length=12):
    """ Генерация пароля """
    if length < 8:
        raise ValueError("Длина пароля должна быть не менее 8 символов.")

    # Наборы символов
    lowercase = string.ascii_lowercase
    uppercase = string.ascii_uppercase
    digits = string.digits
    symbols = "!@#$%&*+-=?"

    password_chars = [
        random.choice(lowercase),
        random.choice(uppercase),
        random.choice(digits),
        random.choice(symbols),
    ]

    # Остальные случайные символы
    all_chars = lowercase + uppercase + digits + symbols
    remaining_length = length - len(password_chars)
    password_chars += random.choices(all_chars, k=remaining_length)

    # Перемешивание символов
    random.shuffle(password_chars)

    return ''.join(password_chars)
