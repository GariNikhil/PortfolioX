"""Profile details for the Settings > About me page.

The page is read-only: everything it shows comes from this file, so
changing a detail is a code edit. Fields left empty are skipped, which
keeps the page looking finished even when only a name is filled in.

Links are ``(label, url)`` pairs. The page turns each into a button that
opens the address in the default browser when clicked, and does nothing
on its own.
"""

# ------------------------ Your details ------------------------ #
# Fill a value in and the page picks it up; leave it empty to hide it.

NAME = "Demo Investor"

BIO = ""

EMAIL = "<email>"

LINKS = (
    ("GitHub", "https://github.com/GariNikhil"),
    ("Donate", "https://buymeacoffee.com/garinikhil"),
)


def profile_rows(name=NAME, bio=BIO, email=EMAIL, links=LINKS):
    """The fields to display, in order, skipping the ones left blank.

    Returns ``(kind, value)`` pairs where ``kind`` is ``name``, ``bio``,
    ``email`` or ``links``; a ``links`` value is a tuple of ``(label,
    url)`` pairs. Whitespace-only values count as blank, and a link is
    kept only when it has both a label and a url.
    """

    rows = []

    for kind, value in (("name", name), ("bio", bio), ("email", email)):
        text = (value or "").strip()
        if text:
            rows.append((kind, text))

    clean_links = tuple(
        (label.strip(), url.strip())
        for label, url in links or ()
        if (label or "").strip() and (url or "").strip()
    )
    if clean_links:
        rows.append(("links", clean_links))

    return rows
