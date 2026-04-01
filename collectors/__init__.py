# Re-export from base so all collectors can do:
#   from collectors import BaseCollector, ContentItem
from collectors.base import BaseCollector, ContentItem

__all__ = ["BaseCollector", "ContentItem"]
