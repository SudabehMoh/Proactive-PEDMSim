# -*- coding: utf-8 -*-
"""
Spyder Editor

This is a temporary script file.
"""

import networkx as nx
import matplotlib.pyplot as plt

class Task:
    def __init__(self, task_id, arrival_time, deadline, category, task_microservices):
        self.task_id = task_id
        self.arrival_time = arrival_time
        self.deadline = deadline
        self.category = category
        self.task_microservices = task_microservices

        self.latency = 0
        self.start_time = None
        self.end_time = None
        self.wait_time = 0
        self.service_time = 0
        self.response_time = 0
        self.accepted = False # it shows that the task is done or isn't done
        self.status = 'pending'  # 'pending', 'running', 'completed'
        self.completed_microservices = set()  # Set to keep track of completed microservices

    def __str__(self):
         return f"task({self.task_id})"


    def update_task_status(self, topology):
        """
        Update task status according to the state of its microservices.
        """

        microservice_list = topology.get_microservice_list(self)

        # -------------------------------------------------
        # No microservices
        # -------------------------------------------------
        if not microservice_list:
            return

        # -------------------------------------------------
        # Rejected task
        # If at least one microservice is rejected
        # -------------------------------------------------
        if any(ms.status == 'rejected' for ms in microservice_list):

            self.status = 'rejected'
            self.accepted = False

            completed_ms = [
                ms for ms in microservice_list
                if ms.end_time is not None
            ]

            if completed_ms:
                self.end_time = max(
                    ms.end_time for ms in completed_ms
                )

            return

        # -------------------------------------------------
        # Completed task
        # -------------------------------------------------
        if all(ms.status == 'completed' for ms in microservice_list):

            self.status = 'completed'
            self.accepted = True

            # ---------------------------------------------
            # Start time
            # ---------------------------------------------
            start_times = [
                ms.start_time
                for ms in microservice_list
                if ms.start_time is not None
            ]

            if start_times:
                self.start_time = min(start_times)

            # ---------------------------------------------
            # End time
            # ---------------------------------------------
            end_times = [
                ms.end_time
                for ms in microservice_list
                if ms.end_time is not None
            ]

            if end_times:
                self.end_time = max(end_times)

            # ---------------------------------------------
            # Response time
            # ---------------------------------------------
            if self.end_time is not None:
                self.response_time = (
                    self.end_time - self.arrival_time
                )

            # ---------------------------------------------
            # Waiting time
            # ---------------------------------------------
            if self.start_time is not None:
                self.wait_time = max(
                    0,
                    self.start_time - self.arrival_time
                )

            # ---------------------------------------------
            # Aggregate latency
            # ---------------------------------------------
            self.latency = sum(
                ms.latency
                for ms in microservice_list
                if ms.latency is not None
            )

            # ---------------------------------------------
            # Aggregate service time
            # ---------------------------------------------
            self.service_time = sum(
                ms.service_time
                for ms in microservice_list
                if ms.service_time is not None
            )

        # -------------------------------------------------
        # Otherwise task is still active
        # -------------------------------------------------
        else:
            self.status = 'running'    
            
    def print_task(self):
        print(f"Task {self.task_id} with {len(self.task_microservices)} microservices")

    def draw_task_microservices_graph(self):
        """
        Draw a graph showing the microservices of a task and their dependencies.
        :param task: Task object containing microservices and their dependencies.
        """
        if not self.task_microservices:
            print(f"Task {self.task_id} has no microservices to display.")
            return

        # Create a directed graph
        graph = nx.DiGraph()

        # Add nodes for each microservice
        for microservice in self.task_microservices:
            graph.add_node(microservice.microservice_id, label=f"MS{microservice.microservice_id}")

        # Add edges for dependencies
        for microservice in self.task_microservices:
            for dependency in microservice.dependencies:
              graph.add_edge(dependency.microservice_id, microservice.microservice_id)

        # Draw the graph
        pos = nx.spring_layout(graph)  # You can use other layouts like circular_layout, shell_layout, etc.
        nx.draw(graph, pos, with_labels=True, labels=nx.get_node_attributes(graph, 'label'), node_color='skyblue', node_size=2000, font_size=10, font_weight='bold', arrowsize=20)
        plt.title(f"Task {self.task_id} Microservices and Dependencies")
        plt.show()
        


