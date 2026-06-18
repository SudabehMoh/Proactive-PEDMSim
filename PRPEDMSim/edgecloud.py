# -*- coding: utf-8 -*-
"""
Created on Sat Jun 28 11:59:54 2025

@author: Sudabeh
"""

from collections import deque


class EdgeCloud:
    def __init__(self, edge_id, storage, IPT):
        self.edge_id = edge_id
        self.storage = storage  # Total storage capacity
        self.IPT = IPT  # Instructions per time unit
        self.current_cpu = IPT
        self.current_storage = storage
        self.queue = deque()  # Queue of waiting microservices
        self.current_microservice = None  # Currently executing microservice
        self.occupied_until = 0  # The time when the current microservice will finish execution
        self.occupied = False  # Whether the edge is currently processing a task

    def __str__(self):
         return f"Edge_cloud({self.edge_id})"

    def has_enough_resource(self, service):
        #print(f"Valid actions for service {service}: checked")
        return(self.storage >= service.storage_req)


    def is_occupied(self):
        """Return whether the edge cloud is currently occupied."""
        return self.occupied
    

