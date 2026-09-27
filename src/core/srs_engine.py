"""
SuperMemo-2 (SM-2) spaced-repetition algorithm.

`grade_review()` takes a card's current SRS state plus a user grade
and returns the updated state to persist via
`queries.record_review()`.
"""
from datetime import date, timedelta
from typing import Union

# Quiz buttons mapped to SM-2 quality scores. "Again" (forgot it) is a
# failing grade and resets the card; Hard/Good/Easy are passing grades
# that grow the interval. Raw 0-5 scores are also accepted directly.
GRADE_TO_QUALITY = {
    "Again": 1,
    "Hard": 3,
    "Good": 4,
    "Easy": 5,
}


def grade_review(
    easiness_factor: float,
    interval_days: int,
    repetition_number: int,
    grade: Union[str, int],
    today: date,
) -> dict:
    """Compute the next SM-2 state after a review.

    `grade` may be "Again"/"Hard"/"Good"/"Easy" or a raw quality score
    (0-5). A quality below 3 resets the repetition count so the card
    starts over from a 1-day interval.
    """
    quality = GRADE_TO_QUALITY[grade] if isinstance(grade, str) else int(grade)
    quality = max(0, min(5, quality))

    if quality < 3:
        repetition_number = 0
        interval_days = 1
    else:
        if repetition_number == 0:
            interval_days = 1
        elif repetition_number == 1:
            interval_days = 6
        else:
            interval_days = round(interval_days * easiness_factor)
        repetition_number += 1

    easiness_factor = easiness_factor + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02))
    easiness_factor = max(1.3, round(easiness_factor, 2))

    return {
        "repetition_number": repetition_number,
        "easiness_factor": easiness_factor,
        "interval_days": interval_days,
        "next_review_date": (today + timedelta(days=interval_days)).isoformat(),
    }
