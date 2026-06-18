# -*- coding: utf-8 -*-
"""
Created on Sat Jun 28 12:13:11 2025

@author: Sudabeh
"""
# Standard libraries
import random
import math
import logging
import time

# Third-party libraries
import numpy as np
import pandas as pd

# PEDMSim modules (ensure PEDMSim is in sys.path or project root is set)
from PRPEDMSim.topology import Topology
from PRPEDMSim.orchestrator import Orchestrator
from PRPEDMSim.microservice import Microservice
from PRPEDMSim.predictor import (PeakWorkloadPredictor, PredictionMode)


class Environment:
    def __init__(self, topology: Topology):
        self.orchestrator = Orchestrator(topology)
        self.topology = topology
        
        self.microservices = self.prepare_microservices()  # for EDMSim 
        self.current_time = 0
        self.completed_microservices = set()
        self.ready_microservices = []

        # Predictor 
        self.proactive_offloads = 0
        self.predictor = PeakWorkloadPredictor(
            topology=topology,
            mode=PredictionMode.TIME_WINDOW,
            history_size=10,
            window_duration=10,
            alpha=0.3
        )
        self.orchestrator.predictor = self.predictor

        # PREEMPTED attributes
        self.preempted_cat = {
            1: 0,
            2: 0,
            3: 0
        }

        self.benefited_cat = {
            1: 0,
            2: 0,
            3: 0
        }
    


    def prepare_microservices(self):
        """Prepare the list of microservices considering their dependencies without modifying originals"""
        print("Preparing microservices...")
        # Step 1: Creating a mapping from microservice_id to the microservice
        id_to_ms = {ms.microservice_id: ms for ms in self.topology.microservices}

        # Step 2: Creating a copy of the dependencies for topological sorting
        dependency_map = {ms.microservice_id: set(dep.microservice_id for dep in ms.dependencies)
                        for ms in self.topology.microservices}

        # Step 3: Microservices with no dependency
        ready_microservices = [id_to_ms[ms_id] for ms_id, deps in dependency_map.items() if not deps]
        ordered_microservices = []
        remaining = set(dependency_map.keys()) - set(ms.microservice_id for ms in ready_microservices)

        while ready_microservices:
            ready_microservices.sort(key=lambda x: x.arrival_time)
            ms = ready_microservices.pop(0)
            ordered_microservices.append(ms)

            # Removing this microservice from the dependencies of others
            for other_id in list(remaining):
                if ms.microservice_id in dependency_map[other_id]:
                    dependency_map[other_id].remove(ms.microservice_id)
                    if not dependency_map[other_id]:
                        ready_microservices.append(id_to_ms[other_id])
                        remaining.remove(other_id)

        if remaining:
            logging.warning(f"{len(remaining)} microservices could not be ordered due to unresolved dependencies or cycles.")
            for ms_id in remaining:
                ordered_microservices.append(id_to_ms[ms_id])  # Add remaining in arbitrary order

        # Just for test:
        for ms in ordered_microservices:
            logging.debug(f"Microservice {ms.microservice_id} (original deps: {[d.microservice_id for d in ms.dependencies]})")
          
        return ordered_microservices

    def reset(self):

        """Reset the environment to its initial state"""

        if not self.microservices:
            print("Warning: No microservices loaded.")
            return None

        # Reset simulation clock
        self.current_time = 0

        # Reset predictor
        self.predictor.reset()
        self.proactive_offloads = 0

        # Reset execution tracking       
        self.completed_microservices = set()
        self.ready_microservices = []

        # Reset all microservices
        for ms in self.microservices:

            ms.status = 'pending'

            ms.start_time = None
            ms.end_time = None

            ms.assigned_resource = None

            ms.latency = 0
            ms.wait_time = 0
            ms.service_time = 0
            ms.response_time = 0
            ms.data_transfer_time = 0

            # Reset PREEMPTED flag
            ms.preemption_count = 0
            ms.was_preempted = False

        # Reset all tasks
        for task in self.topology.tasks:

            task.completed_microservices = set()

            task.status = 'pending'
            task.accepted = False

            task.start_time = None
            task.end_time = None

            task.response_time = None
            task.wait_time = 0
            task.service_time = 0
            task.latency = 0

        # Reset edge clouds
        for edge in self.topology.edgeclouds:

            edge.queue.clear()

            edge.current_microservice = None

            edge.occupied = False
            edge.occupied_until = 0

        # Reset central clouds
        for cloud in self.topology.centralclouds:

            cloud.queue.clear()

            cloud.current_microservices.clear()

            cloud.counter_of_task_in = 0

            cloud.current_cpu = cloud.IPT
            cloud.current_storage = cloud.storage

            cloud.occupied_until = 0

        self.preempted_cat = {
            1: 0,
            2: 0,
            3: 0
        }

        self.benefited_cat = {
            1: 0,
            2: 0,
            3: 0
        }

        # Return initial state
        ready_microservices = self.get_ready_microservices()

        if not ready_microservices:
            return None


        first_ms = ready_microservices[0]

        return self._get_state(first_ms)
    

    def step(self, current_ms, action):
        """
        Execute one scheduling step using
        event-driven simulation.
        """

        # print(
        #     f"[STEP] "
        #     f"time={self.current_time:.2f} "
        #     f"ms={current_ms.microservice_id}"
        # )
        
        # ---------------------------------------------------
        # Initial values
        # ---------------------------------------------------

        success = False
        reward = 0
        done = False

        # Update Predictor
        self.predictor.update(current_ms,self.current_time)

        if self.should_offload_low_priority(current_ms):  
            self.proactive_offloads += 1 

            action = len(self.topology.edgeclouds) # Force cloud execution
            
        # ---------------------------------------------------
        # Ignore already processed microservices
        # ---------------------------------------------------

        if current_ms.status != 'pending':

            next_ready = self.get_ready_microservices()

            if next_ready:

                next_ready.sort(
                    key=lambda ms: (
                    -self.priority_score(ms),
                    ms.microservice_id
                    )
                )

                next_state = self._get_state(
                    next_ready[0]
                )

                return (
                    next_state,
                    0,
                    False,
                    False
                )

            else:

                done = True

                return (
                    None,
                    0,
                    done,
                    False
                )

        # ---------------------------------------------------
        # Debug print
        # ---------------------------------------------------

        
        
        # print(
        #     f"[STEP] "
        #     f"Scheduling MS={current_ms.microservice_id} "
        #     f"| current_time={self.current_time:.4f}"
        # )

        # ---------------------------------------------------
        # Edge allocation
        # ---------------------------------------------------

        if action < len(self.topology.edgeclouds):

            edge = self.topology.edgeclouds[action]

            if edge.has_enough_resource(current_ms):

                edge_busy = (
                    edge.current_microservice is not None
                    and edge.current_microservice.status == 'running'
                )

                # prediction = self.predictor.predict()

                # if (
                #     prediction.future_peak
                #     and prediction.dominant_category == 3
                # ):
                #     action = len(self.topology.edgeclouds)+ len(self.topology.centralclouds) -1  # action = cloud_action

                success, end_time = (
                    self.orchestrator._allocate_edge(
                        current_ms,
                        action
                    )
                )

                if (not success and edge_busy):
                    
                    victim = self.orchestrator.find_preemption_candidate(current_ms,edge)
                    

                    if (
                        victim is not None
                        and
                        self.orchestrator.can_preempt_for(
                            current_ms,
                            edge,
                            self.current_time
                        )
                    ):

                        # print(
                        #     f"[REALLOCATION] "
                        #     f"Incoming={current_ms.microservice_id} "
                        #     f"Edge={edge.edge_id}"
                        # )

                        victim_cat = (victim.get_task_of_microservice(self.topology).category)

                        self.preempted_cat[victim_cat] += 1

                        # Preempt victim
                        self.orchestrator.preempt_microservice(victim,edge)

                        # Retry allocation
                        success, end_time = (
                            self.orchestrator._allocate_edge(
                                current_ms,
                                action
                            )
                        )
                        if success:
                            incoming_cat = (current_ms.get_task_of_microservice(self.topology).category)
                            self.benefited_cat[incoming_cat] += 1

                        #-----------------------------------
                        # DEBUGGING Print
                        #-----------------------------------
                        # print(
                        #     f"[REALLOCATION SUCCESS] "
                        #     f"Incoming={current_ms.microservice_id}"
                        # )

                # print(
                #     f"action={action}, "
                #     f"success={success}, "
                #     f"status={current_ms.status}"
                # )

                reward = self._calculate_reward(
                    current_ms,
                    success,
                    end_time,
                    edge_bonus=True
                )

            else:

                current_ms.status = 'rejected'
                current_ms.rejection_reason = 'edge resource'

                reward = -100

        # ---------------------------------------------------
        # Cloud allocation
        # ---------------------------------------------------

        elif action < (
            len(self.topology.edgeclouds)
            + len(self.topology.centralclouds)
        ):

            cloud_index = (
                action - len(self.topology.edgeclouds)
            )

            cloud = self.topology.centralclouds[
                cloud_index
            ]

            if cloud.has_enough_resource(current_ms):

                success, end_time = (
                    self.orchestrator._allocate_cloud(
                        current_ms,
                        action
                    )
                )
                
                reward = self._calculate_reward(
                    current_ms,
                    success,
                    end_time,
                    edge_bonus=False
                )

            else:

                current_ms.status = 'rejected'
                current_ms.rejection_reason = 'cloud resource'

                reward = -100

        # ---------------------------------------------------
        # Invalid action
        # ---------------------------------------------------

        else:

            current_ms.status = 'rejected'
            current_ms.rejection_reason = 'invalid action'

            reward = -500

        # ---------------------------------------------------
        # Update system state
        # ---------------------------------------------------

        self._update_system_state()
        self._propagate_rejection()
        
        # ---------------------------------------------------
        # Get ready microservices
        # ---------------------------------------------------

        ready_microservices = (
            self.get_ready_microservices()
        )

        # print(
        #     "READY:",
        #     [
        #         ms.microservice_id
        #         for ms in ready_microservices
        #     ]
        # )

        # ---------------------------------------------------
        # Event-driven simulation loop
        # ---------------------------------------------------

        while not ready_microservices:

            previous_time = self.current_time

            # Advance simulation clock
            self._jump_to_next_event()

            # No future event exists
            if self.current_time == previous_time:

                break

            # Update completed executions
            self._update_system_state()

            self._propagate_rejection()

           

            # Recompute ready microservices
            ready_microservices = (
                self.get_ready_microservices()
            )

        # ---------------------------------------------------
        # Normal transition
        # ---------------------------------------------------

        if ready_microservices:

            ready_microservices.sort(
                key=lambda ms: (
                -self.priority_score(ms),
                ms.microservice_id
                )
            )

            next_ms = ready_microservices[0]

            next_state = self._get_state(next_ms)

            return (
                next_state,
                reward,
                False,
                success
            )

        # ---------------------------------------------------
        # No ready microservices remain
        # Final rejection propagation
        # ---------------------------------------------------

        self._propagate_final_rejections()

        unfinished_microservices = [

            ms for ms in self.microservices

            if ms.status in [
                'pending',
                'running'
            ]
        ]

        # if unfinished_microservices:

        #     print(
        #         "Deadlock pending:",
        #         [
        #             ms.microservice_id
        #             for ms in unfinished_microservices
        #         ]
        #     )

        # ---------------------------------------------------
        # Episode finished
        # ---------------------------------------------------

        done = True

        return (
            None,
            reward,
            done,
            success
        )
    
    def _get_state(self, microservice: Microservice):
        """
        Create a compact discrete state representation for Q-learning.
        """

        current_time = self.current_time

        category = microservice.get_task_of_microservice(self.topology).category
        # -------------------------------------------------
        # Remaining time until deadline
        # -------------------------------------------------
        deadline = self._get_task_deadline(microservice.task_id)

        relative_deadline = deadline - microservice.arrival_time
        time_remaining = max(0, deadline - current_time)

        urgency_ratio = time_remaining / relative_deadline
        

        #urgency_ratio = 1 - (time_remaining / relative_deadline) 

  
        urgency_bin = min(int(urgency_ratio * 10), 9) 

        # Discretize remaining time
        
        time_bin = min(int(time_remaining // 20), 10) # We can use this parameter instead of urgency_bin

        # -------------------------------------------------
        # Computational demand
        # -------------------------------------------------
        instruction_bin = min(
            int(microservice.instructions // 250),
            20
        )

        # -------------------------------------------------
        # Communication load
        # -------------------------------------------------
        bytes_bin = min(
            int(microservice.bytes // 100),
            10
        )

        # -------------------------------------------------
        # Storage requirement
        # -------------------------------------------------
        storage_bin = min(
            int(microservice.storage_req // 5),
            10
        )

        # -------------------------------------------------
        # Resource availability
        # -------------------------------------------------
        free_edge_count = sum(
            1
            for edge in self.topology.edgeclouds
            if edge.occupied_until <= current_time
        )

        # -------------------------------------------------
        # Final state
        # -------------------------------------------------
        discrete_state = (
            category,
            instruction_bin,
            bytes_bin,
            storage_bin,
            urgency_bin,
            free_edge_count
        )

        # Store visited states
        self.visited_states.add(discrete_state)

        # print(discrete_state)
        return discrete_state    
    def _get_task_deadline(self, task_id):
        """Finding the corresponding task deadline"""
        for task in self.topology.tasks:
            if task.task_id == task_id:
                return task.deadline
        return float('inf')

    def _check_dependencies(self, ms):
        """
        Check whether all dependencies
        are completed successfully.

        If any parent is rejected,
        propagate rejection immediately.
        """

        # No dependency
        if not ms.dependencies:
            return True

        for parent in ms.dependencies:

            # Parent rejected
            if parent.status == 'rejected':

                ms.status = 'rejected'
                ms.rejection_reason = 'dependency'

                # print(
                #     f"[PROPAGATED REJECTION] "
                #     f"MS={ms.microservice_id}"
                # )

                return False

            # Parent not completed yet
            if parent.status != 'completed':

                return False

        return True
    def _get_resources_status(self):
        """status of exiting resource"""   
        return {
            'edge_servers': [
                {
                    'id': edge.edge_id,
                    'occupied_until': edge.occupied_until,
                    'queue_length': len(edge.queue),
                    'available_storage': edge.storage - sum(ms.bytes for ms in edge.queue)
                }
                for edge in self.topology.edgeclouds
            ],
            'cloud': {
                'occupied_until': max(c.occupied_until for c in self.topology.centralclouds),
                'available_storage': max(c.storage for c in self.topology.centralclouds)
            }
        }
    
    def _propagate_rejection(self):

        changed = True

        while changed:

            changed = False

            for ms in self.microservices:

                if ms.status != 'pending':
                    continue

                for parent in ms.dependencies:

                    if parent.status == 'rejected':

                        ms.status = 'rejected'
                        ms.rejection_reason = 'dependency'

                        # print(
                        #     f"PROPAGATED: "
                        #     f"MS={ms.microservice_id} "
                        #     f"FROM={parent.microservice_id}"
                        # )

                        changed = True

                        break
    
    def _propagate_final_rejections(self):
        """
        Propagate rejection to all descendants
        of rejected microservices.
        """

        changed = True

        while changed:

            changed = False

            for ms in self.microservices:

                if ms.status != 'pending':
                    continue

                for parent in ms.dependencies:

                    if parent.status == 'rejected':

                        ms.status = 'rejected'
                        ms.rejection_reason = 'dependency'

                        # print(
                        #     f"[FINAL PROPAGATED REJECTION] "
                        #     f"MS={ms.microservice_id}"
                        # )

                        changed = True

                        break
    
    def _calculate_reward(
        self,
        microservice: Microservice,
        success: bool,
        end_time: float,
        edge_bonus: bool = False
    ):
        """
        Reward function for microservice scheduling.

        Objectives:
        - Encourage successful scheduling
        - Encourage deadline satisfaction
        - Prefer edge execution
        - Penalize long waiting times
        - Penalize rejected executions
        """

        category = microservice.get_task_of_microservice(self.topology).category
        category_weight = {
            1: 1,
            2: 1.2,
            3: 1.5
        }
        # -------------------------------------------------
        # Hard rejection penalty
        # -------------------------------------------------
        if not success:
            return -category_weight[category] * 1000


        # -------------------------------------------------
        # Deadline slack bonus
        # -------------------------------------------------
        deadline = microservice.deadline_of_microservice(self.topology)

        relative_deadline = deadline - microservice.arrival_time

        slack_time =  deadline - microservice.end_time

        slack_ratio = slack_time / relative_deadline

        #slack_ratio = slack_time / deadline

        

        # -------------------------------------------------
        # Waiting time penalty
        # -------------------------------------------------
        latency_penalty = microservice.latency

        reward = (
            1000
            + 100 * slack_ratio
            - latency_penalty
        )

        reward *= category_weight[category]

        # -------------------------------------------------
        # Edge execution bonus
        # -------------------------------------------------
        if edge_bonus:
            reward += 150

        # print(
        #     f"cat={microservice.get_task_of_microservice(self.topology).category}, "
        #     f"deadline={deadline:.2f}, "
        #     f"end={microservice.end_time:.2f}, "
        #     f"slack={slack_time:.2f}, "
        #     f"slack_ratio={slack_ratio:.4f}, "
        #     f"latency={microservice.latency:.4f}, "
        #     f"reward={reward:.4f}"
        # )
        return reward
    def _calculate_reward4(
        self,
        microservice: Microservice,
        success: bool,
        end_time: float,
        edge_bonus: bool = False
    ):
        """
        Reward function for microservice scheduling.

        Objectives:
        - Encourage successful scheduling
        - Encourage deadline satisfaction
        - Prefer edge execution
        - Penalize long waiting times
        - Penalize rejected executions
        """

        # -------------------------------------------------
        # Hard rejection penalty
        # -------------------------------------------------
        if not success:
            return -1000

        reward = 0

        # -------------------------------------------------
        # Base reward for successful allocation
        # -------------------------------------------------
        reward += 1000

        # -------------------------------------------------
        # Deadline slack bonus
        # -------------------------------------------------
        deadline = microservice.deadline_of_microservice(self.topology)

        slack_time =  deadline - microservice.end_time

        slack_ratio = slack_time / deadline

        reward +=  slack_time

        # -------------------------------------------------
        # Edge execution bonus
        # -------------------------------------------------
        if edge_bonus:
            reward *= 1.5

        # -------------------------------------------------
        # Waiting time penalty
        # -------------------------------------------------
        latency_penalty = microservice.latency

        reward -= latency_penalty

        # -------------------------------------------------
        # Response time penalty
        # -------------------------------------------------
        response_penalty = microservice.response_time 

        reward -= response_penalty

        return reward
    def _calculate_reward3(
        self,
        microservice: Microservice,
        success: bool,
        end_time: float,
        edge_bonus: bool = False
    ):
        """
        Reward function for microservice scheduling.

        Objectives:
        - Encourage successful scheduling
        - Encourage deadline satisfaction
        - Prefer edge execution
        - Penalize long waiting times
        - Penalize rejected executions
        """

        # -------------------------------------------------
        # Hard rejection penalty
        # -------------------------------------------------
        if not success:
            return -100

        reward = 0

        # -------------------------------------------------
        # Base reward for successful allocation
        # -------------------------------------------------
        reward += 50

        # -------------------------------------------------
        # Deadline slack bonus
        # -------------------------------------------------
        deadline = microservice.deadline_of_microservice(self.topology)

        slack_time = max(0 , deadline - microservice.end_time)

        slack_ratio = slack_time / deadline

        reward += 30 * slack_ratio

        # -------------------------------------------------
        # Edge execution bonus
        # -------------------------------------------------
        if edge_bonus:
            reward += 10

        # -------------------------------------------------
        # Waiting time penalty
        # -------------------------------------------------
        waiting_penalty = min(microservice.wait_time / 100 , 20)

        reward -= waiting_penalty

        # -------------------------------------------------
        # Response time penalty
        # -------------------------------------------------
        response_penalty = min(microservice.response_time / 200 , 20)

        reward -= response_penalty

        return reward
    def _calculate_reward2(
        self,
        microservice: Microservice,
        success: bool
    ):
        """
        Reward function aligned with system objectives:

        Objectives:
        - Maximize acceptance rate
        - Minimize response time
        - Minimize latency
        """

        # -------------------------------------------------
        # Rejected microservice
        # -------------------------------------------------
        if not success:
            return -150

        reward = 0

        # -------------------------------------------------
        # Acceptance reward
        # -------------------------------------------------
        reward += 100

        # -------------------------------------------------
        # Response time penalty
        # -------------------------------------------------
        response_penalty = (microservice.response_time / 100)

        reward -= response_penalty

        # -------------------------------------------------
        # Communication latency penalty
        # -------------------------------------------------
        latency_penalty = (microservice.latency * 20)

        reward -= latency_penalty

        # -------------------------------------------------
        # Waiting time penalty
        # -------------------------------------------------
        waiting_penalty = (microservice.wait_time / 50)

        reward -= waiting_penalty

        return reward
    def _calculate_reward1(self, microservice: Microservice, success, end_time, edge_bonus=False):
        """Balanced reward design with category-aware weighting."""
        
        if success==False and end_time==None:
            return -1000 
        
        microservice_deadline = self._get_task_deadline(microservice.task_id)
        task = next(t for t in self.topology.tasks if t.task_id == microservice.task_id)
        category = task.category  # 1, 2, or 3

        # Priority Weight (Soft)
        # cat=1 → 1.0 , cat=2 → 1.3 , cat=3 → 1.6
        #priority_weight = 1 + 0.3 * (category - 1)
        #priority_weight = category
        priority_weight = 1

        # ------------------------
        # Case 1: Deadline met
        # ------------------------
        
        if end_time <= microservice_deadline:
            time_saved = microservice_deadline - end_time

            # base reward
            reward = time_saved * priority_weight
           
            if edge_bonus:
                reward *= 1.5  # edge bonus

        # ------------------------
        # Case 2: Deadline missed
        # ------------------------
        else:
            time_over = end_time - microservice_deadline

            # penalty by priority
            reward = -time_over * priority_weight  

        return reward


    def _update_system_state(self):
        """
        Update the global system state.

        This method:
        - Completes finished microservices
        - Releases occupied resources
        - Updates completed microservice list
        """
        #print(f'update system state | Current time: {self.current_time}')
        # ---------------------------------------------------
        # Update edge clouds
        # ---------------------------------------------------

        for edge in self.topology.edgeclouds:

            ms = edge.current_microservice

            if ms is None:
                continue

            # Complete execution only if finish time reached
            if (
                ms.status == 'running'
                and ms.end_time <= self.current_time
            ):
                #print(f'complete ms {ms.microservice_id} in edge {edge.edge_id}')
                self.orchestrator.complete_execution(ms, edge)

                self.completed_microservices.add(
                    ms.microservice_id
                )

        # ---------------------------------------------------
        # Update central clouds
        # ---------------------------------------------------

        for cloud in self.topology.centralclouds:

            # Iterate over a copy to avoid modification issues
            running_microservices = list(
                cloud.current_microservices
            )

            for ms in running_microservices:

                if (
                    ms.status == 'running'
                    and ms.end_time <= self.current_time
                ):
                    #print(f'complete ms{ms.microservice_id} in cloud {cloud.cloud_id}')
                    self.orchestrator.complete_execution(
                        ms,
                        cloud
                    )

                    self.completed_microservices.add(
                        ms.microservice_id
                    )
    def _jump_to_next_event(self):
        """
        Advance simulation time to the nearest future event.

        Future events include:
        - Arrival of pending microservices
        - Completion of running microservices
        """
        ready_microservices = self.get_ready_microservices()
        if ready_microservices:
            return
        
        future_times = []

        # ---------------------------------------------------
        # Future arrivals
        # ---------------------------------------------------

        for ms in self.microservices:

            if (
                ms.status == 'pending'
                and ms.arrival_time > self.current_time
            ):

                future_times.append(ms.arrival_time)

        # ---------------------------------------------------
        # Future completions on edge clouds
        # ---------------------------------------------------

        for edge in self.topology.edgeclouds:

            ms = edge.current_microservice

            if (
                ms is not None
                and ms.status == 'running'
                and ms.end_time > self.current_time
            ):

                future_times.append(ms.end_time)

        # ---------------------------------------------------
        # Future completions on central clouds
        # ---------------------------------------------------

        for cloud in self.topology.centralclouds:

            for ms in cloud.current_microservices:

                if (
                    ms.status == 'running'
                    and ms.end_time > self.current_time
                ):

                    future_times.append(ms.end_time)

        # ---------------------------------------------------
        # Advance time
        # ---------------------------------------------------
        
        
        #print(f"[FUTURE TIMES] {sorted(future_times)}")


        if future_times:
            old_time = self.current_time
            self.current_time = min(future_times)
            #print(f"[TIME ADVANCE] " f"{old_time:.4f} --> {self.current_time:.4f}")

            
            self.predictor.tick(self.current_time)          

            # Update system state after time jump
            self._update_system_state()
   
    def get_ready_microservices(self):

        """
        Return executable microservices at current time.
        """

        ready_microservices = []

        for ms in self.microservices:

            if (
                ms.status == 'pending'
                and self._check_dependencies(ms)
                and ms.arrival_time <= self.current_time
            ):

                # print(
                #     f"[READY] "
                #     f"MS={ms.microservice_id} | "
                #     f"arrival={ms.arrival_time:.4f} | "
                #     f"current_time={self.current_time:.4f}"
                # )

                ready_microservices.append(ms)
        
        ready_microservices.sort(
            key=lambda ms: (
                -self.priority_score(ms),
                ms.microservice_id
            )
        )

        return ready_microservices
    
    def priority_score(self, ms):

        category = ms.get_task_of_microservice(
            self.topology
        ).category

        deadline = self._get_task_deadline(
            ms.task_id
        )

        time_remaining = max(
            1,
            deadline - self.current_time
        )

        return  category/ time_remaining
    
    def should_offload_low_priority(self, microservice):

        
        category = microservice.get_task_of_microservice(self.topology).category

        if category != 1:
            return False

        prediction = self.predictor.predict()

        # print(
        #     f"[PREDICTOR] "
        #     f"peak={prediction.future_peak} "
        #     f"severity={prediction.peak_severity:.2f} "
        #     f"dominant={prediction.dominant_category}"
        # )

        # return (
        #     prediction.future_peak
        #     and prediction.peak_severity >= 0.8
        # )
        # return (
        #     category == 1
        #     and prediction["severity"] > 0.1
        # )
    
        return (
            prediction.future_peak
            and prediction.dominant_category in [2, 3]
            and category == 1
        )
    
    def get_valid_actions(self, microservice):
        """
        Return all resources that currently have
        enough capacity for the given microservice.

        Action numbering:
        0 ... N_edge-1        -> Edge clouds
        N_edge ... N_total-1  -> Central clouds
        """

        valid_actions = []

        # Edge resources
        for i, edge in enumerate(self.topology.edgeclouds):

            if edge.has_enough_resource(microservice):

                valid_actions.append(i)

        # Cloud resources
        offset = len(self.topology.edgeclouds)

        for j, cloud in enumerate(self.topology.centralclouds):

            if cloud.has_enough_resource(microservice):

                valid_actions.append(offset + j)

        return valid_actions