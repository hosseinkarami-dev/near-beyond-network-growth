"""Compatibility exports for source metadata and project paths.

New code should import path/source definitions from their dedicated modules;
fetch operations live in :mod:`fetch`.
"""
from paths import PROJECT_ROOT, RAW_DATA_DIR
from sources import (SOURCES, SOURCES_BY_NAME, Source, SourceName, SourceProvider,
                     get_source, raw_path, source_metadata)
