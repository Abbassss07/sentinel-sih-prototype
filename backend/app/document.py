"""Small, deterministic TD3 MRZ checks for fictional test documents."""

from __future__ import annotations

from datetime import date

WEIGHTS = (7, 3, 1)


def check_digit(value: str) -> str:
    total = 0
    for index, character in enumerate(value.upper()):
        if character == "<":
            number = 0
        elif character.isdigit():
            number = int(character)
        elif "A" <= character <= "Z":
            number = ord(character) - ord("A") + 10
        else:
            raise ValueError("Unsupported MRZ character")
        total += number * WEIGHTS[index % 3]
    return str(total % 10)


def build_td3(passport_number: str, holder_name: str, birth_date: str, expiry_date: str, sex: str = "<") -> tuple[str, str]:
    parts = holder_name.upper().split()
    surname = parts[-1]
    given_names = "<".join(parts[:-1])
    name_field = f"{surname}<<{given_names}"[:39].ljust(39, "<")
    line_1 = f"P<TST{name_field}"
    number = passport_number.upper().replace("-", "")[:9].ljust(9, "<")
    birth = date.fromisoformat(birth_date).strftime("%y%m%d")
    expiry = date.fromisoformat(expiry_date).strftime("%y%m%d")
    personal = "<" * 14
    line_2_start = f"{number}{check_digit(number)}TST{birth}{check_digit(birth)}{sex}{expiry}{check_digit(expiry)}{personal}{check_digit(personal)}"
    composite = number + check_digit(number) + birth + check_digit(birth) + expiry + check_digit(expiry) + personal + check_digit(personal)
    line_2 = line_2_start + check_digit(composite)
    assert len(line_1) == 44 and len(line_2) == 44
    return line_1, line_2


def inspect_td3(line_1: str, line_2: str, visible_birth_date: str, visible_expiry_date: str, visible_number: str) -> dict:
    if len(line_1) != 44 or len(line_2) != 44 or not line_1.startswith("P<TST"):
        return {"structure_valid": False, "checksums_valid": False, "cross_field_match": False, "fields": {}}
    number = line_2[:9]
    birth = line_2[13:19]
    expiry = line_2[21:27]
    personal = line_2[28:42]
    composite = number + line_2[9] + birth + line_2[19] + expiry + line_2[27] + personal + line_2[42]
    checksums_valid = all((
        check_digit(number) == line_2[9],
        check_digit(birth) == line_2[19],
        check_digit(expiry) == line_2[27],
        check_digit(personal) == line_2[42],
        check_digit(composite) == line_2[43],
    ))
    fields = {
        "passport_number": number.rstrip("<"),
        "birth_date": birth,
        "expiry_date": expiry,
        "nationality": line_2[10:13],
    }
    cross_field_match = all((
        fields["passport_number"] == visible_number.upper().replace("-", ""),
        birth == date.fromisoformat(visible_birth_date).strftime("%y%m%d"),
        expiry == date.fromisoformat(visible_expiry_date).strftime("%y%m%d"),
    ))
    return {"structure_valid": True, "checksums_valid": checksums_valid, "cross_field_match": cross_field_match, "fields": fields}


def synthetic_document(passport_number: str, holder_name: str, issued_birth_date: str, expiry_date: str, presented_birth_date: str | None = None) -> dict:
    presented_birth_date = presented_birth_date or issued_birth_date
    line_1, line_2 = build_td3(passport_number, holder_name, issued_birth_date, expiry_date)
    inspection = inspect_td3(line_1, line_2, presented_birth_date, expiry_date, passport_number)
    return {
        "passport_number": passport_number,
        "holder_name": holder_name,
        "date_of_birth": presented_birth_date,
        "expiry_date": expiry_date,
        "issuer": "Test Passport Authority",
        "mrz_line_1": line_1,
        "mrz_line_2": line_2,
        "mrz": inspection,
    }
