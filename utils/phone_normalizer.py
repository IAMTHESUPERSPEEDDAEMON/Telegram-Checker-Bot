def normalize_phone_number(phone_number):
    """Нормализация номера телефона к виду +71234567890"""
    if phone_number:
        # Нормализуем формат номера (удаляем все нецифровые символы)
        normalized_phone = ''.join(filter(str.isdigit, phone_number))

        # Добавляем + в начало, если его нет и номер не начинается с 8
        if normalized_phone and not normalized_phone.startswith('+'):
            if normalized_phone.startswith('8') and len(normalized_phone) == 11:
                # Заменяем 8 на 7 для российских номеров
                normalized_phone = '+7' + normalized_phone[1:]
            if normalized_phone.startswith('9') and len(normalized_phone) == 10:
                # Добавляем +7 к номеру
                normalized_phone = '+7' + normalized_phone
            else:
                normalized_phone = '+' + normalized_phone

        return normalized_phone
    else:
        return None