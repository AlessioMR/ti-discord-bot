import importlib
import json
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
            "VotesJSON": json.dumps(
                {
                    "1": {
                        "choice": "saturday",
                        "voted_at": "2026-08-01T10:00:00+00:00",
                        "display_name": "Alessio",
                    },
                    "2": {
                        "choice": "both",
                        "voted_at": "2026-08-01T10:01:00+00:00",
                        "display_name": "Janis",
                    },
                    "3": {
                        "choice": "cannot",
                        "voted_at": "2026-08-01T10:02:00+00:00",
                        "display_name": "@everyone **Test**",
                    },
                }
            ),
        }
        embed = bot.build_session_plan_embed(record)
        self.assertIn("Ende der Terminabstimmung", embed.description)
        self.assertIn("Jeder nur eine Stimme", embed.description)
        self.assertEqual(embed.fields[0].name, "Abgegebene Stimmen")
        vote_overview = embed.fields[0].value
        self.assertIn("**Samstag (1):** Alessio", vote_overview)
        self.assertIn("**Beide Tage möglich (nur ein Spieltermin) (1):** Janis", vote_overview)
        self.assertNotIn("@everyone", vote_overview)
        self.assertIn("\\*\\*Test\\*\\*", vote_overview)
        evaluation_text = embed.fields[1].value
        self.assertIn("**Punkte:**", evaluation_text)
        self.assertNotIn("Fairnesspunkte", evaluation_text)
        self.assertIn("Prioritätenliste für die Teilnehmerauswahl", evaluation_text)
        self.assertIn("Prioritätenliste für die Wahl des Tages", evaluation_text)
        self.assertLessEqual(len(evaluation_text), 1024)

        single_record = {
            **record,
            "PlanID": "single-test-plan",
            "WeekendSaturday": "2026-12-25",
            "VotesJSON": json.dumps(
                {
                    "1": {
                        "choice": "available",
                        "voted_at": "2026-08-01T10:00:00+00:00",
                        "display_name": "Alessio",
                    },
                    "2": {
                        "choice": "cannot",
                        "voted_at": "2026-08-01T10:01:00+00:00",
                        "display_name": "Janis",
                    },
                }
            ),
        }
        single_embed = bot.build_session_plan_embed(single_record)
        self.assertIn("Sondertermin", single_embed.title)
        self.assertIn("**Ich kann (1):** Alessio", single_embed.fields[0].value)
        self.assertIn("**Kann nicht (1):** Janis", single_embed.fields[0].value)
        single_evaluation_text = single_embed.fields[1].value
        self.assertNotIn("Wahl des Tages", single_evaluation_text)
        self.assertLessEqual(len(single_evaluation_text), 1024)
        single_summary = bot.build_session_plan_summary_embed(
            single_record,
            {
                "chosen": {"selected": [], "waitlist": []},
                "reason": "Mindestens sechs Spieler sind verfügbar.",
                "single": {"candidate_count": 6},
            },
        )
        self.assertIn("Terminvorschlag", single_summary.title)
        self.assertIn("6 Interessenten", single_summary.description)

        weekend_view = bot.SessionPlanVoteView("weekend")
        weekend_labels = [option.label for option in weekend_view.children[0].options]
        self.assertIn("Beide Tage möglich (nur ein Spieltermin)", weekend_labels)

        single_view = bot.SessionPlanVoteView("single", single_date=True)
        single_labels = [option.label for option in single_view.children[0].options]
        self.assertEqual(single_labels, ["Ich kann", "Kann nicht"])

        crowded_record = {
            **record,
            "VotesJSON": json.dumps(
                {
                    str(user_id): {
                        "choice": "saturday",
                        "voted_at": f"2026-08-01T10:{user_id % 60:02d}:00+00:00",
                        "display_name": f"Spieler {user_id} mit einem sehr langen Anzeigenamen",
                    }
                    for user_id in range(100)
                }
            ),
        }
        crowded_embed = bot.build_session_plan_embed(crowded_record)
        self.assertLessEqual(len(crowded_embed.fields[0].value), 1024)
        self.assertIn("weitere", crowded_embed.fields[0].value)


if __name__ == "__main__":
    unittest.main()
