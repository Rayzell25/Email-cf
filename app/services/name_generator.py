"""Random European-looking human-name generator.

Goals (per PRD):
  * Names should look like short, readable European / human names
    (e.g. CasterBington, GerryShiy, OliverBrenton).
  * The combination space must be very large (hundreds of thousands to
    millions), NOT a small static list that repeats quickly.
  * By default names contain no digits.

The generator mixes several patterns and component pools so the realistic
unique space is in the millions.
"""
from __future__ import annotations

import random
from typing import Callable, List

# --- component pools ---------------------------------------------------------
FIRST_NAMES: List[str] = [
    "Caster", "Gerry", "Jerry", "Thomas", "Oliver", "Harry", "Lucas", "Arthur",
    "Oscar", "Henry", "George", "Louis", "Theo", "Noah", "James", "William",
    "Edward", "Charles", "Albert", "Frederick", "Walter", "Victor", "Leonard",
    "Hugo", "Felix", "Julian", "Marcus", "Adrian", "Sebastian", "Vincent",
    "Maximilian", "Benedict", "Gregory", "Nathaniel", "Reginald", "Sterling",
    "Percival", "Bertram", "Cedric", "Desmond", "Everett", "Florian", "Gideon",
    "Horace", "Ignatius", "Jasper", "Lambert", "Mortimer", "Norbert", "Roland",
    "Rupert", "Silas", "Tobias", "Ulrich", "Wallace", "Xavier", "Conrad",
    "Dorian", "Emil", "Garrett", "Hamish", "Lionel", "Magnus", "Octavian",
    "Quentin", "Rowan", "Stellan", "Tristan", "Wendell", "Alaric", "Casper",
    "Dexter", "Edmund", "Ferdinand", "Godfrey", "Hadrian", "Isadore", "Klaus",
    "Leopold", "Maurice", "Nikolai", "Otto", "Phineas", "Reuben", "Soren",
    "Thaddeus", "Valentin", "Wilfred", "Aldous", "Barnaby", "Crispin",
]

LAST_NAMES: List[str] = [
    "Bington", "Brenton", "Wellington", "Brixton", "Kelvin", "Sterling",
    "Grayson", "Wexler", "Hartley", "Marlow", "Vern", "Kelsen", "Weller",
    "Kley", "Vons", "Brixham", "Ashford", "Barlow", "Caldwell", "Dunmore",
    "Eastwood", "Fairbank", "Goldwyn", "Halloway", "Ironwood", "Jennings",
    "Kingsley", "Lockwood", "Merrick", "Northcote", "Oakley", "Pemberton",
    "Quincey", "Radcliffe", "Sinclair", "Thornton", "Underwood", "Vanderly",
    "Whitlock", "Yardley", "Ashby", "Brampton", "Cromwell", "Davenport",
    "Ellsworth", "Farnham", "Granger", "Hawthorne", "Kensington", "Langley",
    "Montgomery", "Norwood", "Pendleton", "Ravenscroft", "Stanton", "Tennyson",
    "Vandermark", "Westbrook", "Aldridge", "Berkeley", "Carrington", "Devereux",
    "Fitzgerald", "Harrington", "Lancaster", "Middleton", "Pennington",
    "Rutherford", "Somerset", "Templeton", "Winchester", "Abernathy",
]

SHORT_SURNAMES: List[str] = [
    "Shiy", "Sger", "Lsr", "Vry", "Kss", "Brn", "Tly", "Wsk", "Grm", "Pvn",
    "Dsk", "Frt", "Glm", "Hns", "Jrk", "Klv", "Lns", "Mrk", "Nvs", "Prs",
    "Qly", "Rsk", "Svn", "Trv", "Vsk", "Wln", "Zby", "Bly", "Cyr", "Dly",
]

SYLLABLES_START: List[str] = [
    "Bel", "Cor", "Dar", "Far", "Gar", "Hal", "Jar", "Kel", "Lor", "Mar",
    "Nor", "Par", "Ral", "Sal", "Tar", "Val", "Wal", "Bran", "Cren", "Dren",
    "Fren", "Gren", "Tren", "Vren", "Wren", "Brem", "Crem", "Drem", "Flem",
]

SYLLABLES_MID: List[str] = [
    "an", "en", "in", "on", "el", "ar", "or", "ir", "al", "ol", "ber", "der",
    "ler", "ner", "ter", "ver", "wen", "ten", "den", "ken", "len", "ven",
]

SYLLABLES_END: List[str] = [
    "ton", "son", "ley", "field", "ford", "wood", "well", "ham", "worth",
    "stone", "burn", "wick", "more", "shaw", "vale", "ridge", "brook", "land",
    "gate", "holt", "by", "thorpe", "den", "combe", "hurst", "mont",
]


def _cap(token: str) -> str:
    return token[:1].upper() + token[1:].lower() if token else token


# --- pattern builders --------------------------------------------------------
def _p_first_last(rnd: random.Random) -> str:
    return _cap(rnd.choice(FIRST_NAMES)) + _cap(rnd.choice(LAST_NAMES))


def _p_first_short(rnd: random.Random) -> str:
    return _cap(rnd.choice(FIRST_NAMES)) + _cap(rnd.choice(SHORT_SURNAMES))


def _p_first_syllable(rnd: random.Random) -> str:
    return _cap(rnd.choice(FIRST_NAMES)) + rnd.choice(SYLLABLES_MID) + rnd.choice(
        SYLLABLES_END
    )


def _p_short_first_last(rnd: random.Random) -> str:
    first = rnd.choice(FIRST_NAMES)[:4]
    return _cap(first) + _cap(rnd.choice(LAST_NAMES))


def _p_first_mid_end(rnd: random.Random) -> str:
    return (
        _cap(rnd.choice(SYLLABLES_START))
        + rnd.choice(SYLLABLES_MID)
        + rnd.choice(SYLLABLES_END)
    )


def _p_two_short(rnd: random.Random) -> str:
    a = rnd.choice(FIRST_NAMES)[:4]
    b = rnd.choice(LAST_NAMES)[:5]
    return _cap(a) + _cap(b)


def _p_first_last_end(rnd: random.Random) -> str:
    # high-cardinality pattern: first + last + ending syllable
    return _cap(rnd.choice(FIRST_NAMES)) + _cap(rnd.choice(LAST_NAMES)) + rnd.choice(
        SYLLABLES_END
    )


_PATTERNS: List[Callable[[random.Random], str]] = [
    _p_first_last,
    _p_first_short,
    _p_first_syllable,
    _p_short_first_last,
    _p_first_mid_end,
    _p_two_short,
    _p_first_last_end,
]


def estimate_space() -> int:
    """Rough lower-bound estimate of the unique name space (sum over patterns)."""
    f, l = len(FIRST_NAMES), len(LAST_NAMES)
    sh = len(SHORT_SURNAMES)
    s, m, e = len(SYLLABLES_START), len(SYLLABLES_MID), len(SYLLABLES_END)
    return (
        f * l            # first_last
        + f * sh         # first_short
        + f * m * e      # first_syllable
        + f * l          # short_first_last
        + s * m * e      # first_mid_end
        + f * l          # two_short
        + f * l * e      # first_last_end  (largest)
    )


def generate_one(rnd: random.Random | None = None) -> str:
    """Generate a single display name (mixed-case, no digits)."""
    rnd = rnd or random
    pattern = rnd.choice(_PATTERNS)
    name = pattern(rnd)
    # keep it readable/short
    if len(name) > 24:
        name = name[:24]
    return name


def generate_batch(
    count: int,
    *,
    exclude_normalized: set[str] | None = None,
    rnd: random.Random | None = None,
    max_attempts: int = 1000,
) -> List[str]:
    """Generate ``count`` display names with no duplicates within the batch and
    none whose normalized form is in ``exclude_normalized``.
    """
    from app.utils.validators import normalize_name

    rnd = rnd or random
    exclude = set(exclude_normalized or set())
    result: List[str] = []
    seen_norm: set[str] = set()
    attempts = 0
    while len(result) < count and attempts < max_attempts:
        attempts += 1
        candidate = generate_one(rnd)
        norm = normalize_name(candidate)
        if not norm or len(norm) < 4:
            continue
        if norm in seen_norm or norm in exclude:
            continue
        seen_norm.add(norm)
        result.append(candidate)
    return result
