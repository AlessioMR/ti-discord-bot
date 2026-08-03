from __future__ import annotations

from datetime import date, datetime, timedelta, timezone


CHOICE_SATURDAY = "saturday"
CHOICE_SUNDAY = "sunday"
CHOICE_BOTH = "both"
CHOICE_CANNOT = "cannot"

CHOICE_LABELS = {
    CHOICE_SATURDAY: "Samstag",
    CHOICE_SUNDAY: "Sonntag",
    CHOICE_BOTH: "Beide Tage möglich",
    CHOICE_CANNOT: "Kann nicht",
}


def parse_weekend_date(value: str, today: date | None = None) -> date:
    value = str(value).strip()
    parsed = None

    for date_format in ("%d.%m.%Y", "%Y-%m-%d"):
        try:
            parsed = datetime.strptime(value, date_format).date()
            break
        except ValueError:
            continue

    if parsed is None:
        raise ValueError("Ungültiges Datum. Nutze `TT.MM.JJJJ`, z.B. `05.09.2026`.")
    if parsed.weekday() not in {5, 6}:
        raise ValueError("Bitte gib einen Samstag oder Sonntag des gewünschten Wochenendes an.")

    saturday = parsed if parsed.weekday() == 5 else parsed - timedelta(days=1)
    if saturday < (today or date.today()):
        raise ValueError("Das zu planende Wochenende muss in der Zukunft liegen.")
    return saturday


def weekend_week_start(value: date) -> date:
    return value - timedelta(days=value.weekday())


def fairness_points(target_date: date, participation_dates) -> int:
    target_week = weekend_week_start(target_date)
    previous_weeks = []

    for participation_date in participation_dates:
        if isinstance(participation_date, datetime):
            participation_date = participation_date.date()
        participation_week = weekend_week_start(participation_date)
        if participation_week <= target_week:
            previous_weeks.append(participation_week)

    if not previous_weeks:
        return 0

    weeks_since = (target_week - max(previous_weeks)).days // 7
    if weeks_since <= 0:
        return 4
    if weeks_since == 1:
        return 3
    if weeks_since == 2:
        return 2
    if weeks_since == 3:
        return 1
    return 0


def _parse_vote_timestamp(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return datetime.max.replace(tzinfo=timezone.utc)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def rank_candidates(votes: dict, accepted_choices: set[str], points_by_user: dict) -> list[dict]:
    candidates = []

    for user_id, vote in votes.items():
        if vote.get("choice") not in accepted_choices:
            continue
        candidates.append({
            "user_id": str(user_id),
            "display_name": str(vote.get("display_name") or f"Spieler {user_id}"),
            "choice": vote.get("choice"),
            "voted_at": str(vote.get("voted_at", "")),
            "points": int(points_by_user.get(str(user_id), 0)),
        })

    candidates.sort(key=lambda candidate: (
        candidate["points"],
        _parse_vote_timestamp(candidate["voted_at"]),
        int(candidate["user_id"]),
    ))
    return candidates


def build_day_result(votes: dict, points_by_user: dict, day: str) -> dict:
    if day == CHOICE_SATURDAY:
        accepted = {CHOICE_SATURDAY, CHOICE_BOTH}
    elif day == CHOICE_SUNDAY:
        accepted = {CHOICE_SUNDAY, CHOICE_BOTH}
    else:
        raise ValueError(f"Unbekannter Abstimmungstag: {day}")

    ranked = rank_candidates(votes, accepted, points_by_user)
    selected = ranked[:6] if len(ranked) >= 6 else []
    waitlist = ranked[6:] if len(ranked) >= 6 else []
    return {
        "day": day,
        "candidate_count": len(ranked),
        "viable": len(ranked) >= 6,
        "ranked": ranked,
        "selected": selected,
        "waitlist": waitlist,
        "zero_point_selected": sum(candidate["points"] == 0 for candidate in selected),
        "selected_points_sum": sum(candidate["points"] for candidate in selected),
    }


def evaluate_weekend(votes: dict, points_by_user: dict) -> dict:
    saturday = build_day_result(votes, points_by_user, CHOICE_SATURDAY)
    sunday = build_day_result(votes, points_by_user, CHOICE_SUNDAY)
    viable = [result for result in (saturday, sunday) if result["viable"]]

    if not viable:
        return {
            "chosen": None,
            "reason": (
                "Für keinen der beiden Tage haben mindestens sechs reguläre "
                "Teilnehmer abgestimmt."
            ),
            "saturday": saturday,
            "sunday": sunday,
        }

    if len(viable) == 1:
        chosen = viable[0]
        other = sunday if chosen is saturday else saturday
        return {
            "chosen": chosen,
            "reason": (
                f"Nur der {CHOICE_LABELS[chosen['day']]} erreicht mit "
                f"{chosen['candidate_count']} Interessenten mindestens sechs Teilnehmer; "
                f"am {CHOICE_LABELS[other['day']]} sind es {other['candidate_count']}."
            ),
            "saturday": saturday,
            "sunday": sunday,
        }

    if saturday["zero_point_selected"] != sunday["zero_point_selected"]:
        chosen = max((saturday, sunday), key=lambda result: result["zero_point_selected"])
        reason = (
            f"Der {CHOICE_LABELS[chosen['day']]} ermöglicht mehr Spielern mit 0 Punkten "
            "einen festen Platz."
        )
    elif saturday["selected_points_sum"] != sunday["selected_points_sum"]:
        chosen = min((saturday, sunday), key=lambda result: result["selected_points_sum"])
        reason = (
            f"Die sechs vorgeschlagenen Teilnehmer haben am {CHOICE_LABELS[chosen['day']]} "
            f"mit zusammen {chosen['selected_points_sum']} Punkten die niedrigere Belastung."
        )
    elif saturday["candidate_count"] != sunday["candidate_count"]:
        chosen = max((saturday, sunday), key=lambda result: result["candidate_count"])
        reason = (
            f"Der {CHOICE_LABELS[chosen['day']]} besitzt mit "
            f"{chosen['candidate_count']} Interessenten die größere Absicherung durch die Warteliste."
        )
    else:
        chosen = saturday
        reason = "Beide Tage sind gleichwertig; deshalb wird der Samstag leicht bevorzugt."

    return {
        "chosen": chosen,
        "reason": reason,
        "saturday": saturday,
        "sunday": sunday,
    }
