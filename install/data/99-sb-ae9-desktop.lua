-- SPDX-License-Identifier: GPL-2.0-only
-- WirePlumber 0.4 configuration, evaluated by the existing session manager.
table.insert(alsa_monitor.rules, {
  matches = { { { "device.profile-set", "equals", "sb-ae9.conf" } } },
  apply_properties = {
    ["api.alsa.use-acp"] = true,
    ["api.alsa.use-ucm"] = false,
  },
})

-- Loaded after older AE-9 capture restrictions; only this new mapping is allowed.
table.insert(alsa_monitor.rules, {
  matches = { { { "device.profile.name", "equals", "sb-ae9-what-u-hear" } } },
  apply_properties = {
    ["node.disabled"] = false,
    ["node.description"] = "AE-9 What U Hear",
    ["node.nick"] = "What U Hear",
    ["priority.session"] = 100,
    ["priority.driver"] = 100,
    ["audio.rate"] = 48000,
    ["audio.format"] = "S32LE",
  },
})
