from __future__ import annotations

import os
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

import requests


class SecretConfigurationError(RuntimeError):
    """Raised when required secrets are unavailable or unsafe."""


class SecretProvider(ABC):
    @abstractmethod
    def get_secret(self, name: str) -> Optional[str]:
        raise NotImplementedError


class EnvSecretProvider(SecretProvider):
    def get_secret(self, name: str) -> Optional[str]:
        value = os.getenv(name)
        if value is None:
            return None
        stripped = value.strip()
        return stripped if stripped else None


class VaultSecretProvider(SecretProvider):
    """Vault-ready provider (generic HTTP endpoint shape)."""

    def __init__(self) -> None:
        self.base_url = os.getenv("SECRET_VAULT_URL", "").strip()
        self.token = os.getenv("SECRET_VAULT_TOKEN", "").strip()
        self.path_template = os.getenv("SECRET_VAULT_PATH_TEMPLATE", "/v1/secret/data/{name}").strip()
        self.timeout_seconds = int(os.getenv("SECRET_VAULT_TIMEOUT_SECONDS", "5"))

    def get_secret(self, name: str) -> Optional[str]:
        if not self.base_url or not self.token:
            return None

        url = f"{self.base_url.rstrip('/')}{self.path_template.format(name=name)}"
        headers = {"Authorization": f"Bearer {self.token}"}
        try:
            response = requests.get(url, headers=headers, timeout=self.timeout_seconds)
        except requests.RequestException as exc:
            raise SecretConfigurationError("Secret backend unavailable") from exc

        if response.status_code == 404:
            return None
        if response.status_code >= 400:
            raise SecretConfigurationError("Secret backend returned error")

        payload = response.json()
        data = payload.get("data") if isinstance(payload, dict) else None
        if isinstance(data, dict):
            nested = data.get("data")
            if isinstance(nested, dict) and name in nested:
                value = nested.get(name)
                return str(value).strip() if value is not None and str(value).strip() else None
            if name in data:
                value = data.get(name)
                return str(value).strip() if value is not None and str(value).strip() else None
        return None


@dataclass
class SecretRule:
    name: str
    min_length: int = 16


class SecretLoader:
    def __init__(self) -> None:
        backend_name = os.getenv("SECRET_BACKEND", "env").strip().lower()
        self.backend_name = backend_name
        if backend_name == "vault":
            self.provider: SecretProvider = VaultSecretProvider()
        else:
            self.provider = EnvSecretProvider()

    def get_secret(self, name: str) -> str:
        value = self.provider.get_secret(name)
        if value is None:
            raise SecretConfigurationError(f"Missing secret '{name}'")
        return value

    def validate_secret(self, rule: SecretRule) -> None:
        value = self.get_secret(rule.name)
        if len(value) < rule.min_length:
            raise SecretConfigurationError(f"Secret '{rule.name}' is too short")
        if value.lower() in {"changeme", "secret", "password", "default"}:
            raise SecretConfigurationError(f"Secret '{rule.name}' is weak")

    def validate_live_requirements(self, rules: list[SecretRule]) -> None:
        for rule in rules:
            self.validate_secret(rule)


_secret_loader: Optional[SecretLoader] = None


def get_secret_loader() -> SecretLoader:
    global _secret_loader
    if _secret_loader is None:
        _secret_loader = SecretLoader()
    return _secret_loader
