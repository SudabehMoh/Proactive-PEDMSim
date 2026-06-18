# -*- coding: utf-8 -*-
"""
Created on Sat Jun 28 12:02:03 2025

@author: Sudabeh
"""
import logging


logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')


import csv
from dataclasses import field
from ast import literal_eval
from itertools import combinations
import networkx as nx
import random
import numpy as np
import pandas as pd
from PRPEDMSim.task import Task
from PRPEDMSim.microservice import Microservice, Message
from PRPEDMSim.edgecloud import EdgeCloud
from PRPEDMSim.centralcloud import CentralCloud
import matplotlib.pyplot as plt


class Topology:

    #iot_edge_bw = 1000 #G per Sec
    #iot_edge_pr = 10 #second
    #edge_edge_bw = 40000 #G per Sec
    #edge_edge_pr = 0.005 #second
    #edge_cloud_bw =  5000 # G per Sec
    #edge_cloud_pr = 100   #second

    # ================================
    # Realistic Network Parameters
    # ================================
    # IoT → Edge (Wireless Access)
    # Typical Wi-Fi / 5G access conditions with moderate bandwidth
    iot_edge_bw = 50        # Mbps   → realistic IoT/WiFi throughput
    iot_edge_pr = 0.01      # sec    → ~10 ms one-way delay

    # Edge ↔ Edge (Backhaul Fiber)
    # Typical aggregation/backhaul fiber links (10–40 Gbps) with ms-level latency
    edge_edge_bw = 10000    # Mbps   → 40 Gbps fiber backhaul
    edge_edge_pr = 0.001    # sec    → ~1 ms latency (short metro fiber)

    # Edge → Cloud (WAN)
    # Typical WAN connection between edge nodes and a regional cloud
    # edge_cloud_bw = 1000    # Mbps   → 1 Gbps uplink to cloud
    # edge_cloud_pr = 0.05    # sec    → 50 ms one-way WAN latency
    edge_cloud_bw = 50     # Mbps   → 0.2 Gbps uplink to cloud
    edge_cloud_pr = 0.08    # sec    → 80 ms one-way WAN latency

    # =========================================
    # Future High-Capacity Network Parameters
    # =========================================
    # IoT → Edge (Next-generation Wireless Access)
    # Wi-Fi 7 / 5G URLLC capabilities with ultra-low latency
    #iot_edge_bw = 500       # Mbps   → high-speed future IoT/WiFi7 access
    #iot_edge_pr = 0.002     # sec    → ~2 ms one-way latency (URLLC-grade)

    # Edge ↔ Edge (Next-gen Backhaul Fiber)
    # Terabit-class optical networks with extremely low propagation delay
    #edge_edge_bw = 200000   # Mbps   → 200 Gbps next-generation fiber
    #edge_edge_pr = 0.0002   # sec    → 0.2 ms latency (advanced optical switching)

    # Edge → Cloud (Future WAN)
    # Next-gen WAN with edge-integrated cloud regions (distributed cloud)
    #edge_cloud_bw = 10000   # Mbps   → 10 Gbps cloud uplink
    #edge_cloud_pr = 0.01    # sec    → 10 ms one-way cloud latency (near-edge cloud)




    def __init__(self):
        self.graph = nx.Graph()
        self.microservices = []
        self.messages = []
        self.tasks = []
        self.edgeclouds = []
        self.centralclouds = []


    def add_centralclouds(self):
        for r in self.edgeclouds:
            for c in self.centralclouds:
                self.graph.add_edge(r, c, bandwidth = Topology.edge_cloud_bw , propagation_delay = Topology.edge_cloud_pr)

    def create_backhaul_network(self ):
        # The bandwidth and propagation delay in "constant" in all links of backhaul network
        for node1, node2 in combinations(self.edgeclouds,2):
            self.graph.add_edge(node1, node2, bandwidth = Topology.edge_edge_bw , propagation_delay = Topology.edge_edge_pr)

    def add_task_to_edgecloud_random(self):
        # The bandwidth and propagation delay in "constant" in all links between task and edgecloud
        number_of_edge_servers=len(self.edgeclouds)
        for s in self.tasks:
            dev=random.choice(self.edgeclouds)
            self.graph.add_edge(s,dev,bandwidth = Topology.iot_edge_bw, propagation_delay = Topology.iot_edge_pr)

    def nearest_resource(self, task:Task):
        nearest_resource = list(self.graph.neighbors(task))
        return nearest_resource


    def latency(self, ms: Microservice, resource):

        def tx_delay(MBytes_, bw_Mbps):
            return (MBytes_ * 8) / (bw_Mbps) # byte is MB , bandwidth is Mbps


        # IoT → Edge
        iot_edge_latency = (
            tx_delay(ms.bytes, Topology.iot_edge_bw)
            + Topology.iot_edge_pr
        )

        # Edge ↔ Orchestrator (Fiber)
        edge_edge_latency = (
            tx_delay(ms.bytes, Topology.edge_edge_bw)
            + Topology.edge_edge_pr
        )

        # Orchestrator → Cloud (WAN)
        edge_cloud_latency = (
            tx_delay(ms.bytes, Topology.edge_cloud_bw)
            + Topology.edge_cloud_pr
        )

        home_edge = self.nearest_resource(ms.get_task_of_microservice(self))
        if resource in self.edgeclouds:
            if resource == home_edge:
                return iot_edge_latency
            else:
                return (
                    iot_edge_latency
                    + edge_edge_latency
                )
        else:
            return (
                iot_edge_latency
                +  edge_cloud_latency
            )

    # It calculates the dependency ready time
    def spin_up_delay( 
        self,
        microservice,
        resource
    ):
        """
        Calculate the earliest time at which all
        dependency data become available.

        Returns
        -------
        float
            Absolute ready time.
        """

        # No dependencies
        if not microservice.dependencies:
            return 0.0

        ready_times = []

        for parent in microservice.dependencies:

            msg = self.get_message_between(
                parent,
                microservice
            )

            if msg is None:
                continue

            sender_resource = parent.assigned_resource
            receiver_resource = resource

            if sender_resource is None:
                continue

            # ------------------------------------------
            # Communication delay
            # ------------------------------------------

            if sender_resource == receiver_resource:

                transfer_delay = 0.0

            else:

                sender_is_edge = isinstance(
                    sender_resource,
                    EdgeCloud
                )

                receiver_is_edge = isinstance(
                    receiver_resource,
                    EdgeCloud
                )

                sender_is_cloud = isinstance(
                    sender_resource,
                    CentralCloud
                )

                receiver_is_cloud = isinstance(
                    receiver_resource,
                    CentralCloud
                )

                # KB → Mb
                data_mb = (msg.data * 8) / 1000

                # Edge ↔ Edge
                if sender_is_edge and receiver_is_edge:

                    transfer_delay = (data_mb / self.edge_edge_bw) + self.edge_edge_pr

                # Edge ↔ Cloud
                elif (sender_is_edge and receiver_is_cloud) or (sender_is_cloud and receiver_is_edge):

                    transfer_delay = (data_mb / self.edge_cloud_bw) + self.edge_cloud_pr

                # Cloud ↔ Cloud
                else:

                    transfer_delay = 0.0

            ready_time = (parent.end_time+ transfer_delay)

            ready_times.append(ready_time)

        if not ready_times:
            return 0.0

        return max(ready_times)
    
        
    def get_message_between(self, sender, receiver):
        for msg in self.messages:         
            if msg.sender.microservice_id == sender.microservice_id and msg.receiver.microservice_id == receiver.microservice_id:
                return msg
        return None

    def connected_tasks(self, edge_cloud:EdgeCloud):
        connected_tasks = []
        for node in self.graph.neighbors(edge_cloud):
            if node in self.tasks:
                connected_tasks.append(node)
        return connected_tasks

    def get_microservice_list(self , task:Task):
        microservice_list = []
        for microservice_id in task.task_microservices:
            for microservice in self.microservices:
                if microservice.microservice_id == microservice_id:
                    microservice_list.append(microservice)
                    break
        return microservice_list
    def create_random_microservices_for_tasks(self):
        for task in self.tasks:
            task.task_microservices = [random.choice(self.microservices) for _ in range(random.randint(1, 3))]

    def create_random_messages(self, filename):
        messages = []
        message_id = 0           
        for receiver in self.microservices:
            if hasattr(receiver, 'dependencies') and receiver.dependencies:
                print(f"Receiver: {receiver.microservice_id}, Dependencies: {[d.microservice_id for d in receiver.dependencies]}")
                for sender in receiver.dependencies:
                    data = random.randint(1000, 2000)
                    msg = Message(message_id, sender, receiver, data)
                    messages.append(msg)
                    message_id += 1
            else:
                print(f"Receiver {receiver} has no dependencies.")

        self.save_messages_to_csv(messages, filename)


    def read_tasks_from_csv2(self, filename, microservices_source=None):
        # اگر میکروسرویس‌ها از قبل خوانده نشده‌اند، آن‌ها را بخوانید
        if not hasattr(self, 'microservices') and microservices_source:
            self.read_microservices_from_csv(microservices_source)

        # ایجاد نگاشت از microservice_id به شیء Microservice
        id_to_microservice = {ms.microservice_id: ms for ms in self.microservices}

        with open(filename, 'r') as csvfile:
            reader = csv.reader(csvfile)
            header = next(reader)  # خواندن هدر

            for row in reader:
                task_id = int(row[0])
                arrival_time = int(row[1])
                deadline = int(row[2])
                category = int(row[3])
                task_microservices_str = row[4]

                # تبدیل رشته به لیست microservice_idها
                microservice_ids = [int(x.strip()) for x in task_microservices_str.strip("[]").split(',') if x.strip()]

                # تبدیل microservice_idها به اشیاء Microservice
                task_microservices = [
                    id_to_microservice[ms_id]
                    for ms_id in microservice_ids
                    if ms_id in id_to_microservice
                ]

                # ایجاد تسک با اشیاء میکروسرویس
                task = Task(task_id, arrival_time, deadline, category, task_microservices)
                self.tasks.append(task)
    def read_tasks_from_csv(self, filename):
        with open(filename, 'r') as csvfile:
            reader = csv.reader(csvfile)
            # Read the header
            header = next(reader)
            #print("Header:", header)

            # Read and print each row of file
            for row in reader:
                task_id = int(row[0])
                arrival_time = int(row[1])
                deadline = int(row[2])
                category = int(row[3])
                task_microservices_str = row[4]
                task_microservices = [int(x.strip()) for x in task_microservices_str.strip("[]").split(',') if x.strip()]
                task = Task(task_id, arrival_time, deadline, category, task_microservices)
                self.tasks.append(task)

    def save_tasks_to_csv(self,tasks, filename):

        fieldnames = [
            'task_id',
            'arrival_time',
            'category',
            'latency',
            'start_time',            
            'wait_time',
            'service_time',
            'response_time',
            'accepted',
            'end_time',
            'deadline',
            'status',
            'task_microservices',
            'completed_microservices'
        ]

        # آماده‌سازی داده‌ها برای ذخیره
        rows = []
        for task in tasks:
            rows.append({
                'task_id': task.task_id,
                'arrival_time': task.arrival_time,
                'category' : task.category,
                'latency' : task.latency,
                'start_time': task.start_time,
                'wait_time': task.wait_time,
                'service_time': task.service_time,
                'response_time': task.response_time,
                'accepted': task.accepted,
                'end_time': task.end_time,
                'deadline': task.deadline,
                'status': task.status,
                'task_microservices' : task.task_microservices,
                'completed_microservices' : task.completed_microservices
            })

        # Write in CSV file
        with open(filename, mode='w', newline='', encoding='utf-8') as file:
            writer = csv.DictWriter(file, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)


    def read_microservices_from_csv(self, filename):
        temp_microservices = []
        id_to_microservice = {}

        with open(filename, 'r') as csvfile:
            reader = csv.reader(csvfile)
            header = next(reader)

            for row in reader:
                task_id = int(row[0])
                microservice_id = int(row[1])
                instructions = float(row[2])
                bytes = float(row[3])
                dependencies_str = row[4]
                arrival_time = int(row[5])
                storage_req = float(row[6])

                dependency_ids = [int(x.strip()) for x in dependencies_str.strip("[]").split(',') if x.strip()]
                
                microservice = Microservice(task_id, microservice_id, instructions, bytes, [], arrival_time, storage_req)
                microservice._dependency_ids = dependency_ids  # ✅ temporarily store
                temp_microservices.append(microservice)
                id_to_microservice[microservice_id] = microservice

        # ✅ Now resolve dependencies per microservice
        for microservice in temp_microservices:
            microservice.dependencies = [
                id_to_microservice[dep_id]
                for dep_id in microservice._dependency_ids
                if dep_id in id_to_microservice
            ]
            
            del microservice._dependency_ids  # Clean up

        self.microservices.extend(temp_microservices)
        

    def save_microservices_to_csv(self,microservices, filename):

        fieldnames = [
            'task_id',
            'microservice_id',
            'instructions',
            'bytes',
            'dependencies',
            'storage_req',
            'status',
            'arrival_time',
            'start_time',
            'latency',
            'wait_time',
            'service_time',
            'response_time',
            'spin_up_delay',
            'end_time',
            'deadline',
            'assigned_resource',
            'nearest_resource',
            'resource_IPT',
            'resource_storage'

        ]

        # آماده‌سازی داده‌ها برای ذخیره
        rows = []
        for ms in microservices:
            # تبدیل زمان‌ها به رشته اگر None نباشند
            #start_time = ms.start_time if ms.start_time else None
            #end_time = ms.end_time if ms.end_time else None
            #arrival_time = ms.arrival_time if isinstance(ms.arrival_time, datetime) else ms.arrival_time

            # تبدیل لیست وابستگی‌ها به رشته
            dependencies = ",".join([str(dep.microservice_id) for dep in ms.dependencies])
            resource = ms.assigned_resource
            nearest = self.nearest_resource(ms.get_task_of_microservice(self))
            nearest_resource_id = nearest[0].edge_id
            nearest_resource = self.edgeclouds[nearest_resource_id]
            rows.append({
                'task_id': ms.task_id,
                'microservice_id': ms.microservice_id,
                'instructions': ms.instructions,
                'bytes': ms.bytes,
                'dependencies': dependencies,
                'storage_req': ms.storage_req,
                'status': ms.status,
                'arrival_time': ms.arrival_time,
                'start_time': ms.start_time,
                'latency': ms.latency,
                'wait_time': ms.wait_time,
                'service_time': ms.service_time,
                'response_time': ms.response_time,
                'spin_up_delay': ms.spin_up_delay,
                'end_time': ms.end_time,
                'deadline': ms.deadline_of_microservice(self),
                'assigned_resource': ms.assigned_resource,
                'nearest_resource': nearest_resource,
                'resource_IPT': resource.IPT if resource is not None else None,
                'resource_storage': resource.storage if resource is not None else None

            })

            
        # Write in CSV file
        with open(filename, mode='w', newline='', encoding='utf-8') as file:
            writer = csv.DictWriter(file, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

        print(f"Data saved to {filename}")


    def save_messages_to_csv(self, messages, filename):
        fieldnames = [
            'message_id',
            'sender',
            'receiver',
            'data',
        ]

        # Ready of data for saving
        rows = []
        for message in messages:
            rows.append({
                'message_id': message.message_id,
                'sender': message.sender.microservice_id,
                'receiver': message.receiver.microservice_id,
                'data': message.data,
            })

        # Save data in csv file
        with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

            # Write Header
            writer.writeheader()

            # Write all rows
            writer.writerows(rows)

        print(f"messegase is saved to {filename} successfully.")

    def read_messages_from_csv(self, filename):
        id_to_ms = {ms.microservice_id: ms for ms in self.microservices}

        with open(filename, 'r') as csvfile:
            reader = csv.reader(csvfile)
            header = next(reader)

            for row in reader:
                message_id = int(row[0])
                sender_id = int(row[1])
                receiver_id = int(row[2])
                data = int(row[3])

                sender = id_to_ms.get(sender_id)
                receiver = id_to_ms.get(receiver_id)

                if sender is None or receiver is None:
                    print(f"[WARNING] sender or receiver not found for message {message_id}")
                    continue

                message = Message(message_id, sender, receiver, data)
                self.messages.append(message)



    def display_graph1(self):
            pos = nx.spring_layout(self.graph)
            labels = {node: f"({str(node)})" for node, attrs in self.graph.nodes(data=True)}
            edge_labels = {(node1, node2): f"BW: {attrs['bandwidth']}- PR: {attrs['propagation_delay']}" for node1, node2, attrs in self.graph.edges(data=True)}

            plt.figure(figsize=(12, 8))
            nx.draw(self.graph, pos, with_labels=True, labels=labels, node_size=3000, node_color='lightblue', font_size=10, font_weight='bold')
            nx.draw_networkx_edge_labels(self.graph, pos, edge_labels=edge_labels, font_color='red')
            plt.show()

    def display_graph(self):
        pos = nx.spring_layout(self.graph)
    
        # برچسب نودها
        labels = {node: f"{node}" for node in self.graph.nodes()}
    
        # برچسب یال‌ها
        edge_labels = {
            (n1, n2): f"BW: {attrs['bandwidth']} - PR: {attrs['propagation_delay']}"
            for n1, n2, attrs in self.graph.edges(data=True)
        }
    
        # رنگ‌دهی نودها بر اساس نام
        node_colors = []
        for node in self.graph.nodes():
            node_str = str(node).lower()
            if "edge_cloud" in node_str:
                node_colors.append("skyblue")      # Edge clouds
            elif "task" in node_str:
                node_colors.append("lightgreen")   # Tasks
            elif "centralcloud" in node_str:
                node_colors.append("lightcoral")   # Central cloud
            else:
                node_colors.append("lightgray")
    
        # رسم گراف
        plt.figure(figsize=(12, 8))
        nx.draw(
            self.graph,
            pos,
            with_labels=True,
            labels=labels,
            node_size=3000,
            node_color=node_colors,
            font_size=9,
            font_weight='bold'
        )
        nx.draw_networkx_edge_labels(self.graph, pos, edge_labels=edge_labels, font_color='red')
        plt.show()
    

    def draw_graph_with_microservices_as_dots(self):
        G = nx.DiGraph()

        # Add nodes for tasks
        for task in self.tasks:
            G.add_node(task.task_id, label=f"Task {task.task_id}", type="task", microservices=len(task.task_microservices))

        # Get positions for nodes
        pos = nx.spring_layout(G)

        # Draw nodes with custom styles
        for node, attrs in G.nodes(data=True):
            if attrs.get("type") == "task":
                # Draw task nodes as larger circles
                nx.draw_networkx_nodes(G, pos, nodelist=[node], node_size=800, node_color="skyblue")
                # Add dots to represent microservices
                num_microservices = attrs.get("microservices", 0)
                if num_microservices > 0:
                    for i in range(num_microservices):
                        offset = (i - (num_microservices - 1) / 2) * 0.02  # Adjust spacing between dots
                        dot_pos = (pos[node][0] + offset, pos[node][1] - 0.05)  # Adjust position of dots
                        plt.scatter(dot_pos[0], dot_pos[1], color="black", s=20)

        # Draw labels for tasks
        labels = nx.get_node_attributes(G, 'label')
        nx.draw_networkx_labels(G, pos, labels, font_size=10)

        # Show plot
        plt.axis("off")
        plt.show()

    

    
    def resource_utilization_dual_plot(self, metric="bytes"):
        """
        Plots two curves with dual y-axes:
        - Left Y-axis (blue): total requested bytes (arrival → deadline)
        - Right Y-axis (orange): total allocated bytes (start → finish)
        """

        if not self.microservices:
            print("No microservices found.")
            return

        # --- 1. Determine overall time range ---
        t_min = min(ms.arrival_time for ms in self.microservices)
        t_max = max(ms.deadline_of_microservice(self) for ms in self.microservices)
        time_points = np.arange(t_min, t_max + 1)

        # --- 2. Compute requested bytes (arrival → deadline) ---
        requested_metric = []
        for t in time_points:
            active = [
                getattr(ms, metric)
                for ms in self.microservices
                if ms.arrival_time <= t < ms.deadline_of_microservice(self)
            ]
            requested_metric.append(sum(active))

        # --- 3. Compute allocated bytes (start → finish) ---
        allocated_metric = []
        for t in time_points:
            active = [
                getattr(ms, metric)
                for ms in self.microservices
                if hasattr(ms, "start_time") and hasattr(ms, "end_time") and ms.status == "completed" and  ms.start_time<= t < ms.end_time
            ]
            allocated_metric.append(sum(active))

        # --- 4. Create figure with dual y-axes ---
        fig, ax1 = plt.subplots(figsize=(10, 5))

        color1 = 'tab:blue'
        ax1.set_xlabel("Time")
        ax1.set_ylabel(f"Requested {metric.capitalize()}", color=color1)
        ax1.plot(time_points, requested_metric, color=color1, linewidth=2, label=f"Requested {metric.capitalize()}")
        ax1.tick_params(axis='y', labelcolor=color1)

        # Second Y-axis for allocated bytes
        ax2 = ax1.twinx()
        color2 = 'tab:orange'
        ax2.set_ylabel(f"Allocated {metric.capitalize()}", color=color2)
        ax2.plot(time_points, allocated_metric, color=color2, linewidth=2, label=f"Allocated {metric.capitalize()}")
        ax2.tick_params(axis='y', labelcolor=color2)

        # --- 5. Highlight peaks ---
        if requested_metric:
            peak_req_t = time_points[np.argmax(requested_metric)]
            ax1.axvline(peak_req_t, color=color1, linestyle='--', alpha=0.4, label=f'Request Peak t={peak_req_t}')

        if allocated_metric:
            peak_alloc_t = time_points[np.argmax(allocated_metric)]
            ax2.axvline(peak_alloc_t, color=color2, linestyle='--', alpha=0.4, label=f'Allocation Peak t={peak_alloc_t}')

        # --- 6. Title and legend ---
        plt.title(f"Requested vs Allocated {metric.capitalize()} Over Time")
        ax1.grid(True)
        lines1, labels1 = ax1.get_legend_handles_labels()
        lines2, labels2 = ax2.get_legend_handles_labels()
        ax1.legend(lines1 + lines2, labels1 + labels2, loc='upper right')

        plt.tight_layout()
        plt.show()

    def rejection_rate_plot(self, metric="bytes"):
        """
        Plots two curves with dual y-axes:
        - Left Y-axis (blue): total requested bytes (arrival → deadline)
        - Right Y-axis (orange): failure rate (fraction of missed deadlines)
        """

        if not self.microservices:
            print("No microservices found.")
            return

        import numpy as np
        import matplotlib.pyplot as plt

        # --- 1. Determine overall time range ---
        t_min = min(ms.arrival_time for ms in self.microservices)
        t_max = max(ms.deadline_of_microservice(self) for ms in self.microservices)
        time_points = np.arange(t_min, t_max + 1)

        # --- 2. Compute requested bytes (arrival → deadline) ---
        requested_metric = []
        for t in time_points:
            active = [
                getattr(ms, metric)
                for ms in self.microservices
                if ms.arrival_time <= t < ms.deadline_of_microservice(self)
            ]
            requested_metric.append(sum(active))

        # --- 3. Compute failure rate at each time ---
        failure_rate = []
        for t in time_points:
            arrived = [ms for ms in self.microservices if ms.arrival_time <= t]
            if not arrived:
                failure_rate.append(0)
                continue

            failed = [
                ms for ms in arrived
                if ms.deadline_of_microservice(self) <= t and getattr(ms, "status", None) != "completed"
            ]
            rate = len(failed) / len(arrived)
            failure_rate.append(rate)

        # --- 4. Create figure with dual y-axes ---
        fig, ax1 = plt.subplots(figsize=(10, 5))

        color1 = 'tab:blue'
        ax1.set_xlabel("Time")
        ax1.set_ylabel(f"Requested {metric.capitalize()}", color=color1)
        ax1.plot(time_points, requested_metric, color=color1, linewidth=2, label=f"Requested {metric.capitalize()}")
        ax1.tick_params(axis='y', labelcolor=color1)

        # Second Y-axis for failure rate
        ax2 = ax1.twinx()
        color2 = 'tab:red'
        ax2.set_ylabel("Failure Rate", color=color2)
        ax2.plot(time_points, failure_rate, color=color2, linewidth=2, label="Failure Rate")
        ax2.tick_params(axis='y', labelcolor=color2)
        ax2.set_ylim(0, 1)  # Rate between 0 and 1 (or change to 0–100 if percent preferred)

        # --- 5. Highlight peaks ---
        if requested_metric:
            peak_req_t = time_points[np.argmax(requested_metric)]
            ax1.axvline(peak_req_t, color=color1, linestyle='--', alpha=0.4, label=f'Request Peak t={peak_req_t}')

        if failure_rate:
            peak_fail_t = time_points[np.argmax(failure_rate)]
            ax2.axvline(peak_fail_t, color=color2, linestyle='--', alpha=0.4, label=f'Failure Peak t={peak_fail_t}')

        # --- 6. Title and legend ---
        plt.title(f"Requested {metric.capitalize()} vs Failure Rate Over Time")
        ax1.grid(True)
        lines1, labels1 = ax1.get_legend_handles_labels()
        lines2, labels2 = ax2.get_legend_handles_labels()
        ax1.legend(lines1 + lines2, labels1 + labels2, loc='upper right')

        plt.tight_layout()
        plt.show()


    def request_vs_failure_rate_plot(self, metric="bytes", window=10):
        """
        Plots two curves:
        - Blue (left y-axis): total requested metric (arrival → deadline)
        - Red (right y-axis): failure rate (%) in sliding time windows
        """

        if not self.microservices:
            print("No microservices found.")
            return

        # --- 1. Determine overall time range ---
        t_min = min(ms.arrival_time for ms in self.microservices)
        t_max = max(ms.deadline_of_microservice(self) for ms in self.microservices)
        time_points = np.arange(t_min, t_max + 1)

        # --- 2. Compute requested bytes (arrival → deadline) ---
        requested_metric = []
        for t in time_points:
            active = [
                getattr(ms, metric)
                for ms in self.microservices
                if ms.arrival_time <= t < ms.deadline_of_microservice(self)
            ]
            requested_metric.append(sum(active))

        # --- 3. Compute failure rate in windows ---
        window_edges = np.arange(t_min, t_max + window, window)
        failure_rates = []
        window_centers = []

        for i in range(len(window_edges) - 1):
            start = window_edges[i]
            end = window_edges[i + 1]

            # Microservices that finished in this window
            finished = [
                ms for ms in self.microservices
                if start <= ms.deadline_of_microservice(self) < end
            ]

            if not finished:
                failure_rate = 0
            else:
                failed = [
                    ms for ms in finished
                    if ms.status != "completed"
                ]
                failure_rate = 100 * len(failed) / len(finished)

            failure_rates.append(failure_rate)
            window_centers.append((start + end) / 2)

        # --- 4. Create figure with dual y-axes ---
        fig, ax1 = plt.subplots(figsize=(10, 5))

        color1 = 'tab:blue'
        ax1.set_xlabel("Time")
        ax1.set_ylabel(f"Requested {metric.capitalize()}", color=color1)
        ax1.plot(time_points, requested_metric, color=color1, linewidth=2, label=f"Requested {metric.capitalize()}")
        ax1.tick_params(axis='y', labelcolor=color1)

        # Second Y-axis for failure rate
        ax2 = ax1.twinx()
        color2 = 'tab:red'
        ax2.set_ylabel("Failure Rate (%)", color=color2)
        ax2.plot(window_centers, failure_rates, color=color2, linewidth=2, marker='o', label="Failure Rate")
        ax2.tick_params(axis='y', labelcolor=color2)
        ax2.set_ylim(0, 100)

        # --- 5. Title and legend ---
        plt.title(f"Requested {metric.capitalize()} vs Failure Rate (Window={window}s)")
        ax1.grid(True)
        lines1, labels1 = ax1.get_legend_handles_labels()
        lines2, labels2 = ax2.get_legend_handles_labels()
        ax1.legend(lines1 + lines2, labels1 + labels2, loc='upper right')

        plt.tight_layout()
        plt.show()
