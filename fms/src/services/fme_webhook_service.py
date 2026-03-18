"""FME Flow webhook service."""
from __future__ import annotations

from typing import Any

import requests

from src.core.exceptions import FMEWebhookError
from src.core.logger import get_logger

logger = get_logger(__name__)


class FMEWebhookService:
    """
    Sends payloads to FME Flow via webhook endpoint.

    Parameters
    ----------
    webhook_url : str
        Target FME Flow webhook URL.
    timeout_s : int
        Request timeout in seconds.
    """

    def __init__(self, webhook_url: str, timeout_s: int = 60) -> None:
        self.webhook_url = webhook_url
        self.timeout_s = timeout_s

    def trigger(self, payload: dict[str, Any]) -> dict[str, Any]:
        """
        Trigger the FME Flow webhook.

        Parameters
        ----------
        payload : dict[str, Any]
            JSON payload to send.

        Returns
        -------
        dict[str, Any]
            Parsed JSON response or status dict.

        Raises
        ------
        FMEWebhookError
            If the request fails or returns a non-2xx status.
        """
        try:
            logger.info("Calling FME webhook: %s", self.webhook_url)
            resp = requests.post(self.webhook_url, json=payload, timeout=self.timeout_s)
            resp.raise_for_status()
            if resp.headers.get("content-type", "").lower().startswith("application/json"):
                return resp.json()
            return {"status_code": resp.status_code, "text": resp.text}
        except requests.RequestException as exc:
            logger.error("FME webhook request failed: %s", exc, exc_info=True)
            raise FMEWebhookError("FME webhook call failed") from exc
