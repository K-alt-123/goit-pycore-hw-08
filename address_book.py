from collections import UserDict
from datetime import date, datetime, timedelta
import re


class Field:
    """Store a contact field's value and provide its string representation."""

    def __init__(self, value):
        self.value = value

    def __str__(self) -> str:
        return str(self.value)


class Name(Field):
    """Store a required contact name, preserving its spelling and case."""

    def __init__(self, value: str):
        if not isinstance(value, str):
            raise TypeError("Name must be a string.")
        if not value.strip():
            raise ValueError("Name cannot be empty.")
        super().__init__(value.strip())


class Phone(Field):
    """Store a phone number consisting of exactly ten digits from 0 to 9."""

    def __init__(self, value: str):
        if not isinstance(value, str):
            raise TypeError("Phone number must be a string.")
        if len(value) != 10 or not value.isascii() or not value.isdigit():
            raise ValueError("Phone number must contain exactly 10 digits.")
        super().__init__(value)


class Birthday(Field):
    """Store a valid birthday entered in DD.MM.YYYY format."""

    def __init__(self, value: str):
        if not isinstance(value, str):
            raise TypeError("Birthday must be a string.")
        if re.fullmatch(r"[0-9]{2}\.[0-9]{2}\.[0-9]{4}", value) is None:
            raise ValueError("Invalid date format. Use DD.MM.YYYY")
        try:
            birthday = datetime.strptime(value, "%d.%m.%Y")
        except ValueError:
            raise ValueError("Invalid date format. Use DD.MM.YYYY") from None
        super().__init__(birthday)

    def __str__(self) -> str:
        return format_date(self.value)


def format_date(value: date) -> str:
    return f"{value.day:02d}.{value.month:02d}.{value.year:04d}"


class Record:
    """Manage one contact's name, phone numbers, and optional birthday."""

    def __init__(self, name: str):
        self.name = Name(name)
        self.phones: list[Phone] = []
        self.birthday: Birthday | None = None

    def add_birthday(self, value: str) -> None:
        self.birthday = Birthday(value)

    def add_phone(self, number: str) -> None:
        phone = Phone(number)
        if self.find_phone(phone.value) is not None:
            raise ValueError("Phone number already exists.")
        self.phones.append(phone)

    def remove_phone(self, number: str) -> None:
        phone = self.find_phone(number)
        if phone is None:
            raise ValueError("Phone number not found.")
        self.phones.remove(phone)

    def edit_phone(self, old_number: str, new_number: str) -> None:
        phone = self.find_phone(old_number)
        if phone is None:
            raise ValueError("Phone number not found.")

        replacement = Phone(new_number)
        duplicate = self.find_phone(replacement.value)
        if duplicate is not None and duplicate is not phone:
            raise ValueError("Phone number already exists.")

        # Validate first, then update the same object in its original position.
        phone.value = replacement.value

    def find_phone(self, number: str) -> Phone | None:
        number = Phone(number).value
        for phone in self.phones:
            if phone.value == number:
                return phone
        return None

    def __str__(self) -> str:
        phones = "; ".join(str(phone) for phone in self.phones) or "not set"
        birthday = str(self.birthday) if self.birthday else "not set"
        return f"Contact name: {self.name}, phones: {phones}, birthday: {birthday}"


class AddressBook(UserDict):
    """Store records by contact name, using case-sensitive matching."""

    def add_record(self, record: Record) -> None:
        if not isinstance(record, Record):
            raise TypeError("record must be a Record object.")
        name = record.name.value
        if name in self.data:
            raise ValueError(f"Contact already exists: {name}.")
        self.data[name] = record

    def find(self, name: str) -> Record | None:
        """Return the matching record, or None when it does not exist."""
        return self.data.get(Name(name).value)

    def delete(self, name: str) -> None:
        """Delete a record; raise KeyError when the name is absent."""
        del self.data[Name(name).value]

    def get_upcoming_birthdays(self, today: date | None = None) -> list[dict[str, str]]:
        """Find birthdays from today through six days ahead; greet on weekdays."""
        if today is None:
            today = date.today()
        upcoming = []
        for record in self.data.values():
            if record.birthday is None:
                continue
            birthday = record.birthday.value.date()
            next_birthday = self._birthday_in_year(birthday, today.year)
            if next_birthday < today:
                next_birthday = self._birthday_in_year(birthday, today.year + 1)

            if 0 <= (next_birthday - today).days < 7:
                greeting_date = next_birthday
                if greeting_date.weekday() >= 5:
                    greeting_date += timedelta(days=7 - greeting_date.weekday())
                upcoming.append((greeting_date, record.name.value))

        upcoming.sort(key=lambda item: (item[0], item[1]))
        return [
            {"name": name, "congratulation_date": format_date(greeting_date)}
            for greeting_date, name in upcoming
        ]

    @staticmethod
    def _birthday_in_year(birthday: date, year: int) -> date:
        try:
            return birthday.replace(year=year)
        except ValueError:
            # Celebrate February 29 birthdays on February 28 in non-leap years.
            return birthday.replace(year=year, day=28)
