from homeassistant.helpers.entity import Entity
from .const import DOMAIN

import aiohttp

async def async_setup_entry(hass, config_entry, async_add_entities):
    store = hass.helpers.storage.Store(1, f"{DOMAIN}_data")
    data = await store.async_load() or {"tracking_ids": []}
    tracking_ids = data.get("tracking_ids", [])
    api_key = config_entry.data.get("api_key")

    entities = [DHLTrackerSensor(tid, api_key) for tid in tracking_ids]
    async_add_entities(entities)


class DHLTrackerSensor(Entity):
    def __init__(self, tracking_id, api_key):
        self._tracking_id = tracking_id
        self._api_key = api_key
        self._state = "unknown"
        self._attrs = {}

    @property
    def name(self):
        return f"DHL {self._tracking_id}"

    @property
    def unique_id(self):
        return f"dhl_{self._tracking_id.lower()}"

    @property
    def state(self):
        return self._state

    @property
    def extra_state_attributes(self):
        return self._attrs

    async def async_update(self):
        url = f"https://api-eu.dhl.com/track/shipments?trackingNumber={self._tracking_id}"
        headers = {"DHL-API-Key": self._api_key}

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, timeout=10) as response:
                    if response.status == 200:
                        data = await response.json()
                        shipment = data.get("shipments", [{}])[0]
                        status = shipment.get("status", {}).get("statusCode", "unknown")
                        eta = shipment.get("estimatedTimeOfDelivery", "")
                        self._state = status
                        self._attrs = {
                            "eta": eta,
                            "tracking_number": self._tracking_id
                        }
                    else:
                        self._state = f"error {response.status}"
        except Exception as e:
            self._state = "error"
            self._attrs = {"error": str(e)}
