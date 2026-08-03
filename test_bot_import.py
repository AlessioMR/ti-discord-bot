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
        plan_command = session_group.get_command("plan")
        self.assertIsNotNone(plan_command)
        self.assertIsNotNone(session_group.get_command("cancel_plan"))
        self.assertIsNone(session_group.get_command("cleanup"))

        parameter_names = [parameter.name for parameter in plan_command.parameters]
        self.assertIn("poll_duration", parameter_names)
        self.assertNotIn("duration_hours", parameter_names)

        record = {
            "PlanID": "test-plan",
            "GuildID": "1",
            "ChannelID": "2",
            "WeekendSaturday": "2026-09-05",
            "EndsAtUTC": "2026-08-04T12:00:00+00:00",
            "Status": "active",
            "VotesJSON": "{}",
        }
        embed = bot.build_session_plan_embed(record)
        self.assertIn("Ende der Terminabstimmung", embed.description)
        self.assertIn("Jeder nur eine Stimme", embed.description)
        evaluation_text = embed.fields[1].value
        self.assertIn("**Punkte:**", evaluation_text)
        self.assertNotIn("Fairnesspunkte", evaluation_text)
        self.assertLessEqual(len(evaluation_text), 1024)


if __name__ == "__main__":
    unittest.main()
