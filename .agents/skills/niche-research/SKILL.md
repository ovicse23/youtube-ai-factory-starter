---
name: niche-research
description: Research high-growth YouTube niches using vidIQ keyword demand, breakout trend signals, competition ratios, and evergreen audience viability.
---

# Niche Research Skill

This skill discovers, evaluates, and ranks high-opportunity YouTube niches for the YouTube AI Factory platform.

## Research Strategy

1. **Demand Signal Identification**:
   - Query vidIQ MCP (when active) for monthly search volumes, 30-day search growth, and overall opportunity scores.
   - For Gemini fallback mode, perform qualitative market analysis focusing on underserved curiosity gaps, satisfying sensory micro-documentaries, and high-CPM technical topics.

2. **Competition Evaluation**:
   - Assess competition ratio (low/medium/high) and look for low-supply queries with surging viewer search interest.
   - Favor niches where small creators (<10K subscribers) have recent breakout videos (>100K views).

3. **Production Feasibility (Digen-Centric)**:
   - Ensure the niche is technically feasible for Digen AI video generation (e.g., stylized 3D, macro cutaways, isometric miniatures, cinematic mechanical physics).
   - Avoid niches requiring copyrighted celebrity likenesses or photorealistic dialogue.

4. **Output Structure**:
   Return a structured JSON/markdown report containing:
   - Niche Name & Focus
   - Target Audience & Top-Tier Markets (US, UK, CA, AU)
   - Opportunity Score (1–100 weighted rubric)
   - Demand & Competition Evidence
   - 30-Day Testing Experiment Roadmap
