from homeassistant import config_entries
from homeassistant.helpers.storage import Store
from .const import DOMAIN, STORAGE_KEY, STORAGE_VERSION
import voluptuous as vol

class DHLTrackerOptionsFlowHandler(config_entries.OptionsFlow):
    def __init__(self, config_entry):
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        store = Store(self.hass, STORAGE_VERSION, STORAGE_KEY)
        data = await store.async_load() or {"tracking_ids": []}
        current = data.get("tracking_ids", [])

        if user_input is not None:
            new_ids = [x.strip() for x in user_input["tracking_ids"].split(",") if x.strip()]
            await store.async_save({"tracking_ids": new_ids})
            return self.async_create_entry(title="", data={})

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({
                vol.Optional("tracking_ids", default=", ".join(current)): str
            })
        )

def async_get_options_flow(config_entry):
    return DHLTrackerOptionsFlowHandler(config_entry)
