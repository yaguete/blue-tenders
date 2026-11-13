"""Cita del texto nuevo en una página vigilada. Lo que ya estaba no cuenta."""


def change_quote(current: str, previous: str, limit: int = 4000) -> str:
    if not previous:
        return current[:limit]
    current_words = current.split()
    previous_words = set(previous.split())
    fresh = [word for word in current_words if word not in previous_words]
    text = " ".join(fresh).strip()
    return (text or current)[:limit]
