"""SDK response types."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING
from uuid import UUID

if TYPE_CHECKING:
    from agent_key.client import AgentKeyClient


@dataclass(frozen=True, slots=True)
class ServiceInfo:
    """Visible service entry.

    Attributes
    ----------
    provider : str
        Provider slug.
    name : str
        Human-readable provider name.
    base_url : str
        Upstream base URL.
    """

    provider: str
    name: str
    base_url: str


@dataclass(frozen=True, slots=True)
class CheckoutResult:
    """Checkout response payload.

    Attributes
    ----------
    checkout_id : UUID
        Checkout identifier.
    api_key : str
        Raw provider key.
    service : str
        Provider slug.
    checked_out_at : datetime
        Checkout issue timestamp.
    expires_at : datetime
        Checkout expiry timestamp.
    note : str
        Server-supplied note about enforcement semantics.
    """

    checkout_id: UUID
    api_key: str
    service: str
    checked_out_at: datetime
    expires_at: datetime
    note: str

    @property
    def ttl_remaining_seconds(self) -> int:
        """Return remaining checkout TTL.

        Returns
        -------
        int
            Remaining TTL in seconds, clamped at zero.
        """
        expires_at = self.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        return max(0, int((expires_at - now).total_seconds()))


@dataclass(frozen=True, slots=True)
class ActiveCheckoutInfo:
    """Active checkout record.

    Attributes
    ----------
    checkout_id : UUID
        Checkout identifier.
    stored_key_id : UUID
        Stored-key identifier.
    policy_id : UUID
        Policy identifier.
    checked_out_at : datetime
        Checkout issue timestamp.
    expires_at : datetime
        Checkout expiry timestamp.
    returned_at : datetime | None
        Early return timestamp.
    revoked_at : datetime | None
        Revocation timestamp.
    """

    checkout_id: UUID
    stored_key_id: UUID
    policy_id: UUID
    checked_out_at: datetime
    expires_at: datetime
    returned_at: datetime | None
    revoked_at: datetime | None


@dataclass(slots=True)
class CheckoutHandle:
    """Context-managed checkout handle.

    Parameters
    ----------
    client : AgentKeyClient
        SDK client that owns the checkout.
    result : CheckoutResult
        Checkout payload.
    auto_return : bool, default=True
        Whether to return checkout on context exit.
    """

    client: "AgentKeyClient"
    result: CheckoutResult
    auto_return: bool = True
    _returned: bool = False

    @property
    def checkout_id(self) -> UUID:
        """Expose the checkout identifier.

        Returns
        -------
        UUID
            Checkout identifier.
        """
        return self.result.checkout_id

    @property
    def api_key(self) -> str:
        """Expose the raw provider key.

        Returns
        -------
        str
            Provider API key.
        """
        return self.result.api_key

    def return_checkout(self) -> None:
        """Return the checkout once.

        Returns
        -------
        None
            Returns the checkout if it is still active.
        """
        if self._returned:
            return
        self.client.return_checkout(self.result.checkout_id)
        self._returned = True

    def __enter__(self) -> "CheckoutHandle":
        """Enter the checkout context.

        Returns
        -------
        CheckoutHandle
            This checkout handle.
        """
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        """Return the checkout on context exit.

        Parameters
        ----------
        exc_type : type[BaseException] | None
            Exception type if raised.
        exc_value : BaseException | None
            Exception instance if raised.
        traceback : object | None
            Exception traceback if raised.

        Returns
        -------
        None
            Returns the checkout when configured.
        """
        _ = (exc_type, exc_value, traceback)
        if self.auto_return:
            self.return_checkout()
