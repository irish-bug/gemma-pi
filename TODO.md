# To-Do List: Project Gemma (v16.3)

## 1. Droid Audio Integration (The "Beep-Boop" Patch)
- [ ] **Asset Hunt:** Source a clean R2D2 sound pack (WAV format).
- [ ] **Hardware Mapping:** Ensure `aplay` is directed to Card 2 so Artoo shares the Anker S500 with Gemma.
- [ ] **Makefile Hooks:** Link the `success_chirp.wav` to the `test` and `commit` targets for auditory feedback.

## 2. The "Gemma Brain" Injection
- [ ] **Inference Loop:** Replace the audio mirror (the echo) with the actual token-generation logic.
- [ ] **Context Load:** Verify the system prompt correctly identifies your Researcher/Luthier/Chef persona.
- [ ] **Token Optimization:** Tune the `max_tokens` to keep the response time under 2 seconds on the Pi 5 hardware.

## 3. Hardware Resilience
- [ ] **Pre-Flight Probe:** Add a check to the `setup` and `run` targets to verify the Anker S500 is connected at `hw:2,0`.
- [ ] **Thermal Monitoring:** Add a debug log for CPU temperature to ensure the "Brain" isn't cooking the Pi during long conversations.

## 4. Wildcard: The "Command Mode"
- [ ] **Voice Logging:** Explore a way to have Artoo take a "Note" or log a "Weigh-In" via voice command, piping that data directly into tracking spreadsheets.
