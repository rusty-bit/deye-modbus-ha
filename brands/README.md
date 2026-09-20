# Integration icon

Home Assistant does not take the icon shown on the Integrations page from the
integration itself - it loads it from `brands.home-assistant.io`. Until the
domain exists there, the card shows a grey "icon not available" placeholder.
There is no local override for it.

To fix it, open a pull request against https://github.com/home-assistant/brands
adding this folder as:

    custom_integrations/deye_modbus/icon.png      (256x256)
    custom_integrations/deye_modbus/icon@2x.png   (512x512)

Rules that these files already follow:
- square, PNG with transparent background, trimmed (no extra padding)
- icon.png is exactly 256x256, icon@2x.png exactly 512x512
- `logo.png` is optional; when it is missing the icon is used instead

The PR description should link the public repository for the integration. The
domain in the folder name must match `domain` in `custom_components/deye_modbus/manifest.json`
(`deye_modbus`), otherwise the icon will not be picked up.

Note: brands only serves icons for public integrations, so the pull request has
to point at a public repo (the upstream Developer089/deye-modbus-ha, or a public
fork). After it is merged the icon appears for everyone using that domain,
including this personal fork.
