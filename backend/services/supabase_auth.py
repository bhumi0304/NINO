import json
import os

from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from dotenv import load_dotenv


# =========================================================
# ENVIRONMENT
# =========================================================

PROJECT_ROOT = (
    Path(__file__)
    .resolve()
    .parents[2]
)

load_dotenv(
    PROJECT_ROOT
    / ".env"
)


SUPABASE_URL = (
    os.getenv(
        "SUPABASE_URL",
        "",
    )
    .strip()
    .rstrip("/")
)


SUPABASE_PUBLISHABLE_KEY = (
    os.getenv(
        "SUPABASE_PUBLISHABLE_KEY",
        ""
    )
    .strip()
)


if not SUPABASE_URL:
    raise RuntimeError(
        "SUPABASE_URL is missing from .env"
    )


if not SUPABASE_PUBLISHABLE_KEY:
    raise RuntimeError(
        "SUPABASE_PUBLISHABLE_KEY "
        "is missing from .env"
    )


# =========================================================
# TOKEN VERIFICATION
# =========================================================

def verify_access_token(
    access_token,
):
    """
    Verify a Supabase user access token.

    Supabase Auth validates the JWT and returns
    the actual authenticated user.

    Returns
    -------
    dict
        {
            "id": "...",
            "email": "...",
            "user_metadata": {...},
            ...
        }

    Raises
    ------
    ValueError
        If the JWT is missing, expired or invalid.
    """

    if not access_token:

        raise ValueError(
            "Missing access token."
        )


    url = (
        f"{SUPABASE_URL}"
        "/auth/v1/user"
    )


    request = Request(
        url,

        method="GET",

        headers={
            "apikey":
                SUPABASE_PUBLISHABLE_KEY,

            "Authorization":
                f"Bearer {access_token}",

            "Accept":
                "application/json",
        },
    )


    try:

        with urlopen(
            request,
            timeout=10,
        ) as response:

            raw_data = (
                response
                .read()
                .decode(
                    "utf-8"
                )
            )


    except HTTPError as error:

        try:

            error_body = (
                error
                .read()
                .decode(
                    "utf-8"
                )
            )

            error_data = (
                json.loads(
                    error_body
                )
            )

            message = (
                error_data.get(
                    "msg"
                )
                or
                error_data.get(
                    "message"
                )
                or
                "Invalid authentication token."
            )

        except Exception:

            message = (
                "Invalid authentication token."
            )


        raise ValueError(
            message
        )


    except Exception as error:

        raise ValueError(
            "Could not verify "
            "Supabase authentication."
        ) from error


    try:

        user = json.loads(
            raw_data
        )

    except json.JSONDecodeError as error:

        raise ValueError(
            "Invalid Supabase user response."
        ) from error


    user_id = (
        user.get(
            "id"
        )
    )


    if not user_id:

        raise ValueError(
            "Supabase user ID missing."
        )


    return user


# =========================================================
# PROFILE HELPERS
# =========================================================

def get_display_name(
    user,
):
    """
    Extract user's NINO display name.
    """

    metadata = (
        user.get(
            "user_metadata"
        )
        or
        {}
    )


    full_name = (
        metadata.get(
            "full_name"
        )
        or
        metadata.get(
            "name"
        )
    )


    if full_name:

        return str(
            full_name
        ).strip()


    email = (
        user.get(
            "email"
        )
        or
        ""
    )


    if email:

        return (
            email
            .split("@")[0]
        )


    return "NINO User"