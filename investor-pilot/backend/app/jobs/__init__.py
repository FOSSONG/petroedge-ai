"""Persistent background-job infrastructure for PetroEdge AI."""

from app.jobs.manager import BackgroundJobManager, get_job_manager

__all__ = ["BackgroundJobManager", "get_job_manager"]
