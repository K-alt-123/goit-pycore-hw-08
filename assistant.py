import pickle
import sys
from functools import wraps

from address_book import AddressBook, Record
from storage import DEFAULT_FILE, load_data, save_data


def input_error(func):
    """Turn expected input errors into messages and keep the bot running."""
    @wraps(func)
    def inner(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except KeyError:
            return "Contact not found."
        except ValueError as error:
            return str(error) or "Invalid command."
        except IndexError:
            return "Not enough arguments."
    return inner


def parse_input(user_input: str) -> tuple[str, list[str]]:
    parts = user_input.split()
    if not parts:
        return "", []
    command, *args = parts
    return command.casefold(), args


def get_record(name: str, book: AddressBook) -> Record:
    record = book.find(name)
    if record is None:
        raise KeyError(name)
    return record


@input_error
def add_contact(args: list[str], book: AddressBook) -> str:
    if len(args) != 2:
        raise ValueError("Usage: add [name] [phone]")
    name, phone = args
    record = book.find(name)
    if record is None:
        record = Record(name)
        record.add_phone(phone)
        book.add_record(record)
        return "Contact added."
    record.add_phone(phone)
    return "Contact updated."


@input_error
def change_contact(args: list[str], book: AddressBook) -> str:
    if len(args) != 3:
        raise ValueError("Usage: change [name] [old phone] [new phone]")
    name, old_phone, new_phone = args
    get_record(name, book).edit_phone(old_phone, new_phone)
    return "Contact updated."


@input_error
def show_phone(args: list[str], book: AddressBook) -> str:
    if len(args) != 1:
        raise ValueError("Usage: phone [name]")
    record = get_record(args[0], book)
    return "; ".join(str(phone) for phone in record.phones) or "No phone numbers set."


@input_error
def show_all(book: AddressBook) -> str:
    return "\n".join(str(record) for record in book.values()) or "No contacts found."


@input_error
def add_birthday(args: list[str], book: AddressBook) -> str:
    if len(args) != 2:
        raise ValueError("Usage: add-birthday [name] [DD.MM.YYYY]")
    name, birthday = args
    get_record(name, book).add_birthday(birthday)
    return "Birthday saved."


@input_error
def show_birthday(args: list[str], book: AddressBook) -> str:
    if len(args) != 1:
        raise ValueError("Usage: show-birthday [name]")
    record = get_record(args[0], book)
    if record.birthday is None:
        return f"Birthday not set for {record.name}."
    return f"{record.name}: {record.birthday}"


@input_error
def birthdays(args: list[str], book: AddressBook) -> str:
    if args:
        raise ValueError("Usage: birthdays")
    upcoming = book.get_upcoming_birthdays()
    if not upcoming:
        return "No upcoming birthdays in the next 7 days."
    return "\n".join(
        f"{item['congratulation_date']}: {item['name']}" for item in upcoming
    )


@input_error
def handle_command(command: str, args: list[str], book: AddressBook) -> str:
    if command in ("hello", "all", "close", "exit") and args:
        raise ValueError(f"'{command}' does not accept arguments.")
    if command in ("close", "exit"):
        return "Good bye!"
    if command == "hello":
        return "How can I help you?"
    if command == "add":
        return add_contact(args, book)
    if command == "change":
        return change_contact(args, book)
    if command == "phone":
        return show_phone(args, book)
    if command == "all":
        return show_all(book)
    if command == "add-birthday":
        return add_birthday(args, book)
    if command == "show-birthday":
        return show_birthday(args, book)
    if command == "birthdays":
        return birthdays(args, book)
    raise ValueError("Invalid command.")


def main(filename=DEFAULT_FILE) -> int:
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")

    try:
        book = load_data(filename)
    except (OSError, ValueError) as error:
        print(f"Could not load contacts: {error}", file=sys.stderr)
        return 1

    exit_code = 0
    print("Welcome to the assistant bot!")
    try:
        while True:
            user_input = input("Enter a command: ")
            command, args = parse_input(user_input)
            print(handle_command(command, args, book))
            if command in ("close", "exit") and not args:
                break
    except (EOFError, KeyboardInterrupt):
        print("\nGood bye!")
    finally:
        try:
            save_data(book, filename)
        except (OSError, pickle.PickleError) as error:
            print(f"Could not save contacts: {error}", file=sys.stderr)
            exit_code = 1
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
