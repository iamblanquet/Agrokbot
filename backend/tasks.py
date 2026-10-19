"""Shared completion rule for capture and daily notifications."""


def completed(task):
    progress = task.get('progressBps')
    return task.get('status') in ('FINISHED', 'COMPLETED') or (
        isinstance(progress, (int, float)) and progress >= 10000)
