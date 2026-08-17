from __future__ import annotations

import base64
import hashlib
import hmac
import json
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api.app.api.organizations import get_current_user
from apps.api.app.core.config import settings
from apps.api.app.core.database import get_db
from apps.api.app.models.integration import Integration, IntegrationStatus, OAuthCredential
from apps.api.app.models.membership import Membership
from apps.api.app.models.user import User
from packages.integrations.base import OAuthTokenSet
from packages.integrations.credentials import CredentialRecord, CredentialStore
from packages.integrations.sync import GoogleDriveSyncService

router = APIRouter()
credential_store = CredentialStore()
drive_sync_service = GoogleDriveSyncService()


class IntegrationResponse(BaseModel):
    provider: str
    status: str
    account: Optional[str] = None
    metadata: dict[str, Any] | None = None


def _organization_id_for_user(db: Session, user: User) -> str:
    membership = db.scalar(select(Membership).where(Membership.user_id == user.id).limit(1))
    if membership is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User has no organization access")
    return str(membership.organization_id)


def _encode_state(payload: dict[str, Any]) -> str:
    body = base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode("utf-8")).decode("utf-8")
    sig = hmac.new(settings.jwt_secret_key.encode("utf-8"), body.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{body}.{sig}"


def _decode_state(state: str) -> dict[str, Any]:
    try:
        body, sig = state.split(".", 1)
        expected = hmac.new(settings.jwt_secret_key.encode("utf-8"), body.encode("utf-8"), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected):
            raise ValueError("state signature mismatch")
        payload = json.loads(base64.urlsafe_b64decode(body.encode("utf-8")).decode("utf-8"))
        if payload.get("exp", 0) < datetime.now(timezone.utc).timestamp():
            raise ValueError("state expired")
        return payload
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid callback state") from exc


def _upsert_integration(
    db: Session,
    organization_id: str,
    provider: str,
    user: User,
) -> Integration:
    integration = db.scalar(
        select(Integration).where(Integration.organization_id == organization_id, Integration.provider == provider)
    )
    if integration is None:
        integration = Integration(
            organization_id=organization_id,
            provider=provider,
            integration_type="business",
            status=IntegrationStatus.DISCONNECTED,
            account_identifier=None,
            display_name=None,
            created_by=str(user.id),
            name=provider,
        )
        db.add(integration)
        db.commit()
        db.refresh(integration)
    return integration


def _save_credentials(db: Session, integration: Integration, token_set: OAuthTokenSet) -> None:
    record = CredentialRecord(
        access_token=token_set.access_token,
        refresh_token=token_set.refresh_token,
        expires_at=token_set.expires_at,
        scopes=token_set.scopes,
    )
    db_cred = db.scalar(select(OAuthCredential).where(OAuthCredential.integration_id == integration.id))
    encrypted_payload = credential_store.encrypt_payload(
        {
            "access_token": record.access_token,
            "refresh_token": record.refresh_token,
            "expires_at": record.expires_at.isoformat() if record.expires_at else None,
            "scopes": list(record.scopes),
        }
    )
    if db_cred is None:
        db_cred = OAuthCredential(
            integration_id=integration.id,
            encrypted_access_token=encrypted_payload,
            encrypted_refresh_token=None,
            expires_at=token_set.expires_at,
            scopes=" ".join(token_set.scopes),
        )
        db.add(db_cred)
    else:
        db_cred.encrypted_access_token = encrypted_payload
        db_cred.encrypted_refresh_token = None
        db_cred.expires_at = token_set.expires_at
        db_cred.scopes = " ".join(token_set.scopes)
    db.commit()


def _load_token_set(db: Session, integration: Integration) -> OAuthTokenSet:
    credential = db.scalar(select(OAuthCredential).where(OAuthCredential.integration_id == integration.id))
    if credential is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Connection reauthorization required")
    payload = credential_store.decrypt_payload(credential.encrypted_access_token)
    return OAuthTokenSet(
        access_token=str(payload["access_token"]),
        refresh_token=str(payload["refresh_token"]) if payload.get("refresh_token") else None,
        expires_at=datetime.fromisoformat(str(payload["expires_at"])) if payload.get("expires_at") else None,
        scopes=tuple(payload.get("scopes") or ()),
    )


@router.get("")
async def list_integrations(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> list[IntegrationResponse]:
    organization_id = _organization_id_for_user(db, current_user)
    integrations = db.scalars(select(Integration).where(Integration.organization_id == organization_id)).all()
    return [
        IntegrationResponse(
            provider=i.provider,
            status=getattr(i.status, "value", i.status),
            account=i.account_identifier,
            metadata=i.metadata_payload or {},
        )
        for i in integrations
    ]


@router.get("/{provider}")
async def get_integration(provider: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> IntegrationResponse:
    organization_id = _organization_id_for_user(db, current_user)
    integration = db.scalar(
        select(Integration).where(Integration.organization_id == organization_id, Integration.provider == provider)
    )
    if integration is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Integration not found")
    return IntegrationResponse(
        provider=integration.provider,
        status=getattr(integration.status, "value", integration.status),
        account=integration.account_identifier,
        metadata=integration.metadata_payload or {},
    )


@router.post("/{provider}/connect")
async def connect_integration(provider: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> dict[str, Any]:
    organization_id = _organization_id_for_user(db, current_user)
    integration = _upsert_integration(db, organization_id, provider, current_user)
    state = _encode_state(
        {
            "provider": provider,
            "organization_id": organization_id,
            "user_id": str(current_user.id),
            "nonce": hashlib.sha256(f"{current_user.id}:{provider}:{datetime.now(timezone.utc).isoformat()}".encode()).hexdigest(),
            "exp": (datetime.now(timezone.utc) + timedelta(minutes=10)).timestamp(),
        }
    )
    return {
        "provider": provider,
        "authorization_url": f"/api/integrations/{provider}/oauth/callback?state={state}&code=mock_code",
        "scopes": integration.metadata_payload.get("scopes", []) if integration.metadata_payload else [],
    }


@router.get("/{provider}/oauth/callback")
async def oauth_callback(
    provider: str,
    state: str | None = None,
    code: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    if not state or not code:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid callback")
    payload = _decode_state(state)
    if payload.get("provider") != provider or payload.get("user_id") != str(current_user.id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="State mismatch")
    organization_id = _organization_id_for_user(db, current_user)
    if payload.get("organization_id") != organization_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="State mismatch")

    integration = _upsert_integration(db, organization_id, provider, current_user)
    token_set = OAuthTokenSet(
        access_token=hashlib.sha256(f"{provider}:{code}:{datetime.now(timezone.utc).isoformat()}".encode()).hexdigest(),
        refresh_token=hashlib.sha256(f"refresh:{code}:{provider}".encode()).hexdigest(),
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        scopes=("https://www.googleapis.com/auth/userinfo.email",),
    )
    integration.status = IntegrationStatus.CONNECTED
    integration.account_identifier = current_user.email
    integration.display_name = current_user.name
    integration.last_sync_at = datetime.now(timezone.utc)
    integration.metadata_payload = {"scopes": list(token_set.scopes)}
    _save_credentials(db, integration, token_set)
    return {"provider": provider, "status": "CONNECTED", "account": current_user.email}


@router.post("/{provider}/disconnect")
async def disconnect_integration(provider: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> dict[str, str]:
    organization_id = _organization_id_for_user(db, current_user)
    integration = db.scalar(
        select(Integration).where(Integration.organization_id == organization_id, Integration.provider == provider)
    )
    if integration is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Integration not found")
    integration.status = IntegrationStatus.DISCONNECTED
    credential = db.scalar(select(OAuthCredential).where(OAuthCredential.integration_id == integration.id))
    if credential is not None:
        db.delete(credential)
    db.commit()
    return {"status": "DISCONNECTED"}


@router.post("/{provider}/health")
async def health(provider: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> dict[str, Any]:
    organization_id = _organization_id_for_user(db, current_user)
    integration = db.scalar(
        select(Integration).where(Integration.organization_id == organization_id, Integration.provider == provider)
    )
    if integration is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Integration not found")
    return {"provider": provider, "status": getattr(integration.status, "value", integration.status), "account": integration.account_identifier}


@router.post("/google-drive/sync")
async def sync_google_drive(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> dict[str, Any]:
    organization_id = _organization_id_for_user(db, current_user)
    integration = db.scalar(
        select(Integration).where(Integration.organization_id == organization_id, Integration.provider == "google_drive")
    )
    if integration is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Google Drive integration not found")
    token_set = _load_token_set(db, integration)
    result = await drive_sync_service.sync(db=db, organization_id=organization_id, token_set=token_set)
    integration.last_sync_at = datetime.now(timezone.utc)
    integration.status = IntegrationStatus.CONNECTED
    db.commit()
    return {"provider": "google_drive", "scanned": result.scanned, "ingested": result.ingested, "skipped": result.skipped}
