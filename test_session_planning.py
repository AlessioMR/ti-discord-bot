import unittest
from datetime import date, datetime, timedelta, timezone

from session_planning import (
    CHOICE_AVAILABLE,
    CHOICE_BOTH,
    CHOICE_LABELS,
    CHOICE_SATURDAY,
    CHOICE_SUNDAY,
    evaluate_single_date,
    evaluate_weekend,
    fairness_points,
    parse_plan_date,
    parse_weekend_date,
)


def make_votes(saturday_ids, sunday_ids):
    votes = {}
    base = datetime(2026, 8, 1, tzinfo=timezone.utc)
    for index, user_id in enumerate(saturday_ids):
        votes[str(user_id)] = {
            "choice": CHOICE_SATURDAY,
            "voted_at": (base + timedelta(minutes=index)).isoformat(),
            "display_name": f"Spieler {user_id}",
        }
    for index, user_id in enumerate(sunday_ids):
        choice = CHOICE_BOTH if str(user_id) in votes else CHOICE_SUNDAY
        votes[str(user_id)] = {
            "choice": choice,
            "voted_at": (base + timedelta(minutes=index)).isoformat(),
            "display_name": f"Spieler {user_id}",
        }
    return votes


class SessionPlanningTests(unittest.TestCase):
    def test_sunday_is_normalized_to_saturday(self):
        self.assertEqual(
            parse_weekend_date("06.09.2026", today=date(2026, 8, 1)),
            date(2026, 9, 5),
        )

    def test_weekday_is_rejected_as_weekend(self):
        with self.assertRaises(ValueError):
            parse_weekend_date("04.09.2026", today=date(2026, 8, 1))

    def test_weekday_is_accepted_as_single_plan_date(self):
        self.assertEqual(
            parse_plan_date("04.09.2026", today=date(2026, 8, 1)),
            date(2026, 9, 4),
        )

    def test_sunday_plan_date_is_normalized_to_saturday(self):
        self.assertEqual(
            parse_plan_date("06.09.2026", today=date(2026, 8, 1)),
            date(2026, 9, 5),
        )

    def test_points_decay_by_actual_day_distance(self):
        target = date(2026, 9, 26)
        self.assertEqual(fairness_points(target, [date(2026, 9, 20)]), 4)
        self.assertEqual(fairness_points(target, [date(2026, 9, 19)]), 3)
        self.assertEqual(fairness_points(target, [date(2026, 9, 12)]), 2)
        self.assertEqual(fairness_points(target, [date(2026, 9, 5)]), 1)
        self.assertEqual(fairness_points(target, [date(2026, 8, 29)]), 0)

    def test_single_date_selects_six_and_builds_waitlist(self):
        base = datetime(2026, 8, 1, tzinfo=timezone.utc)
        votes = {
            str(user_id): {
                "choice": CHOICE_AVAILABLE,
                "voted_at": (base + timedelta(minutes=user_id)).isoformat(),
                "display_name": f"Spieler {user_id}",
            }
            for user_id in range(1, 8)
        }
        points = {str(user_id): 0 for user_id in range(1, 8)}
        points["1"] = 4
        result = evaluate_single_date(votes, points)
        selected_ids = [item["user_id"] for item in result["chosen"]["selected"]]
        self.assertNotIn("1", selected_ids)
        self.assertEqual([item["user_id"] for item in result["chosen"]["waitlist"]], ["1"])

    def test_single_date_needs_six_available_players(self):
        votes = {
            str(user_id): {
                "choice": CHOICE_AVAILABLE,
                "voted_at": datetime(2026, 8, 1, tzinfo=timezone.utc).isoformat(),
                "display_name": f"Spieler {user_id}",
            }
            for user_id in range(1, 6)
        }
        self.assertIsNone(evaluate_single_date(votes, {})["chosen"])

    def test_both_label_clarifies_only_one_game(self):
        self.assertEqual(
            CHOICE_LABELS[CHOICE_BOTH],
            "Beide Tage möglich (nur ein Spieltermin)",
        )

    def test_only_viable_day_is_selected(self):
        votes = make_votes(range(1, 7), range(20, 25))
        result = evaluate_weekend(votes, {})
        self.assertEqual(result["chosen"]["day"], CHOICE_SATURDAY)

    def test_saturday_wins_complete_tie(self):
        votes = make_votes(range(1, 7), range(20, 26))
        result = evaluate_weekend(votes, {})
        self.assertEqual(result["chosen"]["day"], CHOICE_SATURDAY)

    def test_lower_points_and_earlier_vote_rank_first(self):
        votes = make_votes(range(1, 8), [])
        points = {str(user_id): 0 for user_id in range(1, 8)}
        points["1"] = 3
        result = evaluate_weekend(votes, points)
        selected_ids = [item["user_id"] for item in result["chosen"]["selected"]]
        self.assertNotIn("1", selected_ids)
        self.assertEqual(selected_ids[0], "2")


if __name__ == "__main__":
    unittest.main()
