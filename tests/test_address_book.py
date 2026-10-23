import sys
import unittest
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from address_book import AddressBook, Birthday, Phone, Record


class ValidationTests(unittest.TestCase):
    def test_phone_preserves_leading_zeroes_and_rejects_invalid_numbers(self):
        self.assertEqual(Phone("0123456789").value, "0123456789")
        for value in ("123", "12345678901", "+123456789", "12345abcde",
                      "12345 7890", "١٢٣٤٥٦٧٨٩٠"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                Phone(value)

    def test_birthday_stores_datetime_and_round_trips(self):
        birthday = Birthday("29.02.2000")
        self.assertEqual(birthday.value, datetime(2000, 2, 29))
        self.assertEqual(str(birthday), "29.02.2000")

    def test_birthday_rejects_bad_format_and_impossible_dates(self):
        for value in ("", "1.01.2000", "01.1.2000", "2000-01-01",
                      "01/01/2000", "31.04.2000", "29.02.2001",
                      "00.01.2000", "01.13.2000", "01.01.0000",
                      " 01.01.2000", "01.01.2000 "):
            with self.subTest(value=value):
                with self.assertRaisesRegex(ValueError, "Use DD.MM.YYYY"):
                    Birthday(value)

    def test_invalid_update_preserves_the_existing_birthday(self):
        record = Record("John")
        self.assertIsNone(record.birthday)
        record.add_birthday("01.01.2000")
        original = record.birthday
        with self.assertRaises(ValueError):
            record.add_birthday("31.02.2000")
        self.assertIs(record.birthday, original)
        record.add_birthday("02.01.2000")
        self.assertEqual(str(record.birthday), "02.01.2000")

    def test_invalid_or_duplicate_phone_edits_preserve_existing_numbers(self):
        record = Record("John")
        record.add_phone("0123456789")
        record.add_phone("0987654321")
        for replacement in ("123", "0987654321"):
            with self.subTest(replacement=replacement):
                with self.assertRaises(ValueError):
                    record.edit_phone("0123456789", replacement)
                self.assertEqual([p.value for p in record.phones],
                                 ["0123456789", "0987654321"])

    def test_contacts_have_independent_phones_and_birthdays(self):
        first, second = Record("John"), Record("Jane")
        first.add_phone("0123456789")
        first.add_birthday("01.01.2000")
        self.assertEqual(second.phones, [])
        self.assertIsNone(second.birthday)


class UpcomingBirthdayTests(unittest.TestCase):
    def setUp(self):
        self.book = AddressBook()

    def add(self, name, birthday=None):
        record = Record(name)
        if birthday is not None:
            record.add_birthday(birthday)
        self.book.add_record(record)

    def test_seven_day_window_includes_today_and_day_six_but_not_day_seven(self):
        self.add("Today", "21.10.1990")
        self.add("DaySix", "27.10.1990")
        self.add("TooLate", "28.10.1990")
        self.add("Yesterday", "20.10.1990")
        self.add("NoBirthday")
        self.assertEqual(self.book.get_upcoming_birthdays(date(2026, 10, 21)), [
            {"name": "Today", "congratulation_date": "21.10.2026"},
            {"name": "DaySix", "congratulation_date": "27.10.2026"},
        ])

    def test_weekend_birthdays_move_to_monday_and_results_are_sorted(self):
        self.add("Sunday", "25.10.2000")
        self.add("Friday", "23.10.2000")
        self.add("Saturday", "24.10.2000")
        self.assertEqual(self.book.get_upcoming_birthdays(date(2026, 10, 21)), [
            {"name": "Friday", "congratulation_date": "23.10.2026"},
            {"name": "Saturday", "congratulation_date": "26.10.2026"},
            {"name": "Sunday", "congratulation_date": "26.10.2026"},
        ])

    def test_monday_greeting_can_fall_outside_the_birthday_window(self):
        self.add("Weekend", "25.10.1990")
        self.assertEqual(self.book.get_upcoming_birthdays(date(2026, 10, 19)), [
            {"name": "Weekend", "congratulation_date": "26.10.2026"},
        ])

    def test_new_year_birthdays_use_the_next_year_and_sort_chronologically(self):
        self.add("January", "01.01.1990")
        self.add("December", "31.12.1990")
        self.assertEqual(self.book.get_upcoming_birthdays(date(2026, 12, 29)), [
            {"name": "December", "congratulation_date": "31.12.2026"},
            {"name": "January", "congratulation_date": "01.01.2027"},
        ])

    def test_weekend_shift_can_cross_the_year_boundary(self):
        self.add("YearEnd", "31.12.2000")
        self.assertEqual(self.book.get_upcoming_birthdays(date(2023, 12, 29)), [
            {"name": "YearEnd", "congratulation_date": "01.01.2024"},
        ])

    def test_february_29_in_leap_and_non_leap_years(self):
        self.add("Leap", "29.02.2000")
        for today, expected in (
            (date(2025, 2, 27), "28.02.2025"),
            (date(2028, 2, 28), "29.02.2028"),
        ):
            with self.subTest(today=today):
                self.assertEqual(self.book.get_upcoming_birthdays(today), [
                    {"name": "Leap", "congratulation_date": expected},
                ])
        self.assertEqual(self.book.get_upcoming_birthdays(date(2025, 3, 1)), [])
        self.assertEqual(str(self.book.find("Leap").birthday), "29.02.2000")

    def test_empty_book_and_contacts_without_birthdays(self):
        self.assertEqual(self.book.get_upcoming_birthdays(), [])
        self.add("John")
        self.assertEqual(self.book.get_upcoming_birthdays(date(2026, 10, 21)), [])


if __name__ == "__main__":
    unittest.main()
