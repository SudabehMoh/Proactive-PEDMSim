# -*- coding: utf-8 -*-
"""
Created on Sat Jun 28 11:58:58 2025

@author: Sudabeh
"""

class Microservice:
    def __init__(self, task_id, microservice_id, instructions, bytes, dependencies, arrival_time, storage_req ):
        self.microservice_id = microservice_id
        self.task_id = task_id
        self.instructions = instructions
        self.bytes = bytes
        self.dependencies = dependencies if dependencies else []  # List of dependent microservice objects
        self.storage_req = storage_req
        self.status = 'pending'  # 'pending', 'running', 'completed', 'rejected', 'preempted'
        self.rejection_reason = None
        self.arrival_time = arrival_time
        self.start_time = None
        self.end_time = None
        self.latency= 0
        self.wait_time = 0
        self.service_time = 0
        self.response_time = 0
        self.spin_up_delay = 0
        self.assigned_resource = None

        # Preemption variables
        self.preemption_count = 0
        self.was_preempted = False

    def __str__(self):
         return f"microservice({self.microservice_id}) with dependencies ({[dp.microservice_id for dp in self.dependencies]})"


    def get_task_of_microservice(self, topology):
        for task in topology.tasks:
            if task.task_id == self.task_id:
                return task

    def deadline_of_microservice(self, topology):
        deadline = self.get_task_of_microservice(topology).deadline
        return deadline

    def is_ready1(self, completed_microservices):
        """ check if all of the dependencies are in the completed_microservice"""
        return all(dep.microservice_id in completed_microservices for dep in self.dependencies)

    def is_ready(self):
        return all(dep.microservice_id in self.get_task_of_microservice().completed_microservices for dep in self.dependencies)

    def print_microservice(self):
        """Show the microservice information and its dependencies"""
        print(f"\n🔹 Microservice ID: {self.microservice_id}")
        print(f"🔹 Task ID: {self.task_id}")
        print(f"🔹 Data Size: {self.data_size} bytes")
        print(f"🔹 Instructions: {self.instructions}")
        print(f"🔹 Number of Dependencies: {len(self.dependencies)}")

        if self.dependencies:
            print(f"🔹 Dependencies (Microservice IDs): {[dep.microservice_id for dep in self.dependencies]}")
        else:
            print("🔹 No Dependencies")

        print(f"🔹 Status: {self.status.upper()}")
        print(f"🔹 Start Time: {self.start_time if self.start_time is not None else 'Not Started'}")
        print(f"🔹 End Time: {self.end_time if self.end_time is not None else 'Not Completed'}")
        print("-" * 50)

class Message:
    def __init__(self,message_id, sender:Microservice, receiver:Microservice, data):
      self.message_id = message_id
      self.sender = sender
      self.receiver = receiver
      self.data = data

    def print_message(self):
        print(f"Message ID: {self.message_id}")
        print(f"Sender: {self.sender.microservice_id}")
        print(f"Receiver: {self.receiver}")
        print(f"Data: {self.data}")

    def __str__(self):
        return f"Message from {self.sender.microservice_id} to {self.receiver.microservice_id} with {self.data} data"


