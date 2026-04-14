"""
app/requests/routes.py

This blueprint used to contain stub routes that duplicated and OVERRODE the
real routes in `app/main` (because it was registered after `main`).

BUG FIX: Removed all duplicate route stubs. The `/request_form` and `/status`
routes are fully implemented in `app/main/routes.py` and are reached there.
This blueprint is kept in case future request-specific sub-routes are needed.
"""
from app.requests import bp  # noqa: F401 — blueprint registration kept
