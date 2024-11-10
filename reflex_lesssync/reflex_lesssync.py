"""Welcome to Reflex! This file outlines the steps to create a basic app."""
import asyncio
import functools
import json
import os
import time
from collections.abc import AsyncGenerator

import reflex as rx
from google.auth.transport import requests
from google.oauth2.id_token import verify_oauth2_token

from reflex_lesssync.google_auth import GoogleOAuthProvider, GoogleLogin

CLIENT_ID = os.getenv("G_CLIENT_ID", "")

class State(rx.State):
    id_token_json: rx.Field[str] = rx.LocalStorage()
    background_state: rx.Field[str] = rx.field("")

    @rx.var
    def g_client_id(self) -> str:
        return CLIENT_ID

    def on_success(self, id_token: dict):
        self.id_token_json = json.dumps(id_token)

    @rx.var(cache=True)
    def tokeninfo(self) -> dict[str, str]:
        try:
            return verify_oauth2_token(
                json.loads(self.id_token_json)[
                    "credential"
                ],
                requests.Request(),
                self.g_client_id,
            )
        except Exception as exc:
            if self.id_token_json:
                print(f"Error verifying token: {exc}")
        return {}

    def logout(self):
        self.id_token_json = ""

    @rx.var
    def token_is_valid(self) -> bool:
        try:
            return bool(
                self.tokeninfo
                and int(self.tokeninfo.get("exp", 0))
                > time.time()
            )
        except Exception:
            return False

    @rx.var(cache=True)
    def protected_content(self) -> str:
        if self.token_is_valid:
            return f"This content can only be viewed by a logged in User. Nice to see you {self.tokeninfo['name']}"
        return "Not logged in."

    @rx.background
    async def poll_user_data(self) -> AsyncGenerator[None, None]:
        """
        This is a example background task that runs every 1 seconds.
        """
        while self.router.session.client_token in app.event_namespace.token_to_sid:
            await asyncio.sleep(1)
            async with self:
                if not self.token_is_valid:
                    self.background_state = "not logged in"
                    continue

            # Polling db or any other resources

            async with self:
                self.background_state = "logged in as " + self.tokeninfo["name"]



def user_info(tokeninfo: dict, background_state: str) -> rx.Component:
    return rx.hstack(
        rx.avatar(
            name=tokeninfo["name"],
            src=tokeninfo["picture"],
            size="lg",
        ),
        rx.vstack(
            rx.heading(tokeninfo["name"], size="md"),
            rx.text(background_state),
            align_items="flex-start",
        ),
        rx.button("Logout", on_click=State.logout),
        padding="10px",
    )


def login() -> rx.Component:
    return rx.vstack(
        GoogleLogin.create(on_success=State.on_success),
    )


def require_google_login(page) -> rx.Component:
    @functools.wraps(page)
    def _auth_wrapper() -> rx.Component:
        return GoogleOAuthProvider.create(
            rx.cond(
                State.is_hydrated,
                rx.cond(
                    State.token_is_valid, page(), login()
                ),
                rx.spinner(),
            ),
            client_id=State.g_client_id,
        )

    return _auth_wrapper


def index():
    return rx.vstack(
        rx.heading("Google OAuth", size="lg"),
        rx.link("Protected Page", href="/protected"),
    )


@rx.page(route="/protected")
@require_google_login
def protected() -> rx.Component:
    return rx.vstack(
        # Pass background state
        user_info(State.tokeninfo, State.background_state),
        rx.text(State.protected_content),
        rx.link("Home", href="/"),
        # Begin background task
        on_mount=State.poll_user_data,
    )


app = rx.App()
app.add_page(index)


