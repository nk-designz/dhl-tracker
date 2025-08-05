from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from datetime import timedelta
import aiohttp
import async_timeout

class DHLDataCoordinator(DataUpdateCoordinator):
    def __init__(self, hass, api_key, tracking_ids):
        super().__init__(hass, _LOGGER, name="DHL Tracker", update_interval=timedelta(minutes=30))
        self.api_key = api_key
        self.tracking_ids = tracking_ids

    async def _async_update_data(self):
        results = {}
        headers = {
            "DHL-API-Key": self.api_key,
            "Accept": "application/json"
        }
        async with aiohttp.ClientSession(headers=headers) as session:
            for tracking_id in self.tracking_ids:
                try:
                    async with async_timeout.timeout(10):
                        url = f"https://api-eu.dhl.com/track/shipments?trackingNumber={tracking_id}"
                        async with session.get(url) as response:
                            data = await response.json()
                            results[tracking_id] = data
                except Exception as e:
                    results[tracking_id] = {"error": str(e)}
        return results
