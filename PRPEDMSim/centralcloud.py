# -*- coding: utf-8 -*-
"""
Created on Sat Jun 28 12:00:49 2025

@author: Sudabeh
"""
from collections import deque


class CentralCloud:
    def __init__(self, cloud_id, storage, IPT):
        self.cloud_id = cloud_id
        self.storage = storage  # Total storage capacity
        self.IPT = IPT  # Instructions per time unit
        self.current_cpu = IPT
        self.current_storage = storage
        self.current_microservices = []  # Currently executing microservices
        self.queue = deque()  # Queue of waiting microservices
        self.occupied_until = 0  # The time when the current microservice will finish execution
        self.counter_of_task_in = 0  # Count of tasks currently being processed

    def __str__(self):
        return f"CentralCloud({self.cloud_id})"


    def has_enough_resource(self, service):
        """Always returns True, as Central Cloud has sufficient resources."""
        return True

    def is_occupied(self):
        """Central cloud does not have hard occupancy limits like edge clouds."""
        return False  # Always ready to accept tasks

