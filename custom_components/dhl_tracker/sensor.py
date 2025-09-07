import logging
import aiohttp
from datetime import timedelta

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.helpers.storage import Store
from homeassistant.components.sensor import SensorEntity

from .const import DOMAIN, STORAGE_KEY, STORAGE_VERSION, CONF_API_KEY

_LOGGER = logging.getLogger(__name__)
SCAN_INTERVAL = timedelta(minutes=15)

ENTITY_REGISTRY = {}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback
) -> None:
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

    async def handle_force_update(call: ServiceCall):
        await coordinator.async_request_refresh()
        _LOGGER.info("Manual update triggered")

    async def handle_remove_entity(call: ServiceCall):
        tracking_id = call.data.get("tracking_id")
        if tracking_id:
            await modify_tracking_ids(False, tracking_id)
        else:
            _LOGGER.warning("No tracking_id provided to remove_entity")

    hass.services.async_register(DOMAIN, "add_tracking_id", handle_add)
    hass.services.async_register(DOMAIN, "remove_tracking_id", handle_remove)
    hass.services.async_register(DOMAIN, "update", handle_force_update)
    hass.services.async_register(DOMAIN, "remove_entity", handle_remove_entity)


class DHLTrackingSensor(SensorEntity):
    def __init__(self, tracking_id: str, coordinator: "DHLTrackerCoordinator"):
        self._tracking_id = str(tracking_id)
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
                    status_info = latest.get("status", {})
                    status = status_info.get("statusCode", "unknown")
                    description = status_info.get("description", "No description")
                    timestamp = status_info.get("timestamp")

                    result[tracking_id] = {
                        "status": status,
                        "description": description,
                        "origin": latest.get("origin", {}).get("address", {}).get("addressLocality"),
                        "destination": latest.get("destination", {}).get("address", {}).get("addressLocality"),
                        "estimated_delivery": latest.get("estimatedTimeOfDelivery"),
                        "tracking_id": tracking_id,
                        "url": latest.get("serviceUrl"),
                        "last_updated": timestamp,
                    }

                    _LOGGER.info("Updated tracking ID %s: %s - %s", tracking_id, status, description)

                else:
                    result[tracking_id] = {
                        "status": "not_found",
                        "tracking_id": tracking_id,
                        "description": "No shipment found",
                        "last_updated": None,
                        "url": f"https://www.dhl.de/en/privatkunden.html?piececode={tracking_id}",
                    }
                    _LOGGER.warning("Tracking ID %s not found in DHL API", tracking_id)

            except Exception as e:
                _LOGGER.error("Failed to fetch tracking info for %s: %s", tracking_id, e)
                result[tracking_id] = {
                    "status": "error",
                    "tracking_id": tracking_id,
                    "description": str(e),
                    "last_updated": None,
                    "url": f"https://www.dhl.de/en/privatkunden.html?piececode={tracking_id}",
                }

        return result
