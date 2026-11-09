"""Perfiles y roles del panel. Clerk guarda las contraseñas; aquí solo hay identidad y permisos."""
from dataclasses import dataclass

USER_ROLES = ("admin", "operator")


class LastAdminError(Exception):
    """El cambio dejaría al sistema sin ningún admin activo."""


class AdminExistsError(Exception):
    """Ya hay un admin activo y no se pidió crear otro."""


class AccountDeletedError(Exception):
    """La cuenta ya no existe en Clerk: no se puede reactivar."""


class EmailConflictError(Exception):
    """El correo pertenece a otro perfil vigente."""


@dataclass(frozen=True)
class Principal:
    """Quién hace la solicitud. `service` es la clave compartida, sin persona detrás."""
    role: str
    user_id: str | None = None
    service: bool = False


SERVICE = Principal(role="admin", service=True)


@dataclass(frozen=True)
class ClerkIdentity:
    clerk_user_id: str
    email: str
    display_name: str | None
    invited: bool
    invited_role: str


def identity_from_clerk(user: dict) -> ClerkIdentity | None:
    """Traduce un usuario de Clerk; None si no tiene id o correo principal."""
    clerk_user_id = user.get("id")
    primary = user.get("primary_email_address_id")
    email = next((item.get("email_address") for item in user.get("email_addresses") or []
                  if isinstance(item, dict) and item.get("id") == primary), None)
    if not clerk_user_id or not email:
        return None
    # La marca de invitación solo la escribe FastAPI: public_metadata no se edita desde el navegador.
    metadata = (user.get("public_metadata") or {}).get("sentrix") or {}
    role = metadata.get("role")
    names = " ".join(part for part in (user.get("first_name"), user.get("last_name")) if part)
    return ClerkIdentity(clerk_user_id=clerk_user_id, email=email.strip().lower(),
                         display_name=metadata.get("display_name") or names or None,
                         invited=metadata.get("invited") is True,
                         invited_role=role if role in USER_ROLES else "operator")
