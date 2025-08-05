# DHL Tracker for Home Assistant

Track your DHL packages directly in Home Assistant using the official DHL API. Supports UI-based setup, automatic sensors, and a custom Lovelace card.

## Features
- 📦 Track multiple DHL shipments
- 🎛️ Add/remove tracking numbers via UI
- 🔁 Auto-updates every 30 minutes
- 🧠 Automations and voice assistant support
- 🖼️ Beautiful custom Lovelace card

## Installation

### Manual
1. Copy `custom_components/dhl_tracker` to your Home Assistant `custom_components/` folder.
2. Copy `www/community/dhl-tracker-card/` to your `www/community/` folder.
3. Restart Home Assistant.

### Via HACS *(optional)*
1. Add this repository to HACS as a custom repository.
2. Install both the integration and the Lovelace card.
3. Restart Home Assistant.

## Configuration
1. Go to **Settings > Devices & Services > Add Integration**
2. Search for `DHL Tracker` and enter your DHL API key
3. Done! Now you can manage tracking numbers via the UI

## Lovelace Card
Add this to a dashboard:

```yaml
type: custom:dhl-tracker-card
```

## Services
| Service | Description |
|--------|-------------|
| `dhl_tracker.add_tracking_id` | Add a DHL tracking number |
| `dhl_tracker.remove_tracking_id` | Remove a DHL tracking number |

## Voice Assistant
Use Assist or `intent_script` to trigger adding new tracking numbers.

## Credits
Created by [Your Name]. Not affiliated with DHL.
