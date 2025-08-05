class DHLTrackerCard extends HTMLElement {
  set hass(hass) {
    this.hass = hass;
    const allStates = Object.values(hass.states).filter(e => e.entity_id.startsWith('sensor.dhl_'));

    this.innerHTML = `
      <ha-card header="\ud83d\udce6 DHL Packages">
        <div style="padding: 16px;">
          ${allStates.map(s => {
            const eta = s.attributes.eta || '';
            return `<div>\ud83d\udce6 <b>${s.attributes.tracking_number}</b> – ${s.state} ${eta ? `– ETA: ${eta}` : ''}</div>`;
          }).join("")}
          <br/>
          <input id="dhl-id-input" placeholder="Add Tracking ID" />
          <button onclick="this.parentElement.parentElement.parentElement.addID()">➕ Add</button>
        </div>
      </ha-card>
    `;

    this.querySelector('input')?.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') this.addID();
    });
  }

  addID() {
    const id = this.querySelector('#dhl-id-input')?.value.trim();
    if (!id) return;
    this.hass.callService('dhl_tracker', 'add_tracking_id', { tracking_id: id });
    this.querySelector('#dhl-id-input').value = '';
  }

  setConfig(config) {
    this.config = config;
  }

  getCardSize() {
    return 3;
  }
}

customElements.define('dhl-tracker-card', DHLTrackerCard);
