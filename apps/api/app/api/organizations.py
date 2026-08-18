from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session
from typing import Dict, Optional

from apps.api.app.core.database import get_db
from apps.api.app.core.security import decode_access_token
from apps.api.app.models.organization import Organization
from apps.api.app.models.user import User

from fastapi.security import OAuth2PasswordBearer
from jose import JWTError

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

router = APIRouter()


class OrganizationResponse(BaseModel):
    id: str
    name: str
    slug: str
    metadata: Optional[Dict[str, str]] = None


class CreateOrganizationRequest(BaseModel):
    name: str
    slug: str
    metadata: Optional[Dict[str, str]] = None


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    try:
        claims = decode_access_token(token)
        user_id = str(claims.get("sub"))
    except JWTError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid authentication credentials") from exc

    user = db.scalar(select(User).where(User.id == user_id))
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user


@router.get("/", response_model=list[OrganizationResponse])
def list_organizations(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> list[OrganizationResponse]:
    organizations = db.scalars(select(Organization)).all()
    return [OrganizationResponse(id=str(org.id), name=org.name, slug=org.slug, metadata=org.metadata_payload) for org in organizations]


@router.post("/", response_model=OrganizationResponse, status_code=status.HTTP_201_CREATED)
def create_organization(payload: CreateOrganizationRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> OrganizationResponse:
    existing = db.scalar(select(Organization).where(Organization.slug == payload.slug))
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Organization slug already exists")

    organization = Organization(name=payload.name.strip(), slug=payload.slug.strip(), metadata_payload=payload.metadata)
    db.add(organization)
    db.flush()

    # Auto-create membership for the creating user
    from apps.api.app.models.membership import Membership
    membership = Membership(user_id=current_user.id, organization_id=organization.id, role="admin")
    db.add(membership)
    db.commit()
    db.refresh(organization)
    return OrganizationResponse(id=str(organization.id), name=organization.name, slug=organization.slug, metadata=organization.metadata_payload)
