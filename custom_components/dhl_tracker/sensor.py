import logging
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.storage import Store
from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN, STORAGE_KEY, STORAGE_VERSION

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback
) -> None:
    """Set up DHL Tracker sensor entities from config entry."""
    store = Store(hass, STORAGE_VERSION, STORAGE_KEY)
    data = await store.async_load() or {}
    tracking_ids = data.get("tracking_ids", [])

    # Create sensors from stored tracking IDs
    sensors = [DHLTrackingSensor(tracking_id) for tracking_id in tracking_ids]
    async_add_entities(sensors)

    async def modify_tracking_ids(add: bool, tracking_id: str):
        """Add or remove tracking IDs, persist them, and create/remove sensors."""
        data = await store.async_load() or {}
        tracking_ids = data.get("tracking_ids", [])

        if add and tracking_id not in tracking_ids:
            tracking_ids.append(tracking_id)
            await store.async_save({"tracking_ids": tracking_ids})
            async_add_entities([DHLTrackingSensor(tracking_id)])
            _LOGGER.info("Added DHL tracking ID: %s", tracking_id)

        elif not add and tracking_id in tracking_ids:
            tracking_ids.remove(tracking_id)
            await store.async_save({"tracking_ids": tracking_ids})
            _LOGGER.info("Removed DHL tracking ID: %s", tracking_id)
            # Note: Sensor entity removal not handled here.

    async def handle_add(call: ServiceCall):
        tracking_id = call.data.get("tracking_id")
        if tracking_id:
            await modify_tracking_ids(True, tracking_id)
        else:
            _LOGGER.warning("No tracking_id provided to add_tracking_id service")

    async def handle_remove(call: ServiceCall):
        tracking_id = call.data.get("tracking_id")
        if tracking_id:
            await modify_tracking_ids(False, tracking_id)
        else:
            _LOGGER.warning("No tracking_id provided to remove_tracking_id service")

    # Register the services
    hass.services.async_register(DOMAIN, "add_tracking_id", handle_add)
    hass.services.async_register(DOMAIN, "remove_tracking_id", handle_remove)

