gemma-pi

A low-latency conversational agent for Raspberry Pi 5 with local wake-word detection and CLI integration utilizing the Gemini Multimodal Live API and Anker PowerConf S500.
🤖 System Architecture (Mark IV)

This project utilizes a multi-layered intelligence hierarchy:

    Mike (Strategic Advisor): The high-level logic and architectural coordinator.

    Gemma (Operational Interface): The real-time conversational agent living on the Pi 5.

    arTOO (Operational Astromech): The local Gemini CLI bridge for file and system management.

🛠 Hardware Requirements

    Compute: Raspberry Pi 5

    Audio I/O: Anker PowerConf S500 (Optimized for duplex communication)

🚀 Getting Started

    Clone the repo: git clone git@github.com:irish-bug/gemma-pi.git

    Setup Environment: * Ensure GEMINI_API_KEY is in your environment variables.

        Install dependencies: pip install asyncio websockets numpy sounddevice openwakeword

    Initialize the Manifest: Copy gemma_manifest_example.json to gemma_manifest.json and populate with local data.

    Run Gemma: python gemma_speaks.py

🔒 Configuration & Privacy

This project utilizes a Zero-Footprint PII Strategy. To protect personal data, sensitive identifiers are stored in a local manifest that is explicitly ignored by version control.

    Local Manifest: gemma_manifest.json is included in the .gitignore. It stores your specific locations, project aliases, and personal identifiers.

    Example Template: See gemma_manifest_example.json for the required structure.

    Verification: Always run git status before pushing to ensure no sensitive JSON or log files are staged for commit.

⚙️ Key Features

    Unity Gain Calibration: Tailored specifically for the S500 to prevent digital clipping.

    Duplex Gating: Prevents the agent from entering feedback loops during high-volume responses.

    CLI Bridge: Speak commands directly to the arTOO agent for local shell execution.

⚖️ License

This project is licensed under the MIT License - see the LICENSE file for details.

