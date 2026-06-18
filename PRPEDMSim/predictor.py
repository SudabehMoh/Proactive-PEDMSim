"""
peak_workload_predictor.py

Peak workload prediction module for PRPEDMSim.

Supports:
- MICROSERVICE_WINDOW mode
- TIME_WINDOW mode
- Compute / Storage / Bandwidth prediction
- Category-aware prediction
- EMA-based forecasting
- Peak probability and severity estimation
- Recommendation generation
"""

from collections import deque
from dataclasses import dataclass
from enum import Enum
from typing import Dict, Deque


class PredictionMode(Enum):
    MICROSERVICE_WINDOW = 1
    TIME_WINDOW = 2


class RecommendationType(Enum):
    NORMAL = "NORMAL"
    RESERVE_RESOURCES = "RESERVE_RESOURCES"
    OFFLOAD_LOW_PRIORITY = "OFFLOAD_LOW_PRIORITY"
    PROACTIVE_PREEMPTION = "PROACTIVE_PREEMPTION"


@dataclass
class PredictionResult:
    future_peak: bool
    peak_probability: float
    peak_severity: float

    predicted_compute_utilization: float
    predicted_storage_utilization: float
    predicted_bandwidth_utilization: float

    dominant_category: int
    predicted_category_distribution: Dict[int, float]


class PeakWorkloadPredictor:

    def __init__(
        self,
        topology,
        mode=PredictionMode.TIME_WINDOW,
        history_size: int = 10,
        window_duration: float = 10.0,
        prediction_horizon: int = 1,
        compute_threshold_ratio: float = 0.80,
        storage_threshold_ratio: float = 0.80,
        bandwidth_threshold_ratio: float = 0.80,
        alpha: float = 0.30,
    ):

        self.topology = topology
        self.mode = mode

        self.history_size = history_size
        self.window_duration = window_duration
        self.prediction_horizon = prediction_horizon

        self.compute_threshold_ratio = compute_threshold_ratio
        self.storage_threshold_ratio = storage_threshold_ratio
        self.bandwidth_threshold_ratio = bandwidth_threshold_ratio

        self.alpha = alpha

        # Total capacities
        self.total_compute_capacity = sum(  # 110+2900+3700+3700
            edge.IPT for edge in topology.edgeclouds
        )

        self.total_storage_capacity = sum(   # 64 + 32 + 64 + 64
            edge.storage for edge in topology.edgeclouds
        )

        self.total_bandwidth_capacity = ( 
            len(topology.edgeclouds) * topology.iot_edge_bw
        )

        # Global histories
        self.compute_history: Deque[float] = deque(maxlen=history_size)
        self.storage_history: Deque[float] = deque(maxlen=history_size)
        self.bandwidth_history: Deque[float] = deque(maxlen=history_size)

        # Category histories
        self.category_history = {
            1: deque(maxlen=history_size),
            2: deque(maxlen=history_size),
            3: deque(maxlen=history_size),
        }

        # Current accumulation buffers
        self.current_compute = 0.0
        self.current_storage = 0.0
        self.current_bandwidth = 0.0

        self.current_cat = {
            1: 0,
            2: 0,
            3: 0,
        }

        self.window_start_time = 0.0

    def reset(self):

        self.compute_history.clear()
        self.storage_history.clear()
        self.bandwidth_history.clear()

        for cat in self.category_history:
            self.category_history[cat].clear()

        self.current_compute = 0.0
        self.current_storage = 0.0
        self.current_bandwidth = 0.0

        self.current_cat = {
            1: 0,
            2: 0,
            3: 0,
        }

        self.window_start_time = 0.0

    def update(self, microservice, current_time: float):

        category = (microservice.get_task_of_microservice(self.topology).category)

        compute = microservice.instructions
        storage = microservice.storage_req
        bandwidth = microservice.bytes

        if self.mode == PredictionMode.MICROSERVICE_WINDOW:

            self.compute_history.append(compute)
            self.storage_history.append(storage)
            self.bandwidth_history.append(bandwidth)

            self.category_history[category].append(1)

        else:

            self.current_compute += compute
            self.current_storage += storage
            self.current_bandwidth += bandwidth

            self.current_cat[category] += 1

            self.tick(current_time)

    def tick(self, current_time: float):

        if self.mode != PredictionMode.TIME_WINDOW:
            return

        while (current_time - self.window_start_time >= self.window_duration):

            self._finalize_time_window()
            self.window_start_time += self.window_duration
        # print(
        #     f"[TICK] "
        #     f"time={current_time:.2f} "
        #     f"window_start={self.window_start_time:.2f}"
        # )

    def _finalize_time_window(self):

        # print(
        #     f"[WINDOW CLOSED] "
        #     f"compute={self.current_compute:.2f} "
        #     f"storage={self.current_storage:.2f} "
        #     f"bw={self.current_bandwidth:.2f}"
        # )

        self.compute_history.append(self.current_compute)
        self.storage_history.append(self.current_storage)
        self.bandwidth_history.append(self.current_bandwidth)

        for cat in (1, 2, 3):
            self.category_history[cat].append(
                self.current_cat[cat]
            )

        self.current_compute = 0.0
        self.current_storage = 0.0
        self.current_bandwidth = 0.0

        self.current_cat = {
            1: 0,
            2: 0,
            3: 0,
        }

    def _ema_predict(self, history):

        if not history:
            return 0.0

        prediction = history[0]

        for value in list(history)[1:]:
            prediction = (
                self.alpha * value
                + (1.0 - self.alpha) * prediction
            )

        return prediction

    def _predict_category_distribution(self):

        predicted = {}

        total = 0.0

        for cat in (1, 2, 3):
            predicted[cat] = self._ema_predict(self.category_history[cat])
            total += predicted[cat]

        if total <= 0:
            return {
                1: 0.33,
                2: 0.33,
                3: 0.34,
            }

        return {
            cat: predicted[cat] / total
            for cat in predicted
        }

    def _peak_probability(
        self,
        compute_ratio,
        storage_ratio,
        bandwidth_ratio,
    ):

        max_ratio = max(
            compute_ratio,
            storage_ratio,
            bandwidth_ratio,
        )

        return min(1.0, max_ratio)

    def _peak_severity(
        self,
        compute_ratio,
        storage_ratio,
        bandwidth_ratio,
    ):

        return max(
            compute_ratio,
            storage_ratio,
            bandwidth_ratio,
        )

    def predict(self):

        predicted_compute = self._ema_predict(self.compute_history)

        predicted_storage = self._ema_predict(self.storage_history)

        predicted_bandwidth = self._ema_predict(self.bandwidth_history)

        compute_util = (predicted_compute/ max(1.0, self.total_compute_capacity))

        storage_util = (predicted_storage/ max(1.0, self.total_storage_capacity))

        bandwidth_util = (predicted_bandwidth/ max(1.0, self.total_bandwidth_capacity))

        category_distribution = (self._predict_category_distribution())

        dominant_category = max(
            category_distribution,
            key=category_distribution.get
        )

        probability = self._peak_probability(
            compute_util,
            storage_util,
            bandwidth_util,
        )

        severity = self._peak_severity(
            compute_util,
            storage_util,
            bandwidth_util,
        )

        future_peak = (
            compute_util >= self.compute_threshold_ratio
            or storage_util >= self.storage_threshold_ratio
            or bandwidth_util >= self.bandwidth_threshold_ratio
        )

        return PredictionResult(
            future_peak=future_peak,
            peak_probability=probability,
            peak_severity=severity,
            predicted_compute_utilization=compute_util,
            predicted_storage_utilization=storage_util,
            predicted_bandwidth_utilization=bandwidth_util,
            dominant_category=dominant_category,
            predicted_category_distribution=category_distribution,
        )

    def get_recommendation(self):

        result = self.predict()

        if result.peak_severity < 0.60:
            return RecommendationType.NORMAL

        if result.peak_severity < 0.80:
            return RecommendationType.RESERVE_RESOURCES

        if (
            result.peak_severity < 1.00
            and result.dominant_category == 3
        ):
            return RecommendationType.OFFLOAD_LOW_PRIORITY

        return RecommendationType.PROACTIVE_PREEMPTION
