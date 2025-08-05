import logging
import aiohttp
from datetime import timedelta

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed
)
from homeassistant.helpers.storage import Store
from homeassistant.components.sensor import SensorEntity

from .const import DOMAIN, STORAGE_KEY, STORAGE_VERSION, CONF_API_KEY

_LOGGER = logging.getLogger(__name__)
SCAN_INTERVAL = timedelta(minutes=15)

ENTITY_REGISTRY = {}  # For tracking sensor instances


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback
) -> None:
    """Set up DHL tracking sensors."""

    api_key = entry.data.get(CONF_API_KEY)
    store = Store(hass, STORAGE_VERSION, STORAGE_KEY)
    data = await store.async_load() or {}
    tracking_ids = data.get("tracking_ids", [])

    coordinator = DHLTrackerCoordinator(hass, tracking_ids, api_key)
    await coordinator.async_config_entry_first_refresh()

    sensors = []
    for tracking_id in tracking_ids:
        sensor = DHLTrackingSensor(tracking_id, coordinator)
        ENTITY_REGISTRY[tracking_id] = sensor
        sensors.append(sensor)

    async_add_entities(sensors)

    async def modify_tracking_ids(add: bool, tracking_id: str):
        data = await store.async_load() or {}
        tracking_ids = data.get("tracking_ids", [])

        if add and tracking_id not in tracking_ids:
            tracking_ids.append(tracking_id)
            await store.async_save({"tracking_ids": tracking_ids})
            await coordinator.update_ids(tracking_ids)
            sensor = DHLTrackingSensor(tracking_id, coordinator)
            ENTITY_REGISTRY[tracking_id] = sensor
            async_add_entities([sensor])
            _LOGGER.info("Added tracking ID: %s", tracking_id)

        elif not add and tracking_id in tracking_ids:
            tracking_ids.remove(tracking_id)
            await store.async_save({"tracking_ids": tracking_ids})
            await coordinator.update_ids(tracking_ids)
            if tracking_id in ENTITY_REGISTRY:
                sensor = ENTITY_REGISTRY.pop(tracking_id)
                await sensor.async_remove(force_remove=True)
                _LOGGER.info("Removed tracking ID: %s", tracking_id)

    async def handle_add(call: ServiceCall):
        tracking_id = call.data.get("tracking_id")
        if tracking_id:
            await modify_tracking_ids(True, tracking_id)
        else:
            _LOGGER.warning("No tracking_id provided")

    async def handle_remove(call: ServiceCall):
        tracking_id = call.data.get("tracking_id")
        if tracking_id:
            await modify_tracking_ids(False, tracking_id)
        else:
            _LOGGER.warning("No tracking_id provided")

    hass.services.async_register(DOMAIN, "add_tracking_id", handle_add)
    hass.services.async_register(DOMAIN, "remove_tracking_id", handle_remove)

class DHLTrackingSensor(SensorEntity):
    def __init__(self, tracking_id: str, coordinator: "DHLTrackerCoordinator"):
        self._tracking_id = tracking_id
        self.coordinator = coordinator
        self._attr_unique_id = f"dhl_{tracking_id}"
        self._attr_name = f"DHL Package {tracking_id[-4:]}"
        self._attr_native_value = None

    async def async_update(self):
        await self.coordinator.async_request_refresh()

    async def async_added_to_hass(self):
        self.coordinator.async_add_listener(self.async_write_ha_state)

    @property
    def native_value(self):
        data = self.coordinator.data.get(self._tracking_id)
        return data.get("status") if data else "unknown"

    @property
    def extra_state_attributes(self):
        return self.coordinator.data.get(self._tracking_id, {})

class DHLTrackerCoordinator(DataUpdateCoordinator):
    def __init__(self, hass: HomeAssistant, tracking_ids: list[str], api_key: str):
        super().__init__(
            hass,
            _LOGGER,
            name="DHL Tracker Coordinator",
            update_interval=SCAN_INTERVAL,
        )
        self.tracking_ids = tracking_ids
        self.api_key = api_key
        self.session = aiohttp.ClientSession()

    async def update_ids(self, tracking_ids: list[str]):
        self.tracking_ids = tracking_ids
        await self.async_request_refresh()

    async def _async_update_data(self):
        """Fetch tracking info from DHL."""
        result = {}

        for tracking_id in self.tracking_ids:
            try:
                url = f"https://api-eu.dhl.com/track/shipments?trackingNumber={tracking_id}"
                headers = {
                    "DHL-API-Key": self.api_key,
                    "Accept": "application/json"
                }

                async with self.session.get(url, headers=headers) as resp:
                    if resp.status != 200:
                        raise UpdateFailed(f"DHL API error {resp.status}")
                    response = await resp.json()

                shipments = response.get("shipments", [])
                if shipments:
                    latest = shipments[0]
                    status = latest.get("status", {}).get("statusCode", "unknown")
                    result[tracking_id] = {
                        "status": status,
                        "description": latest.get("status", {}).get("status"),
                        "origin": latest.get("origin", {}).get("address", {}).get("addressLocality"),
                        "destination": latest.get("destination", {}).get("address", {}).get("addressLocality"),
                        "estimated_delivery": latest.get("estimatedTimeOfDelivery"),
                        "tracking_id": tracking_id,
                    }
                else:
                    result[tracking_id] = {"status": "not_found", "tracking_id": tracking_id}

            except Exception as e:
                _LOGGER.error("Failed to fetch tracking info for %s: %s", tracking_id, e)
                result[tracking_id] = {"status": "error", "tracking_id": tracking_id}

        return result


