import pickle
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from address_book import AddressBook, Birthday, Name, Phone, Record
from storage import load_data, save_data


class StorageTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.directory = Path(directory.name)
        self.filename = self.directory / "addressbook.pkl"
        self.book = AddressBook()
        john = Record("John")
        john.add_phone("0123456789")
        john.add_phone("0987654321")
        john.add_birthday("29.02.2000")
        self.book.add_record(john)

    def test_missing_file_returns_a_new_empty_book(self):
        first = load_data(self.filename)
        second = load_data(self.filename)
        self.assertIsInstance(first, AddressBook)
        self.assertEqual(first.data, {})
        self.assertIsNot(first, second)
        self.assertFalse(self.filename.exists())

    def test_empty_book_can_be_saved_and_loaded(self):
        save_data(AddressBook(), self.filename)
        restored = load_data(self.filename)
        self.assertIsInstance(restored, AddressBook)
        self.assertEqual(restored.data, {})

    def test_round_trip_preserves_all_fields_and_object_types(self):
        self.book.add_record(Record("Олексій"))
        save_data(self.book, self.filename)
        restored = load_data(self.filename)
        self.assertIsInstance(restored, AddressBook)
        self.assertEqual(list(restored), ["John", "Олексій"])
        john = restored.find("John")
        self.assertIsInstance(john, Record)
        self.assertIsInstance(john.name, Name)
        self.assertTrue(all(isinstance(phone, Phone) for phone in john.phones))
        self.assertEqual([p.value for p in john.phones],
                         ["0123456789", "0987654321"])
        self.assertIsInstance(john.birthday, Birthday)
        self.assertEqual(john.birthday.value, datetime(2000, 2, 29))
        self.assertEqual(restored.find("Олексій").phones, [])
        self.assertIsNone(restored.find("Олексій").birthday)
        john.edit_phone("0123456789", "0501234567")
        self.assertEqual(self.book.find("John").phones[0].value, "0123456789")

    def test_later_saves_include_edits_and_deletions(self):
        self.book.add_record(Record("Jane"))
        save_data(self.book, self.filename)
        restored = load_data(self.filename)
        restored.find("John").edit_phone("0123456789", "0501234567")
        restored.find("John").add_birthday("01.01.2001")
        restored.delete("Jane")
        save_data(restored, str(self.filename))
        latest = load_data(str(self.filename))
        self.assertIsNone(latest.find("Jane"))
        self.assertEqual(latest.find("John").phones[0].value, "0501234567")
        self.assertEqual(str(latest.find("John").birthday), "01.01.2001")
        latest.clear()
        save_data(latest, self.filename)
        self.assertEqual(load_data(self.filename).data, {})

    def test_corrupt_and_empty_files_raise_without_being_changed(self):
        for content in (b"", b"not a pickle", pickle.dumps(self.book)[:20]):
            with self.subTest(content=content):
                self.filename.write_bytes(content)
                with self.assertRaisesRegex(ValueError, "damaged or incompatible"):
                    load_data(self.filename)
                self.assertEqual(self.filename.read_bytes(), content)

    def test_pickle_containing_the_wrong_object_is_rejected(self):
        content = pickle.dumps({"John": "0123456789"})
        self.filename.write_bytes(content)
        with self.assertRaisesRegex(ValueError, "does not contain an AddressBook"):
            load_data(self.filename)
        self.assertEqual(self.filename.read_bytes(), content)

    def test_read_permission_error_is_not_treated_as_a_missing_file(self):
        with patch("storage.open", side_effect=PermissionError("Access denied")):
            with self.assertRaises(PermissionError):
                load_data(self.filename)

    def test_saving_the_wrong_object_preserves_the_existing_file(self):
        save_data(self.book, self.filename)
        original = self.filename.read_bytes()
        with self.assertRaises(TypeError):
            save_data({}, self.filename)
        self.assertEqual(self.filename.read_bytes(), original)

    def test_partial_write_failure_preserves_the_previous_save(self):
        save_data(self.book, self.filename)
        original = self.filename.read_bytes()

        def fail_after_writing(book, file, protocol):
            file.write(b"incomplete")
            raise OSError("Disk full")

        with patch("storage.pickle.dump", side_effect=fail_after_writing):
            with self.assertRaisesRegex(OSError, "Disk full"):
                save_data(self.book, self.filename)
        self.assertEqual(self.filename.read_bytes(), original)
        self.assertEqual(list(self.directory.iterdir()), [self.filename])

    def test_replacement_failure_preserves_the_previous_save(self):
        save_data(self.book, self.filename)
        original = self.filename.read_bytes()
        with patch("storage.os.replace", side_effect=PermissionError("Locked")):
            with self.assertRaises(PermissionError):
                save_data(AddressBook(), self.filename)
        self.assertEqual(self.filename.read_bytes(), original)
        self.assertEqual(list(self.directory.iterdir()), [self.filename])

    def test_serialization_failure_does_not_leave_an_incomplete_save(self):
        with patch("storage.pickle.dump", side_effect=pickle.PicklingError):
            with self.assertRaises(pickle.PicklingError):
                save_data(self.book, self.filename)
        self.assertEqual(list(self.directory.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
