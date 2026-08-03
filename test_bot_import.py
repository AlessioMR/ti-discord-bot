import importlib
import os
import unittest
from unittest import mock


class _FakeSpreadsheet:
    sheet1 = object()


class _FakeGspreadClient:
    def open_by_key(self, _sheet_id):
        return _FakeSpreadsheet()


class BotImportTests(unittest.TestCase):
    def test_session_plan_command_registers(self):
        os.environ["DISCORD_TOKEN"] = "test-token"
        os.environ["GOOGLE_CREDENTIALS"] = "{}"

        import discord
        import gspread
        from google.oauth2 import service_account

        with (
            mock.patch.object(
                service_account.Credentials,
                "from_service_account_info",
                return_value=object(),
            ),
            mock.patch.object(
                gspread,
                "authorize",
                return_value=_FakeGspreadClient(),
            ),
            mock.patch.object(discord.Client, "run", return_value=None),
        ):
            bot = importlib.import_module("bot")

        session_group = bot.tree.get_command("session")
        self.assertIsNotNone(session_group)
        self.assertIsNotNone(session_group.get_command("plan"))


if __name__ == "__main__":
    unittest.main()
