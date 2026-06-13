#!/bin/bash 
# Combines the architectural summary and the latest code into one file for Gemini 
OUTPUT="gemma_manifest.txt" 
echo "# PROJECT GEMMA - CURRENT STATE" > $OUTPUT 
cat gemma_summary.md >> $OUTPUT 
echo -e "\n\n# --- CURRENT CODE: gemma_runtime.py ---" >> $OUTPUT 
cat gemma_runtime.py >> $OUTPUT 
echo -e "\n\n# --- CURRENT CODE: artoo_tools.py ---" >> $OUTPUT 
cat artoo_tools.py >> $OUTPUT 
echo -e "\n\n# --- CURRENT CODE: gemma_tools.py ---" >> $OUTPUT
cat gemma_tools.py >> $OUTPUT
echo -e "\n\n# --- CURRENT CODE: spotify_control.py ---" >> $OUTPUT
cat spotify_control.py >> $OUTPUT
echo -e "\n\n# --- CURRENT CODE: ARTOO.md ---" >> $OUTPUT
cat ARTOO.md >> $OUTPUT
echo -e "\n\n# --- CURRENT ARTOO MEMORIES: contents of memory subdirectory used by artoo ---" >> $OUTPUT
echo -e "\n\n# --- CURRENT ARTOO MEMORIES: calendar_mappings.md ---" >> $OUTPUT
cat memory/calendar_mappings.md >> $OUTPUT
echo -e "\n\n# --- CURRENT ARTOO MEMORIES: emily_calendars.md ---" >> $OUTPUT
cat memory/emily_calendars.md >> $OUTPUT
echo -e "\n\n# --- CURRENT ARTOO MEMORIES: HEALTH_PROTOCOL.md ---" >> $OUTPUT
cat memory/HEALTH_PROTOCOL.md >> $OUTPUT
echo -e "\n\n# --- CURRENT ARTOO MEMORIES: MEMORY.md ---" >> $OUTPUT
cat memory/MEMORY.md >> $OUTPUT
echo -e "\n\n# --- CURRENT ARTOO POLICIES: contents of policy subdirectory used by artoo ---" >> $OUTPUT
echo -e "\n\n# --- CURRENT ARTOO MEMORIES: HOME_ASSISTANT.md ---" >> $OUTPUT
cat policies/HOME_ASSISTANT.md >> $OUTPUT
echo -e "\n\n# --- CURRENT ARTOO MEMORIES: WORKSPACE.md ---" >> $OUTPUT
cat policies/WORKSPACE.md >> $OUTPUT
echo -e "\n\n# --- CURRENT SERVICE: artoo.service ---" >> $OUTPUT 
cat /home/shane/.config/systemd/user/artoo.service >> $OUTPUT
echo -e "\n\n# --- CURRENT SERVICE: artoo-audio-guardian.service ---" >> $OUTPUT 
cat /home/shane/.config/systemd/user/artoo-audio-guardian.service >> $OUTPUT
echo -e "\n\n# --- CURRENT SERVICE: gemma.service ---" >> $OUTPUT 
cat /home/shane/.config/systemd/user/gemma.service >> $OUTPUT
echo "Manifest compiled to $OUTPUT" 