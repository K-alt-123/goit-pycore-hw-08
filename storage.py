import os
import pickle
import tempfile
from pathlib import Path

from address_book import AddressBook


DEFAULT_FILE = Path(__file__).resolve().with_name("addressbook.pkl")


def save_data(book: AddressBook, filename=DEFAULT_FILE) -> None:
    if not isinstance(book, AddressBook):
        raise TypeError("Only an AddressBook can be saved.")

    path = Path(filename)
    temporary_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb", dir=path.parent, prefix=f".{path.name}.",
            suffix=".tmp", delete=False,
        ) as file:
            temporary_path = Path(file.name)
            pickle.dump(book, file, protocol=pickle.HIGHEST_PROTOCOL)
            file.flush()
            os.fsync(file.fileno())
        # Replace the previous save only after the new file is complete.
        os.replace(temporary_path, path)
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def load_data(filename=DEFAULT_FILE) -> AddressBook:
    """Load the application's own pickle file."""
    try:
        with open(filename, "rb") as file:
            book = pickle.load(file)
    except FileNotFoundError:
        return AddressBook()
    except (pickle.UnpicklingError, EOFError, AttributeError,
            ImportError, ValueError, TypeError) as error:
        raise ValueError(
            "The saved address book is damaged or incompatible."
        ) from error

    if not isinstance(book, AddressBook):
        raise ValueError("The save file does not contain an AddressBook.")
    return book
