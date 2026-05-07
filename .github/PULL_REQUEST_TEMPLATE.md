# Pull Request

## What this changes

<!-- One paragraph. Be specific. -->

## Why

<!-- Link the issue if there is one, or explain the motivation. -->

## Safety review

If your change touches any of the following, you MUST describe what
you changed and why:

- [ ] Hard angle clamp (`HARD_ANGLE_LIMIT_DEG`)
- [ ] Rate limit (`MAX_RATE_DEG_PER_SEC`)
- [ ] Any watchdog (RX timeout, divergence, bus error, loop overrun)
- [ ] Any E-STOP path (button, ESC, Q, window, automatic)
- [ ] Keepalive synthesis (`SYNTHESIZE_GTW`, `SYNTHESIZE_EPB`,
      `thirty_mph_mode`)
- [ ] CAN message builders (`build_das_steering_control`,
      `build_gtw_epas_control`, `build_epb_epas_control`,
      `build_fake_esp_speed`)
- [ ] `0x370` decode

If you checked any box above, write a paragraph explaining why the
change is safe.

## Tested

- [ ] Syntax-checked
- [ ] Ran `tesla_control.py` and saw the GUI come up
- [ ] Tested on real hardware (rack on bench or in-car)
- [ ] Reviewed session logs for unexpected EAC transitions or errors

If untested on hardware, say so explicitly.

## Version

If you're shipping a new release, bump `__version__` in
`tesla_control.py` and add an entry to `CHANGELOG.md`.

- [ ] `__version__` bumped
- [ ] `CHANGELOG.md` updated

(If neither applies because this is a docs / refactor change, leave
the boxes unchecked.)
