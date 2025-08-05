from homeassistant.core import HomeAssistant, ServiceCall
from .const import DOMAIN, STORAGE_KEY, STORAGE_VERSION
from homeassistant.helpers.storage import Store
import json

async def async_setup(hass: HomeAssistant, config: dict):
    store = Store(hass, STORAGE_VERSION, STORAGE_KEY)
    if (existing := await store.async_load()) is None:
        await store.async_save({"tracking_ids": []})

    async def modify_tracking_ids(add: bool, tracking_id: str):
        data = await store.async_load()
        tracking_ids = data.get("tracking_ids", [])
        if add and tracking_id not in tracking_ids:
            tracking_ids.append(tracking_id)
        elif not add and tracking_id in tracking_ids:
            tracking_ids.remove(tracking_id)
        await store.async_save({"tracking_ids": tracking_ids})

    async def handle_add(call: ServiceCall):
        await modify_tracking_ids(True, call.data["tracking_id"])

    async def handle_remove(call: ServiceCall):
        await modify_tracking_ids(False, call.data["tracking_id"])

    hass.services.async_register(DOMAIN, "add_tracking_id", handle_add)
    hass.services.async_register(DOMAIN, "remove_tracking_id", handle_remove)
    return True

async def async_setup_entry(hass: HomeAssistant, entry):
    """Set up DHL Tracker from a config entry."""
    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(entry, "sensor")
    )
    return True

async def async_unload_entry(hass: HomeAssistant, entry):
    """Unload a config entry."""
    return await hass.config_entries.async_forward_entry_unload(entry, "sensor")
