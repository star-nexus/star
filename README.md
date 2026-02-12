# STAR: Strategic Tactical Agent Reasoning

<div align="center">

[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Python](https://img.shields.io/badge/Python-3.10%2B-blue)](https://www.python.org/)
[![Status](https://img.shields.io/badge/Status-Active%20Development-success)]()

[Introduction](#introduction) • [Components](#Components) • [Architecture](#System-Architecture) • [Quick Start](#quick-start)

</div>

---

## 🚀 Introduction

**STAR (Strategic Tactical Agent Reasoning)** is a modular research framework for studying LLM-driven agents in dynamic multi-agent environments.

STAR focuses on evaluating how large language models perform under **long-horizon strategic planning**, **partial observability**, and **real-time decision constraints**, providing a reproducible interface that integrates simulation, evaluation, and extensible agent interaction.

## Overview

Recent advances in language models have demonstrated strong reasoning ability in static settings, yet their behavior in interactive, dynamic environments remains less understood. STAR provides a standardized environment for investigating decision-making under uncertainty, adversarial interaction, and execution latency.

The framework is designed to decouple simulation logic, agent reasoning, and communication protocols, enabling researchers to build new environments, integrate diverse agent runtimes, and evaluate strategies within a consistent experimental pipeline.

## Components

STAR is organized around three complementary components:

### 🏗️ The Engine (`STAREngine`)
A modular simulation core built on an Entity–Component–System (ECS) architecture.
*   **Data-Oriented:** Data-oriented design for scalable execution.
*   **LLM-friendly modular design:** The decoupling design enables LLMs to intuitively understand and refactor project mechanics without navigating complex inheritance trees.
*   **Extensible:** Researchers can plug in new environments or swap agent backends (DeepSeek, Qwen, GPT-4) without reinventing the wheel.

### 🏆 The Benchmark (`STARBench`)
A benchmarking suite for strategic multi-agent scenarios.
*   **Scenario:** *Romance of the Three Kingdoms (RoTK)* — A zero-sum competitive environment.
*   **Modes:** Configurable real-time and turn-based execution modes.
*   **Metrics:** Standardized evaluation metrics and reporting.

### 🔌 The Protocol (`Star Protocol`)
An asynchronous communication layer for integrating heterogeneous agents and ENVs.
*   **Router Bridge:** Structured message interface between agents and environments
*   **Remote Support:** Runtime-agnostic integration (local or remote)

---

## System Architecture

STAR adopts a hierarchical, modular architecture designed for scalability.

![System Architecture](docs/architecture.jpg)

| Layer | Component | Description |
| :--- | :--- | :--- |
| **Agent Layer** | *Decision Host* | Decision hosts implementing perception–planning–action loops. |
| **Protocol Layer** | *Nexus Bridge* | Asynchronous protocol and communication abstraction. |
| **Environment Layer** | *Simulation Logic* | Implements specific ENV rules (e.g., RoTK), physics, and vision systems. |
| **Framework Layer** | *STAREngine* | Core ECS-based execution framework. |

---

## ✨ Key Features

- Strategic multi-agent evaluation
- Real-time and turn-based execution modes
- Partial observability environments
- Extensible environment and agent integration
- Layered ECS runtime for scalable simulation

---

## 🛠️ Quick Start

### Prerequisites
*   Python 3.12+
*   `uv` (recommended) or `pip`

### Installation

```bash
# Clone the repository
git clone https://github.com/star-nexus/star.git

cd star

# Install dependencies using uv (fastest)
uv sync
```

### Running a Demo (AI v.s. AI)

Experience the *Romance of the Three Kingdoms* scenario directly:

```bash
# Launch the RoTK environment in GUI mode
# LLM Agents play as 'Wei' (Blue) and 'Shu' (Green).
uv run rotk_env/main.py

# Launch the first Agent
uv run rotk_agent/qwen3_agent.py \
    --env-id env_1 \
    --agent-id agent_1 \
    --faction "shu" \
    --provider xxx 

# Launch the second Agent
uv run rotk_agent/qwen3_agent.py \
    --env-id env_1 \
    --agent-id agent_2 \
    --faction "wei" \
    --provider xxx 
```

### Running Agent Evaluation in Batch

To run a headless evaluation between two LLM agents:

```bash
python auto_test.py --mode [real_time | turn_based] --players ai_vs_ai --report-wait 120 --list provider.txt

# provider.txt:
deepseek,glm_47
glm_46,deepseek

# You need to specify the providers in .config.toml:
[deepseek]
model_id = "deepseek"
api_key = "xxx"
base_url = "https://xxx/v1/chat/completions"
```

---

## 🗺️ Roadmap

*   [x] **Core ECS Framework** & RoTK Environment.
*   [x] **WebSocket Protocol** for remote agent connection.
*   [x] **Real-Time Mode:** Moving from Turn-Based to RTS (Real-Time Strategy) constraints.
*   [x] **Multi-Modal Agents:** allowing agents to consume the rendered map frame pixels instead of JSON text.
*   [x] **Web Hub:** A centralized dashboard to spectate matches and view leaderboards.