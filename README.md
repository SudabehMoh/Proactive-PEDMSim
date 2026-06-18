# PRPEDMSim: Proactive Priority-Aware Resource Reallocation in Edge Computing

## Overview

**PRPEDMSim** (*Proactive Resource Reallocation and Priority-Aware Edge Deployment Microservices Simulator*) is an event-driven simulation framework for studying intelligent resource management in edge-cloud computing environments.

This project extends the previous simulators:

* **EDMSim** – Edge Decision Making Simulator
* **PEDMSim** – Priority-Aware Edge Decision Making Simulator
* **RPEDMSim** – Resource Reallocation and Priority-Aware Edge Decision Making Simulator

by introducing a **predictive workload management layer** capable of forecasting future workload surges and proactively mitigating resource congestion before it occurs.

The main objective of PRPEDMSim is to improve service acceptance rates and reduce unnecessary preemptions by combining:

* Reinforcement Learning (Q-Learning)
* Priority-aware scheduling
* Resource reallocation
* Workload prediction
* Proactive cloud offloading

---

## Key Idea

Traditional resource allocation strategies react **after congestion occurs**.

PRPEDMSim introduces a **Peak Workload Predictor** that continuously analyzes incoming microservice requests and forecasts future resource demand.

When an upcoming workload surge is predicted, the system proactively transfers low-priority workloads to the central cloud, preserving edge resources for latency-sensitive and high-priority services.

This transforms resource management from a:

> Reactive strategy

to a

> Proactive strategy

---

## System Architecture

```text
IoT Devices
      |
      v
+-------------------+
|   Edge Clouds     |
+-------------------+
      |
      v
+-------------------+
|   Orchestrator    |
+-------------------+
      |
      +--------------------+
      |                    |
      v                    v
Peak Workload      Central Cloud
 Predictor
```

The orchestrator receives scheduling decisions from the Q-learning agent while the predictor continuously estimates future workload conditions.

---

## Features

### Event-Driven Simulation

* Event-driven execution model
* Microservice-based task representation
* DAG-based dependency management
* Deadline-aware scheduling

### Priority-Aware Resource Management

Tasks are categorized into three priority classes:

| Category | Description     |
| -------- | --------------- |
| C1       | Low Priority    |
| C2       | Medium Priority |
| C3       | High Priority   |

Higher-priority services receive preferential access to edge resources.

---

### Resource Reallocation

Inherited from RPEDMSim:

* Dynamic resource reallocation
* Microservice preemption
* Priority-aware victim selection
* Limited preemption count per task

---

### Peak Workload Prediction

PRPEDMSim introduces a new prediction module that monitors:

* Computational demand (Instructions)
* Storage demand
* Communication demand (Bytes)

The predictor supports:

* Exponential Moving Average (EMA)
* Time-window workload aggregation
* Multi-dimensional workload analysis

---

### Proactive Offloading

When an upcoming peak workload is predicted:

* Low-priority (C1) microservices are proactively redirected to the cloud.
* High-priority (C2/C3) workloads continue competing for edge resources.
* Resource pressure is reduced before congestion occurs.

Unlike RPEDMSim, which relies on preemption after contention occurs, PRPEDMSim attempts to avoid contention in advance.

---

## Reinforcement Learning

The simulator uses Q-Learning to learn resource allocation policies.

### State Representation

The state includes:

* Task category
* Computational demand
* Communication demand
* Storage demand
* Deadline urgency
* Number of available edge servers

### Actions

The agent selects one of:

* Edge Cloud 1
* Edge Cloud 2
* ...
* Central Cloud

### Reward Function

The reward encourages:

* Successful execution
* Deadline satisfaction
* Edge utilization
* Low latency
* Priority-aware scheduling

while penalizing:

* Rejections
* Deadline violations
* Resource contention

---

## Workload Prediction Model

For each observation window, the predictor collects:

```text
Compute Demand
Storage Demand
Communication Demand
Category Distribution
```

and estimates future demand using:

```text
EMA(t) = α × Demand(t)
       + (1 − α) × EMA(t−1)
```

The predicted workload is compared against total edge capacity.

A peak is detected when predicted utilization exceeds a configurable threshold.

---

## Dataset

The simulator supports workload generation using traces derived from real-world cloud datasets, including:

* Alibaba Cluster Trace
* Google Cluster Trace
* Synthetic microservice workloads

Microservices are organized into application DAGs with realistic resource requirements and deadlines.

---

## Evaluation Metrics

PRPEDMSim reports:

* Task Acceptance Rate
* Category-wise Acceptance Rate
* Average Response Time
* Latency
* Number of Preemptions
* Benefited Tasks
* Victim Tasks
* Proactive Offloads
* Peak Prediction Statistics

---

## Project Structure

```text
PRPEDMSim/
│
├── environment.py
├── orchestrator.py
├── predictor.py
├── qlearning.py
├── topology.py
├── edgecloud.py
├── centralcloud.py
├── task.py
├── microservice.py
│
├── data/
│   ├── tasks.csv
│   ├── microservices.csv
│   └── messages.csv
│
├── examples/
│   └── main_PRPEDMSim.py
│
└── results/
```

---

## Research Contribution

PRPEDMSim contributes a novel integration of:

* Reinforcement Learning
* Priority-Aware Scheduling
* Resource Reallocation
* Predictive Workload Management

for edge-cloud computing environments.

The framework enables the investigation of how predictive resource management can reduce congestion and improve quality of service in latency-sensitive applications.

---

## Citation

If you use PRPEDMSim in academic research, please cite the corresponding publication when available.

---

## License

This project is intended for academic and research purposes.
