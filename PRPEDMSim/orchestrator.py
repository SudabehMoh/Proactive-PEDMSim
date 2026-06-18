# -*- coding: utf-8 -*-
"""
Created on Sat Jun 28 12:12:19 2025

@author: Sudabeh
"""

import numpy as np
from typing import Dict, List, Tuple
from PRPEDMSim.topology import Topology
from PRPEDMSim.microservice import Microservice
from PRPEDMSim.edgecloud import EdgeCloud
from PRPEDMSim.centralcloud import CentralCloud

class Orchestrator:
    def __init__(self, topology: Topology):
        self.topology = topology
        self.tasks = topology.tasks
        self.microservices = topology.microservices
        self.messages = topology.messages
        self.edge_clouds = topology.edgeclouds
        self.central_clouds = topology.centralclouds
        self.predictor = None
    
    def _allocate_edge(
        self,
        ms: Microservice,
        edge_id: int
    ) -> Tuple[bool, float]:

        edge = self.edge_clouds[edge_id]

        # -------------------------------------------------
        # Communication latency
        # -------------------------------------------------
        latency = self.topology.latency(ms, edge)

        # -------------------------------------------------
        # Spin Up delay
        # -------------------------------------------------
        spin_up_delay = self.topology.spin_up_delay(ms, edge)

        # -------------------------------------------------
        # Execution time
        # -------------------------------------------------
        service_time = ms.instructions / edge.IPT


        if (edge.current_microservice is not None and edge.current_microservice.status == 'running'):

            return False, None
        # -------------------------------------------------
        # Resource becomes available after previous jobs
        # -------------------------------------------------
        start_time = max(
            ms.arrival_time + latency,
            spin_up_delay,
            edge.occupied_until
        )

        end_time = start_time + service_time

        # -------------------------------------------------
        # Deadline check
        # -------------------------------------------------
        if end_time <= ms.deadline_of_microservice(self.topology):

            ms.status = 'running'
            ms.assigned_resource = edge

            ms.latency  = latency
            ms.spin_up_delay = spin_up_delay
            ms.service_time = service_time

            # Actual waiting time inside resource queue or for spin up delay
            ms.wait_time = max(
                0,
                start_time - ms.arrival_time - latency
            )

            ms.start_time = start_time
            ms.end_time = end_time

            ms.response_time = end_time + latency - ms.arrival_time # latency is the communication downloading delay
            

            # -------------------------------------------------
            # Update edge state
            # -------------------------------------------------
            edge.occupied_until = end_time

            edge.queue.append(ms)

            edge.current_microservice = ms
            
            return True, end_time

        # -------------------------------------------------
        # Rejected
        # -------------------------------------------------
        else:
            ms.status = 'rejected'
            ms.rejection_reason = 'inedge, deadline'
            
            return False, end_time

    def _allocate_cloud(
        self,
        ms: Microservice,
        cloud_id: int
    ) -> Tuple[bool, float]:

        cloud = self.central_clouds[
            cloud_id - len(self.edge_clouds)
        ]

        # -------------------------------------------------
        # Communication latency
        # -------------------------------------------------
        latency = self.topology.latency(ms, cloud)

        # -------------------------------------------------
        # Data transfer delay
        # -------------------------------------------------
        spin_up_delay = self.topology.spin_up_delay(ms, cloud)

        # -------------------------------------------------
        # Execution time
        # -------------------------------------------------
        service_time = ms.instructions / cloud.IPT

        # -------------------------------------------------
        # Cloud execution starts immediately after data arrival
        # -------------------------------------------------
        

        start_time = max(
            ms.arrival_time + latency,
            spin_up_delay
        )

        end_time = start_time + service_time

        # -------------------------------------------------
        # Deadline check
        # -------------------------------------------------
        if end_time  <= ms.deadline_of_microservice(self.topology):

            ms.status = 'running'
            ms.assigned_resource = cloud

            ms.latency = latency
            ms.spin_up_delay = spin_up_delay
            ms.service_time = service_time

            # Actual waiting time for spin up delay
            ms.wait_time = max(
                0,
                start_time - ms.arrival_time - latency
            )

            ms.start_time = start_time
            ms.end_time = end_time

            ms.response_time = end_time + latency - ms.arrival_time # latency is the communication downloading delay
            

            # -------------------------------------------------
            # Update cloud state
            # -------------------------------------------------
            cloud.current_storage -= ms.storage_req

            cloud.queue.append(ms)

            cloud.current_microservices.append(ms)
            
            return True, end_time

        # -------------------------------------------------
        # Rejected
        # -------------------------------------------------
        else:
            ms.status = 'rejected'
            ms.rejection_reason = 'incloud, deadline'
            
            return False, end_time
        


    def complete_execution(
        self,
        ms: Microservice,
        resource
    ):
        """
        Release resource after microservice completion.
        """

        ms.status = 'completed'

        task = ms.get_task_of_microservice(self.topology)

        task.completed_microservices.add(
            ms.microservice_id
        )

        # -------------------------------------------------
        # Edge resource cleanup
        # -------------------------------------------------

        if isinstance(resource, EdgeCloud):

            # Remove from execution slot
            if resource.current_microservice == ms:

                resource.current_microservice = None

            # Remove from queue
            if ms in resource.queue:

                resource.queue.remove(ms)

        # -------------------------------------------------
        # Cloud resource cleanup
        # -------------------------------------------------

        elif isinstance(resource, CentralCloud):

            if ms in resource.current_microservices:

                resource.current_microservices.remove(ms)

            if ms in resource.queue:

                resource.queue.remove(ms)

            resource.current_storage += ms.storage_req
                    
    def get_microservice(self, ms_id):
        for microservice in self.microservices:
            if microservice.microservice_id == ms_id:
                return microservice

    def preempt_microservice(
        self,
        victim: Microservice,
        edge: EdgeCloud
    ):

        victim.status = 'pending'

        victim.was_preempted = True
        victim.preemption_count += 1

        victim.start_time = None
        victim.end_time = None

        victim.assigned_resource = None

        if edge.current_microservice == victim:
            edge.current_microservice = None

        if victim in edge.queue:
            edge.queue.remove(victim)

        #---------------------------------------
        # DEBUGING PRINT
        #---------------------------------------
        # print(
        #     f"[PREEMPT] Victim={victim.microservice_id} "
        #     f"Task={victim.task_id} "
        #     f"Count={victim.preemption_count}"
        # )
        #edge.occupied_until = 0

    def find_preemption_candidate(
        self,
        incoming_ms: Microservice,
        edge: EdgeCloud
    ):

        victim = edge.current_microservice

        if victim is None:
            return None

        incoming_priority = (incoming_ms.get_task_of_microservice(self.topology).category)

        victim_priority = (victim.get_task_of_microservice(self.topology).category)

        if incoming_priority > victim_priority:
            return victim

        return None
    def can_preempt_for(
        self,
        incoming_ms,
        edge,
        current_time
    ):
        """
        Check whether preempting the currently running microservice
        would make it possible to execute incoming_ms on this edge.

        Returns
        -------
        bool
            True if incoming_ms can be scheduled after preemption.
        """

        # -----------------------------------------
        # Resource check
        # -----------------------------------------
        if not edge.has_enough_resource(incoming_ms):
            return False

        # -----------------------------------------
        # Communication latency
        # -----------------------------------------
        latency = self.topology.latency(
            incoming_ms,
            edge
        )

        # -----------------------------------------
        # Spin-up delay
        # -----------------------------------------
        spin_up_delay = self.topology.spin_up_delay(
            incoming_ms,
            edge
        )

        # -----------------------------------------
        # Execution time
        # -----------------------------------------
        service_time = (
            incoming_ms.instructions / edge.IPT
        )

        # -----------------------------------------
        # Assume edge becomes free immediately
        # after preemption
        # -----------------------------------------
        start_time = max(
            current_time,
            incoming_ms.arrival_time + latency,
            spin_up_delay
        )

        end_time = start_time + service_time

        deadline = incoming_ms.deadline_of_microservice(
            self.topology
        )

        # -----------------------------------------
        # Deadline feasibility
        # -----------------------------------------
        return end_time <= deadline