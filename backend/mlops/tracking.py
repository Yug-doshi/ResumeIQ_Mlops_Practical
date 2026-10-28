
import os
from contextlib import contextmanager
from time import perf_counter

import mlflow


EXPERIMENT_NAME = os.getenv(
    "MLFLOW_EXPERIMENT_NAME",
    "ResumeIQ-Resume-Screening",
)

TRACKING_URI = os.getenv(
    "MLFLOW_TRACKING_URI",
    "sqlite:///mlflow.db",
)


def configure_mlflow():
    """Configure the MLflow tracking server or local store."""
    mlflow.set_tracking_uri(TRACKING_URI)
    mlflow.set_experiment(EXPERIMENT_NAME)


@contextmanager
def track_matching_run(
    *,
    model_name: str,
    scoring_version: str,
    skill_dictionary_version: str,
    uploaded_count: int,
):
    """
    Track one ResumeIQ matching request.

    Never log resume text, filenames, candidate names,
    or personally identifiable information.
    """
    configure_mlflow()
    started = perf_counter()

    with mlflow.start_run(run_name="resume-matching"):
        mlflow.set_tags({
            "project": "ResumeIQ",
            "task": "resume_screening",
        })

        mlflow.log_params({
            "model_name": model_name,
            "scoring_version": scoring_version,
            "skill_dictionary_version": skill_dictionary_version,
            "uploaded_count": uploaded_count,
        })

        metrics = {}

        try:
            yield metrics
        finally:
            metrics["tracking_wrapper_duration_seconds"] = (
                perf_counter() - started
            )

            safe_metrics = {
                key: float(value)
                for key, value in metrics.items()
                if isinstance(value, (int, float))
                and not isinstance(value, bool)
            }

            if safe_metrics:
                mlflow.log_metrics(safe_metrics)
