from typing import Protocol

from .models import Message
from .store import MessageStore


class ModemAdapter(Protocol):
    def list_messages(self) -> list[Message]: ...

    def initiate_ussd(self, code: str) -> str: ...

    def send_message(self, number: str, text: str) -> Message: ...


class SmsService:
    def __init__(self, modem: ModemAdapter, store: MessageStore):
        self.modem = modem
        self.store = store

    def sync_messages(self) -> list[Message]:
        return [self.store.upsert_message(message) for message in self.modem.list_messages()]

    def query_credit(self, ussd_code: str) -> str:
        if not ussd_code:
            raise ValueError("USSD code cannot be empty")
        return self.modem.initiate_ussd(ussd_code)

    def send_message(self, number: str, text: str) -> Message:
        if not number:
            raise ValueError("recipient number cannot be empty")
        if not text:
            raise ValueError("message text cannot be empty")
        return self.store.upsert_message(self.modem.send_message(number, text))
