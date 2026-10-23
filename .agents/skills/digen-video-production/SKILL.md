---
name: digen-video-production
description: Orchestrate Digen-only video generation, enforce the Scene-01 First credit gate, poll task status, and assemble final MP4s with FFmpeg locally.
---

# Digen Video Production Skill

Manages video generation through the official Digen AI integration (MCP endpoint and CLI) with strict credit governance.

## Guardrails & Principles

1. **Digen-Only Mandate**:
   - Digen is the exclusive video generation provider. Do not invoke secondary video generators.

2. **Scene-01 First Rule (Credit Protection)**:
   - Always generate and inspect **Scene 1** before approving credits for Scenes 2..N.
   - Verifies character proportions, lighting, and actual credit deductions before committing the full video budget.

3. **Prompt Formatting**:
   - Pack prompts with aspect ratio (9:16 or 16:9), target duration (e.g. 8s), continuity notes, and negative instructions (no text, no distorted limbs).

4. **Local FFmpeg Stitching**:
   - Heavy video rendering runs strictly on the Local Engine:
     ```bash
     ffmpeg -y -f concat -safe 0 -i inputs.txt -c:v libx264 -pix_fmt yuv420p -c:a aac output/final.mp4
     ```
   - Avoids Workers Free CPU limits and operates at zero extra cloud cost.
