import io
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from datetime import date
from pathlib import Path
from unittest.mock import patch

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))
import assistant
from address_book import AddressBook
from storage import load_data


class CommandTests(unittest.TestCase):
    def setUp(self):
        self.book = AddressBook()

    def command(self, text):
        command, args = assistant.parse_input(text)
        return assistant.handle_command(command, args, self.book)

    def test_all_contact_commands_and_multiple_phones(self):
        self.assertEqual(self.command("HELLO"), "How can I help you?")
        self.assertEqual(self.command("all"), "No contacts found.")
        self.assertEqual(self.command("add John 0123456789"), "Contact added.")
        self.assertEqual(self.command("add John 0987654321"), "Contact updated.")
        self.assertEqual(self.command("phone John"), "0123456789; 0987654321")
        self.assertEqual(self.command("change John 0123456789 0501234567"),
                         "Contact updated.")
        self.assertEqual(self.command("phone John"), "0501234567; 0987654321")
        self.assertIn("birthday: not set", self.command("all"))

    def test_birthday_commands_store_replace_and_show_a_single_birthday(self):
        self.command("add John 0123456789")
        self.assertEqual(self.command("show-birthday John"), "Birthday not set for John.")
        self.assertEqual(self.command("add-birthday John 24.10.1990"), "Birthday saved.")
        self.assertEqual(self.command("show-birthday John"), "John: 24.10.1990")
        self.command("add-birthday John 25.10.1990")
        self.assertIn("birthday: 25.10.1990", self.command("all"))

    def test_birthdays_command_uses_current_date_and_formats_greeting_dates(self):
        self.command("add John 0123456789")
        self.command("add-birthday John 24.10.1990")
        with patch("address_book.date") as current_date:
            current_date.today.return_value = date(2026, 10, 21)
            self.assertEqual(self.command("birthdays"), "26.10.2026: John")
        self.assertEqual(assistant.birthdays([], AddressBook()),
                         "No upcoming birthdays in the next 7 days.")

    def test_invalid_new_phone_does_not_create_a_contact(self):
        self.assertIn("exactly 10 digits", self.command("add John 123"))
        self.assertIsNone(self.book.find("John"))

    def test_invalid_updates_do_not_change_existing_data(self):
        self.command("add John 0123456789")
        self.command("add-birthday John 01.01.2000")
        self.assertIn("Invalid date format", self.command("add-birthday John 31.02.2000"))
        self.assertIn("exactly 10 digits", self.command("change John 0123456789 123"))
        self.assertIn("already exists", self.command("add John 0123456789"))
        self.assertIn("not found", self.command("change John 9999999999 0501234567"))
        self.assertEqual(self.command("show-birthday John"), "John: 01.01.2000")
        self.assertEqual(self.command("phone John"), "0123456789")

    def test_missing_contacts_return_informative_messages(self):
        for text in ("phone Missing", "change Missing 0123456789 0987654321",
                     "add-birthday Missing 01.01.2000", "show-birthday Missing"):
            with self.subTest(text=text):
                self.assertEqual(self.command(text), "Contact not found.")
        self.assertEqual(len(self.book), 0)

    def test_argument_counts_are_checked_for_every_data_command(self):
        cases = {
            "add": ["", "John", "John 0123456789 extra"],
            "change": ["", "John 0123456789", "John 0123456789 0987654321 extra"],
            "phone": ["", "John extra"],
            "add-birthday": ["", "John", "John 01.01.2000 extra"],
            "show-birthday": ["", "John extra"],
            "birthdays": ["extra"],
        }
        for command, arguments in cases.items():
            for args in arguments:
                with self.subTest(command=command, args=args):
                    self.assertTrue(self.command(f"{command} {args}").startswith("Usage:"))
        for command in ("all", "hello", "exit", "close"):
            self.assertIn("does not accept arguments", self.command(f"{command} extra"))

    def test_parser_preserves_names_and_handles_empty_input(self):
        self.assertEqual(assistant.parse_input("  AdD\tОлексій  0123456789 "),
                         ("add", ["Олексій", "0123456789"]))
        for text in ("", " \t", "unknown"):
            self.assertEqual(self.command(text), "Invalid command.")

    def test_error_decorator_preserves_metadata_and_does_not_hide_programming_errors(self):
        @assistant.input_error
        def broken():
            raise TypeError("Unexpected error")
        self.assertEqual(broken.__name__, "broken")
        with self.assertRaises(TypeError):
            broken()


class SessionTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.directory = Path(directory.name)
        self.project = self.directory / "bot"
        self.project.mkdir()
        for name in ("assistant.py", "address_book.py", "storage.py"):
            shutil.copyfile(PROJECT / name, self.project / name)

    def run_bot(self, commands):
        return subprocess.run(
            [sys.executable, "-B", str(self.project / "assistant.py")],
            input=commands, capture_output=True, text=True, encoding="utf-8",
            env={**os.environ, "PYTHONIOENCODING": "cp1252"},
            cwd=self.directory, timeout=10, check=False,
        )

    def test_complete_session_recovers_from_errors_and_preserves_unicode(self):
        result = self.run_bot(
            "add Олексій 123\nadd Олексій 0123456789\n"
            "add Олексій 0987654321\nphone Олексій\n"
            "change Олексій 0123456789 0501234567\n"
            "add-birthday Олексій 31.02.2000\n"
            "add-birthday Олексій 24.10.1990\nshow-birthday Олексій\n"
            "all\nbirthdays\nexit extra\nhello\nexit\nhello\n"
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, "")
        self.assertIn("exactly 10 digits", result.stdout)
        self.assertIn("Invalid date format", result.stdout)
        self.assertIn("Олексій: 24.10.1990", result.stdout)
        self.assertIn("0501234567; 0987654321", result.stdout)
        self.assertIn("'exit' does not accept arguments.", result.stdout)
        self.assertEqual(result.stdout.count("How can I help you?"), 1)
        self.assertTrue(result.stdout.endswith("Good bye!\n"))

    def test_close_and_exit_stop_before_the_next_command(self):
        for command in ("ClOsE", "EXIT"):
            with self.subTest(command=command):
                result = self.run_bot(
                    f"add {command} 0123456789\n{command}\nhello\n"
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertNotIn("How can I help you?", result.stdout)
                self.assertTrue(result.stdout.endswith("Good bye!\n"))
                restarted = self.run_bot(f"phone {command}\nexit\n")
                self.assertEqual(restarted.returncode, 0, restarted.stderr)
                self.assertIn("0123456789", restarted.stdout)

    def test_end_of_input_exits_without_a_traceback(self):
        result = self.run_bot("add John 0123456789\n")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, "")
        self.assertTrue(result.stdout.endswith("Good bye!\n"))
        restarted = self.run_bot("phone John\nexit\n")
        self.assertEqual(restarted.returncode, 0, restarted.stderr)
        self.assertIn("0123456789", restarted.stdout)

    def test_keyboard_interrupt_exits_cleanly(self):
        output = io.StringIO()
        filename = self.project / "addressbook.pkl"
        with patch("sys.stdin", io.StringIO()), patch("sys.stderr", io.StringIO()):
            with patch("builtins.input", side_effect=[
                "add John 0123456789", "add-birthday John 24.10.1990",
                KeyboardInterrupt,
            ]):
                with redirect_stdout(output):
                    exit_code = assistant.main(filename)
        self.assertEqual(exit_code, 0)
        self.assertTrue(output.getvalue().endswith("Good bye!\n"))
        restored = load_data(filename).find("John")
        self.assertEqual(restored.phones[0].value, "0123456789")
        self.assertEqual(str(restored.birthday), "24.10.1990")

    def test_restart_restores_contacts_and_saves_later_changes(self):
        first = self.run_bot(
            "add Олексій 0123456789\nadd Олексій 0987654321\n"
            "add-birthday Олексій 24.10.1990\nadd Jane 0501234567\nexit\n"
        )
        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertTrue((self.project / "addressbook.pkl").is_file())
        self.assertFalse((self.directory / "addressbook.pkl").exists())
        second = self.run_bot(
            "phone Олексій\nshow-birthday Олексій\nphone Jane\n"
            "change Олексій 0123456789 1112223333\n"
            "add-birthday Jane 01.01.2000\nclose\n"
        )
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertIn("0123456789; 0987654321", second.stdout)
        self.assertIn("Олексій: 24.10.1990", second.stdout)
        self.assertIn("0501234567", second.stdout)
        third = self.run_bot("all\nexit\n")
        self.assertEqual(third.returncode, 0, third.stderr)
        self.assertIn("1112223333; 0987654321", third.stdout)
        self.assertIn("birthday: 24.10.1990", third.stdout)
        self.assertIn("Jane, phones: 0501234567, birthday: 01.01.2000",
                      third.stdout)

    def test_damaged_save_stops_startup_without_overwriting_the_file(self):
        filename = self.project / "addressbook.pkl"
        content = b"damaged save"
        filename.write_bytes(content)
        result = self.run_bot("add John 0123456789\nexit\n")
        self.assertEqual(result.returncode, 1)
        self.assertIn("Could not load contacts", result.stderr)
        self.assertNotIn("Traceback", result.stderr)
        self.assertNotIn("Enter a command", result.stdout)
        self.assertEqual(filename.read_bytes(), content)

    def test_load_permission_error_reports_failure_without_saving(self):
        output, errors = io.StringIO(), io.StringIO()
        with patch("assistant.load_data", side_effect=PermissionError("Denied")):
            with patch("assistant.save_data") as save:
                with redirect_stdout(output), redirect_stderr(errors):
                    exit_code = assistant.main(self.project / "addressbook.pkl")
        self.assertEqual(exit_code, 1)
        self.assertIn("Could not load contacts", errors.getvalue())
        save.assert_not_called()

    def test_save_error_is_reported_with_a_failure_exit_code(self):
        output, errors = io.StringIO(), io.StringIO()
        with patch("assistant.save_data", side_effect=OSError("Disk full")):
            with patch("builtins.input", side_effect=["add John 0123456789", "exit"]):
                with redirect_stdout(output), redirect_stderr(errors):
                    exit_code = assistant.main(self.project / "addressbook.pkl")
        self.assertEqual(exit_code, 1)
        self.assertIn("Could not save contacts: Disk full", errors.getvalue())


if __name__ == "__main__":
    unittest.main()
