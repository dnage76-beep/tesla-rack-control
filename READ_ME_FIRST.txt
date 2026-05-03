============================================================
  TESLA RACK TEST -- v3
============================================================

Hey Jordan,

Status update: Derek already flashed gregjhogan's firmware
patch on the EPAS rack. The car is a 2013 Model S, post-May-31
build, post-patch. You can now command steering directly via
0x488 messages.

Two ways to test, simple and full. Pick one based on how
careful you want to be.

============================================================
  WHAT'S IN THIS FOLDER (v3 ADDS move.py)
============================================================

  1. WIRING_DIAGRAM.pdf        <-- LOOK AT THIS FIRST
     1-page printable diagram. Shows exactly which pin
     on the OBD-II port goes to which pin on the SYS
     TEC DB9. Color-coded with safety notes.

  2. PINOUT_VERIFICATION.pdf   <-- READ NEXT
     2-page guide. Find the OBD-II port in the driver
     footwell. Confirm pins 1 (CH+) and 9 (CH-) are
     populated. Multimeter check. Run the sniffer.

  3. INSTRUCTION_MANUAL.pdf
     2-page guide. Install Python on Windows, install
     python-can, install SYS TEC driver, run the test
     program.

  3b. FLASH_AND_TROUBLESHOOTING.pdf  (NEW)
     4-page guide. Use this if the rack stays at INHIBITED
     and won't move when you send commands. Walks through
     re-running the BogGyver EPAS flasher on the comma 3X,
     verifying the patch took, and a full troubleshooting
     matrix for every common failure mode.

  4. move.py                   <-- SIMPLEST RUN
     ~120 lines, every line commented. Run it like:
        python move.py 15
     and the wheels go to +15 deg. Ctrl-C to disengage.
     No GUI. No rate limit. Read the file before running.

  5. tesla_steering_test.py    <-- FULL GUI OPTION
     The dark-themed window with the slider, big red E-STOP,
     status panel, and all the failsafes. Use this if you
     want the safety net.

  6. can_sniffer.py
     Passive bus listener. Run BEFORE either move.py or
     tesla_steering_test.py to confirm wiring is right.

  7. SETUP.md
     Longer text install reference if a PDF is unclear.

============================================================
  THE SIMPLEST PATH (move.py)
============================================================

This is the bare-minimum way to move the wheels.

STEP 1.  Print and follow PINOUT_VERIFICATION.pdf.
         Confirm chassis CAN traffic on the sniffer.

STEP 2.  Follow INSTRUCTION_MANUAL.pdf STEPS 1-3 only:
         install Python, install python-can, install
         SYS TEC driver. Skip step 5 onward.

STEP 3.  Front of car on jack stands. Wheels off the ground
         OR tie rods disconnected.

STEP 4.  Open command prompt in this folder. Type:
            python move.py 0
         Wheel should center (or stay put). Ctrl-C to stop.

STEP 5.  Try:
            python move.py 5
         Wheels turn +5 deg. Ctrl-C disengages.

STEP 6.  Try -5, +15, -15. Stop if anything feels wrong.

NO E-STOP BUTTON IN move.py. Ctrl-C is your only abort.
If Ctrl-C doesn't react instantly, close the whole terminal
window with the X.

============================================================
  THE SAFER PATH (tesla_steering_test.py)
============================================================

Same effect, but with:
  - Big red E-STOP button
  - ESC key as another E-STOP
  - Slider so you can ramp slowly
  - Live status display showing the rack's response
  - Watchdog that disengages if something looks wrong

Follow the INSTRUCTION_MANUAL.pdf in full, including step 5
onward. Use this if it's your first time or you want belt
and suspenders.

============================================================
  WHEN TO USE WHICH
============================================================

Use move.py if:
  - You're confident in the wiring
  - You just want a quick "does the wheel move?" test
  - You've already done a successful run with the GUI
    once and trust the setup

Use tesla_steering_test.py if:
  - It's your first time on this car
  - The car is new to the project
  - Anyone else might walk up and start interacting with it
  - You want the failsafes

Either way: text Derek a screenshot before going past
+/- 5 degrees the first time.
Derek's number: 847-226-3311

============================================================
  KNOWN BEHAVIOR
============================================================

* The rack ignores 0x488 if the firmware patch is missing.
  It's already patched, so this is fine. If for some reason
  the rack does NOT move, the patch is the first thing to
  check.

* Stock GTW and EPB modules in the car keep sending 0x101
  and 0x214. We do NOT touch those. The patched rack ignores
  the gating values inside them but needs them present on
  the bus, which the stock modules already provide.

* The rack auto-disengages 200 ms after we stop sending
  0x488. So if Ctrl-C interrupts the script, the rack
  goes back to manual within a fraction of a second.

============================================================
  WHAT NOT TO DO
============================================================

* Do NOT skip the pinout verification.
* Do NOT run with front wheels touching the ground.
* Do NOT raise the +/- 90 deg cap in the code.
* Do NOT modify any .py file unless Derek says so.

============================================================

Open PINOUT_VERIFICATION.pdf and start at Test A.

-- Derek
