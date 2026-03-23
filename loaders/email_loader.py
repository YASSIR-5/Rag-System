import mailparser


def load_email(path: str) -> str:
    mail = mailparser.parse_from_file(path)
    parts = []

    if mail.from_:
        parts.append(f"From: {mail.from_}")
    if mail.to:
        parts.append(f"To: {mail.to}")
    if mail.date:
        parts.append(f"Date: {mail.date}")
    if mail.subject:
        parts.append(f"Subject: {mail.subject}")

    parts.append("")  # blank line separator
    parts.append(mail.body or "")

    return "\n".join(parts)
