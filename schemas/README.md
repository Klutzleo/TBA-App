# 📘 TBA App Schema Documentation  
**Version:** 1.0  
**Last Updated:** 2025-09-09  
**Author:** Jason Germino | GameOctane.com 
**System:** Tools for the Bad Ass RPG (TBA) v1.5

---

## 🧠 Overview

This schema suite powers the TBA App—a modular, emotionally reactive storytelling engine built for narrative-first play. Each JSON file represents a distinct domain: user identity, character state, session logs, emotional mechanics, and authored lore.

---

## 📁 JSON Index

| File Name               | Purpose                                                                 |
|-------------------------|-------------------------------------------------------------------------|
| `user_profile.json`      | Tracks GM/player identity, authored lore, emotional style              |
| `character_profile.json` | Unified structure for all builds—magic, tech, hybrid, emotional arcs   |
| `session_log.json`       | Logs narrative events, rolls, echoes, Calling moments, spectator input |
| `storyweaver_state.json` | Controls scene pacing, NPC reactions, environment flags                |
| `tether_registry.json`   | Centralized emotional anchors across characters and sessions           |
| `calling_log.json`       | Tracks death threshold events and tether evolution                     |
| `memory_echoes.json`     | Stores persistent emotional effects tied to past trauma or triumph     |
| `bap_registry.json`      | Logs narrative bonuses triggered by creativity                        |
| `game_instance.json`     | Represents a playable fork or timeline of a campaign                   |
| `lore_entry.json`        | Stores authored lore with emotional and mechanical metadata            |

---

## 🧩 Schema Principles

- **Modular**: Each JSON is self-contained and cross-referenced via IDs  
- **Flat**: No deep nesting—easy to parse, store, and query  
- **Expressive**: Emotional flags, memory markers, and narrative tags are first-class citizens  
- **Reactive**: Supports tether triggers, Calling events, and echo propagation  
- **Privacy-Aware**: Visibility flags (`public`, `private`, `mixed`) on all sensitive fields

---

## 🧷 Field Conventions

- `*_id`: Unique identifiers for linking across schemas  
- `visibility`: Controls UI exposure and sharing  
- `tags`: Thematic or emotional metadata for filtering and surfacing  
- `origin_event`, `session_id`: Traceable emotional lineage  
- `bonus`, `effect`: Mechanical impact of emotional triggers

---

## 🧠 Emotional Mechanics

| Mechanic        | JSON Source           | Description                                               |
|-----------------|-----------------------|-----------------------------------------------------------|
| **Tethers**     | `tether_registry.json`| Emotional anchors that trigger bonuses or penalties       |
| **The Calling** | `calling_log.json`    | Death threshold mechanic with narrative consequences      |
| **Memory Echoes**| `memory_echoes.json` | Persistent effects from trauma or triumph                 |
| **Marked by Death**| `character_profile.json` | Status effect after surviving The Calling             |
| **BAP Triggers**| `bap_registry.json`   | Narrative bonuses granted by Story Weaver creativity      |

---

## 🛠️ Next Steps

- Implement schema validation  
- Build API endpoints for each domain  
- Design UI components to surface emotional data  
- Prototype emotional trigger engine for reactive storytelling

---

## 🧙 Author Note

This schema honors memory, agency, and emotional safety. It’s not just a data model—it’s a mythic machine built to remember what mattered.
