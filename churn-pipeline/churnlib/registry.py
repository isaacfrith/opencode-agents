"""Thin helpers over the MLflow Model Registry, encoding the @champion contract.

See ``docs/adr/0002-serving-via-mlflow-champion-alias.md``.
"""

from __future__ import annotations

import mlflow
from mlflow.entities.model_registry import ModelVersion
from mlflow.tracking import MlflowClient

from . import config


def client() -> MlflowClient:
    mlflow.set_tracking_uri(config.tracking_uri())
    return MlflowClient()


def champion() -> ModelVersion | None:
    """The model version currently carrying the ``@champion`` alias, if any."""
    try:
        return client().get_model_version_by_alias(
            config.REGISTERED_MODEL, config.CHAMPION_ALIAS
        )
    except Exception:
        return None


def champion_uri() -> str:
    """The registry URI the API loads from."""
    return f"models:/{config.REGISTERED_MODEL}@{config.CHAMPION_ALIAS}"


def champion_threshold() -> float:
    """Decision threshold stored on the champion version (defaults to 0.5)."""
    version = champion()
    if version is None:
        return config.DEFAULT_THRESHOLD
    return float(version.tags.get(config.THRESHOLD_TAG, config.DEFAULT_THRESHOLD))


def latest_version() -> int:
    versions = client().search_model_versions(f"name='{config.REGISTERED_MODEL}'")
    if not versions:
        raise RuntimeError(
            f"No versions of '{config.REGISTERED_MODEL}' found in the registry."
        )
    return max(int(v.version) for v in versions)


def promote(version: int) -> None:
    """Point the ``@champion`` alias at ``version`` (see ``make promote``)."""
    client().set_registered_model_alias(
        config.REGISTERED_MODEL, config.CHAMPION_ALIAS, version
    )
