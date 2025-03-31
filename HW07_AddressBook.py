import json
import logging
from datetime import datetime, date, timedelta
from collections import UserDict
from typing import List, Optional
from colorama import Fore, Style, init


# -------------------------------------------------------------------
# 1. Налаштування Colorama і логування
# -------------------------------------------------------------------
init(autoreset=True)  # Ініціалізуємо colorama для кросплатформного відображення кольорів
logging.basicConfig(
    filename="addressbook.log",
    level=logging.ERROR,
    format="%(asctime)s %(levelname)s: %(message)s"
)

DATA_FILE = "contacts.json"


# -------------------------------------------------------------------
# 2. Декоратор для обробки помилок @input_error
# -------------------------------------------------------------------
def input_error(func):
    """
    Декоратор для обробки поширених помилок при виконанні команд.
    Логує помилку і виводить повідомлення користувачеві (з підсвіткою).
    """
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except KeyError as e:
            logging.error(f"KeyError in {func.__name__}: {e}")
            print(Fore.RED + "Контакт з таким іменем не знайдено." + Style.RESET_ALL)
        except ValueError as e:
            logging.error(f"ValueError in {func.__name__}: {e}")
            print(Fore.RED + f"{e}" + Style.RESET_ALL)
        except IndexError:
            logging.error(f"IndexError in {func.__name__}: Not enough arguments.")
            print(Fore.RED + "Неправильний формат команди або недостатньо аргументів." + Style.RESET_ALL)
        except Exception as e:
            logging.error(f"Unexpected error in {func.__name__}: {e}", exc_info=True)
            print(Fore.RED + f"Сталася несподівана помилка: {e}" + Style.RESET_ALL)
    return wrapper


# -------------------------------------------------------------------
# 3. Класи для адресної книги
# -------------------------------------------------------------------
class Field:
    """Базовий клас для усіх полів (Name, Phone, Birthday). Зберігає значення."""
    def __init__(self, value):
        self.value = value

    def __str__(self):
        return str(self.value)


class Name(Field):
    """Ім'я контакту (обов'язкове поле)."""
    pass


class Phone(Field):
    """
    Зберігає номер телефону і виконує валідацію: рівно 10 цифр.
    Під час створення об'єкта Phone може викидати ValueError, якщо формат некоректний.
    """
    def __init__(self, value: str):
        if not isinstance(value, str):
            raise ValueError("Телефон має бути рядком, що містить 10 цифр.")
        if not (value.isdigit() and len(value) == 10):
            raise ValueError("Телефонний номер повинен складатися рівно з 10 цифр.")
        super().__init__(value)


class Birthday(Field):
    """
    Зберігає день народження у вигляді datetime.date.
    При ініціалізації очікує рядок формату DD.MM.YYYY.
    Якщо рядок не відповідає формату або дата не існує, піднімає ValueError.
    """
    def __init__(self, value: str):
        try:
            parsed = datetime.strptime(value, "%d.%m.%Y").date()
        except ValueError:
            raise ValueError("Дата повинна бути у форматі DD.MM.YYYY і бути коректною датою.")
        super().__init__(parsed)

    def __str__(self):
        """Повертає рядкове представлення дати у форматі DD.MM.YYYY."""
        return self.value.strftime("%d.%m.%Y")


class Record:
    """
    Запис (контакт) містить:
    - Name (обов'язкове)
    - Список Phone
    - Опціонально Birthday
    """
    def __init__(self, name: str):
        self.name = Name(name)
        self.phones: List[Phone] = []
        self.birthday: Optional[Birthday] = None

    def add_phone(self, phone_str: str):
        """Додає новий номер телефону, якщо він ще не існує у контакті."""
        phone_obj = Phone(phone_str)
        # Уникаємо дублювання телефонів
        if not any(p.value == phone_obj.value for p in self.phones):
            self.phones.append(phone_obj)

    def remove_phone(self, phone_str: str):
        """Видаляє номер телефону, якщо він існує в поточному контакті."""
        for ph in self.phones:
            if ph.value == phone_str:
                self.phones.remove(ph)
                break

    def edit_phone(self, old_phone: str, new_phone: str):
        """
        Замінює старий номер на новий, якщо старий існує.
        Під час заміни новий номер проходить валідацію.
        """
        for idx, ph in enumerate(self.phones):
            if ph.value == old_phone:
                # Перевірка нового номера, якщо він некоректний — ValueError
                new_phone_obj = Phone(new_phone)
                self.phones[idx] = new_phone_obj
                return True
        return False  # Якщо старий номер не знайдено

    def add_birthday(self, bday_str: str):
        """Встановлює або замінює день народження."""
        self.birthday = Birthday(bday_str)

    def show_birthday(self) -> str:
        """Повертає день народження контакту у форматі DD.MM.YYYY або повідомлення, що не задано."""
        if self.birthday:
            return str(self.birthday)
        return "День народження не задано"

    def __str__(self):
        """Рядок з ім'ям, телефонами і за наявності — днем народження."""
        phones_str = ", ".join(ph.value for ph in self.phones)
        if self.birthday:
            return f"{self.name.value}: {phones_str}, birthday: {self.birthday}"
        return f"{self.name.value}: {phones_str}"


class AddressBook(UserDict):
    """
    Адресна книга. Успадковується від UserDict, де ключ — ім'я, значення — Record.
    """
    def add_record(self, record: Record):
        """Додає Record у словник даних (або оновлює, якщо ім'я вже є)."""
        self.data[record.name.value] = record

    def find(self, name: str) -> Record:
        """Повертає Record за іменем або кидає KeyError, якщо не знайдено."""
        rec = self.data.get(name)
        if rec is None:
            raise KeyError(f"{name} not found in AddressBook.")
        return rec

    def delete(self, name: str) -> bool:
        """Видаляє контакт з книги. Повертає True, якщо успішно, False — якщо ні."""
        if name in self.data:
            del self.data[name]
            return True
        return False

    def get_upcoming_birthdays(self) -> List[dict]:
        """
        Повертає список словників з іменами та датами, у кого день народження протягом 7 днів.
        Якщо день народження припадає на суботу (weekday=5) чи неділю (6),
        дата привітання переноситься на найближчий понеділок.
        Формат повернення: [{"name": ..., "congratulation_date": "YYYY.MM.DD"}, ...]
        """
        today = date.today()
        upcoming = []

        for record in self.data.values():
            if record.birthday is None:
                continue
            bday: date = record.birthday.value

            # Формуємо дату дня народження в поточному році
            birthday_this_year = bday.replace(year=today.year)
            # Якщо вже минув у поточному році, переносимо на наступний
            if birthday_this_year < today:
                birthday_this_year = birthday_this_year.replace(year=today.year + 1)

            # Обчислюємо різницю в днях між днем народження та сьогодні
            days_ahead = (birthday_this_year - today).days
            # Перевіряємо, чи відбувається протягом наступних 7 днів (включно з сьогодні)
            if 0 <= days_ahead <= 6:
                # Якщо день народження на вихідних, переносимо на понеділок
                if birthday_this_year.weekday() == 5:  # субота
                    congratulation_date = birthday_this_year + timedelta(days=2)
                elif birthday_this_year.weekday() == 6:  # неділя
                    congratulation_date = birthday_this_year + timedelta(days=1)
                else:
                    congratulation_date = birthday_this_year

                upcoming.append({
                    "name": record.name.value,
                    "congratulation_date": congratulation_date.strftime("%Y.%m.%d")
                })
        return upcoming


# -------------------------------------------------------------------
# 4. Функції для збереження/завантаження AddressBook у JSON
# -------------------------------------------------------------------
def save_address_book(book: AddressBook, filename: str = DATA_FILE):
    """
    Зберігає AddressBook у JSON.
    Кожен запис: {name: {"phones": [...], "birthday": "DD.MM.YYYY" or None}}
    """
    data_to_save = {}
    for name, record in book.data.items():
        phones_list = [ph.value for ph in record.phones]
        birthday_str = None
        if record.birthday is not None:
            # Зберігаємо у форматі DD.MM.YYYY, щоб при повторному завантаженні прочитати Birthday
            birthday_str = record.birthday.value.strftime("%d.%m.%Y")
        data_to_save[name] = {
            "phones": phones_list,
            "birthday": birthday_str
        }
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data_to_save, f, ensure_ascii=False, indent=4)


def load_address_book(filename: str = DATA_FILE) -> AddressBook:
    """
    Завантажує AddressBook з JSON-файлу. Якщо файл відсутній або некоректний, поверне порожню книгу.
    """
    book = AddressBook()
    try:
        with open(filename, "r", encoding="utf-8") as f:
            raw_data = json.load(f)
    except FileNotFoundError:
        print(Fore.YELLOW + f"Файл {filename} не знайдено. Створено нову книгу." + Style.RESET_ALL)
        return book
    except json.JSONDecodeError:
        print(Fore.YELLOW + "Помилка декодування JSON. Почато нову книгу." + Style.RESET_ALL)
        return book

    # Відтворюємо контакти
    for name, info in raw_data.items():
        record = Record(name)
        # Телефони
        for phone_str in info.get("phones", []):
            try:
                record.add_phone(phone_str)
            except ValueError as e:
                logging.error(f"Неправильний номер телефону в даних для {name}: {e}")
        # День народження
        birthday_str = info.get("birthday")
        if birthday_str:
            try:
                record.add_birthday(birthday_str)
            except ValueError as e:
                logging.error(f"Неправильна дата народження в даних для {name}: {e}")

        book.add_record(record)
    return book


# -------------------------------------------------------------------
# 5. Функції-обробники команд (з декоратором @input_error)
# -------------------------------------------------------------------
@input_error
def add_contact(args: list, book: AddressBook) -> str:
    """
    add [name] [phone] – Додає новий контакт або телефон до існуючого.
    Якщо контакт існує, додає телефон. Якщо не існує – створює контакт.
    """
    name, phone = args[0], args[1]
    try:
        record = book.find(name)
        # Якщо рекорд існує, просто додаємо телефон
        record.add_phone(phone)
        return f"Для контакту {name} додано номер {phone}."
    except KeyError:
        # Якщо не знайдено – створюємо новий контакт
        record = Record(name)
        record.add_phone(phone)
        book.add_record(record)
        return f"Створено новий контакт: {name} з номером {phone}."


@input_error
def change_phone(args: list, book: AddressBook) -> str:
    """
    change [name] [old_phone] [new_phone] – Змінює старий номер на новий.
    """
    name, old_phone, new_phone = args[0], args[1], args[2]
    record = book.find(name)
    changed = record.edit_phone(old_phone, new_phone)
    if changed:
        return f"У {name} замінено номер {old_phone} на {new_phone}."
    return f"У {name} не знайдено номер {old_phone}."


@input_error
def show_phones(args: list, book: AddressBook) -> str:
    """
    phone [name] – Показує всі номери телефону для контакту.
    """
    name = args[0]
    record = book.find(name)
    if not record.phones:
        return f"У {name} немає телефонних номерів."
    phones_str = ", ".join(ph.value for ph in record.phones)
    return f"Контакт {name}, телефони: {phones_str}"


@input_error
def show_all(args: list, book: AddressBook) -> str:
    """
    all – Показує всі контакти в адресній книзі (з телефонами та днями народження).
    """
    if not book.data:
        return "Адресна книга порожня."
    lines = []
    for record in book.data.values():
        lines.append(str(record))
    return "\n".join(lines)


@input_error
def add_birthday(args: list, book: AddressBook) -> str:
    """
    add-birthday [name] [DD.MM.YYYY] – Додає або оновлює день народження для контакту.
    """
    name, bday_str = args[0], args[1]
    record = book.find(name)
    record.add_birthday(bday_str)
    return f"Для {name} встановлено день народження: {bday_str}"


@input_error
def show_birthday(args: list, book: AddressBook) -> str:
    """
    show-birthday [name] – Показує день народження контакту.
    """
    name = args[0]
    record = book.find(name)
    bday_str = record.show_birthday()
    if bday_str == "День народження не задано":
        return f"У {name} день народження не вказано."
    return f"День народження {name}: {bday_str}"


@input_error
def show_upcoming_birthdays(args: list, book: AddressBook) -> str:
    """
    birthdays – Показує, у кого день народження протягом наступних 7 днів,
    з переносом вихідних на понеділок.
    """
    upcoming = book.get_upcoming_birthdays()
    if not upcoming:
        return "На наступному тижні немає іменинників."
    # Формуємо гарний вивід
    lines = ["Ось хто святкує День народження протягом наступних 7 днів:"]
    for person in upcoming:
        lines.append(f"{person['name']} => {person['congratulation_date']}")
    return "\n".join(lines)


@input_error
def greet(args: list, book: AddressBook) -> str:
    """hello – Виводить привітальне повідомлення."""
    return "Привіт! Чим можу допомогти?"


# -------------------------------------------------------------------
# 6. Головна функція main() з циклом вводу команд
# -------------------------------------------------------------------
def main():
    """
    Головна точка входу в програму.
    Завантажує / створює AddressBook, потім запускає цикл командного інтерфейсу.
    Після виходу зберігає книгу у файл.
    """
    # Вибір користувача: завантажити чи створити нову
    choice = input("Load existing contacts from JSON? (y/n): ").strip().lower()
    if choice.startswith("y"):
        address_book = load_address_book(DATA_FILE)
    else:
        address_book = AddressBook()
        print("Створено нову (порожню) адресну книгу.")

    # Словник команд -> функцій-обробників
    COMMANDS = {
        "add": add_contact,
        "change": change_phone,
        "phone": show_phones,
        "all": show_all,
        "add-birthday": add_birthday,
        "show-birthday": show_birthday,
        "birthdays": show_upcoming_birthdays,
        "hello": greet
    }

    print("Вітаю! Це бот адресної книги. Наберіть 'help' для відображення списку команд або команду для продовження.")

    while True:
        user_input = input(">>> ").strip()
        if not user_input:
            continue

        parts = user_input.split()
        command = parts[0].lower()
        args = parts[1:]

        # Перевірка на вихід
        if command in ("close", "exit"):
            print("До побачення! Зберігаю книгу...")
            save_address_book(address_book, DATA_FILE)
            break
        # Перевірка на help
        elif command == "help":
            print(Fore.YELLOW + "Підтримувані команди:\n" + Style.RESET_ALL +
                  "  hello\n"
                  "  add [name] [phone]\n"
                  "  change [name] [old_phone] [new_phone]\n"
                  "  phone [name]\n"
                  "  all\n"
                  "  add-birthday [name] [DD.MM.YYYY]\n"
                  "  show-birthday [name]\n"
                  "  birthdays\n"
                  "  close або exit (для завершення)\n")
        elif command in COMMANDS:
            handler = COMMANDS[command]
            result = handler(args, address_book)
            if result is not None:
                print(result)
        else:
            print(Fore.CYAN + "Невідома команда. Спробуйте 'help' для списку доступних команд." + Style.RESET_ALL)


if __name__ == "__main__":
    main()