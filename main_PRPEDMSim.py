# -*- coding: utf-8 -*-
"""
Created on Sat Jun 28 12:23:14 2025

@author: Sudabeh
"""
import time
import os
import sys
import tkinter as tk
from tkinter import filedialog, messagebox

# Add the root path to the sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if project_root not in sys.path:
    sys.path.append(project_root)

from PRPEDMSim.edgecloud import EdgeCloud
from PRPEDMSim.centralcloud import CentralCloud
from PRPEDMSim.topology import Topology
from PRPEDMSim.orchestrator import Orchestrator
from PRPEDMSim.environment import *
from PRPEDMSim.qlearning import *


def select_dataset_folder():
    """Open folder selection dialog and return the selected folder path"""
    root = tk.Tk()
    root.withdraw()  # Hide the main window
    root.attributes('-topmost', True)  # Show dialog on top of all windows
    folder_selected = filedialog.askdirectory(title="Select Dataset Folder")
    root.destroy()
    return folder_selected


def main(folder_path):
    """
    Main function that receives the dataset folder path and executes the program
    """
    # Check for required files in the selected folder
    task_data_file = os.path.join(folder_path, 'tasks100.csv')
    microservice_data_file = os.path.join(folder_path, 'microservices100.csv')
    message_data_file = os.path.join(folder_path, 'messages100.csv')
    
    missing_files = []
    if not os.path.exists(task_data_file):
        missing_files.append('TasksWithMicroservices100-2.csv')
    if not os.path.exists(microservice_data_file):
        missing_files.append('microservices100.csv')
    if not os.path.exists(message_data_file):
        missing_files.append('messages100-1.csv')
    
    if missing_files:
        print(f"Error: Missing files in selected folder:\n{', '.join(missing_files)}")
        return False
    
    # =============== Define Topology ===============
    # Initialize the topology
    topology = Topology()

    # Create edge cloud resources
    edge_clouds = [
        EdgeCloud(edge_id=0, storage=64, IPT=110),  # IPT= MIPS (Mega Instruction Per Second) = 10^6 IPS , 0.11 GIPS = 110 MIPS
        EdgeCloud(edge_id=1, storage=64, IPT=2900), # Storage = 32 GB
        
        EdgeCloud(edge_id=2, storage=32, IPT=2900),
        EdgeCloud(edge_id=3, storage=64, IPT=3700),
    ]
    topology.edgeclouds = edge_clouds

    # Create central cloud resources
    central_clouds = [CentralCloud(cloud_id=4, storage=1000000, IPT=50000)]
    topology.centralclouds = central_clouds

    # Setup network infrastructure
    topology.create_backhaul_network()
    topology.add_centralclouds()
    
    # =============== Load Data from Selected Folder ===============
    # Read input data from CSV files
    topology.read_tasks_from_csv(task_data_file)
    topology.read_microservices_from_csv(microservice_data_file)
    topology.read_messages_from_csv(message_data_file)
   
    # Assign tasks to edge clouds randomly
    topology.add_task_to_edgecloud_random()
    
    # Validate that tasks were loaded successfully
    if not topology.tasks:
        raise ValueError("Task list should not be empty.")

    # =============== Initialize Components ===============
    # Create microservice environment
    env = Environment(topology)
    print(
        "Predictor Mode:",
        env.predictor.mode
    )
   
    
    # Create orchestrator
    #orchestrator = Orchestrator(topology)  #orchestrator object is created in environment
    
    # Initialize Q-learning agent with action space equal to number of clouds
    agent = QLearningAgent(action_size=len(topology.edgeclouds) + len(topology.centralclouds))

    # =============== Training Phase ===============
    # Get number of episodes from user
    number_of_episodes = int(input("please enter the number of episodes:"))
    
    # Create trainer and start training
    trainer = QLearningTrainer(agent, env, episodes=number_of_episodes)
    trainer.train()
    trainer.evaluate(episodes=1)
    
    # =============== Save Results ===============
    # Create results directory inside the selected folder
    results_dir = os.path.join(folder_path, 'results')
    os.makedirs(results_dir, exist_ok=True)
    
    # Save training plots and final microservice data
    trainer.save_results(save_dir=os.path.join(results_dir))
    trainer.plot_results_separate(save_dir=os.path.join(results_dir))
    final_microservices_data = os.path.join(results_dir, 'prpedm_microservices_final_data100.csv')
    topology.save_microservices_to_csv(topology.microservices, filename=final_microservices_data)

    final_tasks_data = os.path.join(results_dir, 'prpedm_tasks_final_data100.csv')
    topology.save_tasks_to_csv(topology.tasks, filename=final_tasks_data)


    #--------------------------------------------------
    #Debuging (task status, category, deadline, end time)
    #----------------------------------------------------


    # for task in topology.tasks:
        # print(
        #     task.category,
        #     task.deadline,
        #     task.end_time,
        #     task.status
        # )

    # cat_stats = {
    #     1: {"completed":0, "rejected":0},
    #     2: {"completed":0, "rejected":0},
    #     3: {"completed":0, "rejected":0}
    # }

    # for task in topology.tasks:

    #     cat = task.category

    #     if task.status == "completed":
    #         cat_stats[cat]["completed"] += 1
    #     else:
    #         cat_stats[cat]["rejected"] += 1

    # print(cat_stats)

    #--------------------------------------------------
    # Debugging (task stats)
    #--------------------------------------------------

    
    #--------------------------------------------------
    # Debugging (Reason for Rejection)
    #--------------------------------------------------
    # reasons = {}

    # for ms in topology.microservices:

    #     if ms.status == 'rejected':

    #         reason = ms.rejection_reason

    #         reasons[reason] = reasons.get(reason, 0) + 1

    # print(reasons)


    return True


if __name__ == "__main__":
    start_time = time.time()
    
    # Step 1: Let user select the dataset folder
    selected_folder = select_dataset_folder()
    
    if not selected_folder:
        print("No folder selected. Exiting...")
        exit()
    
    print(f"Selected folder: {selected_folder}")
    
    # Step 2: Run main program with the selected folder
    success = main(selected_folder)
    
    if success:
        print("\nProgram completed successfully!")
    else:
        print("\nProgram failed due to missing files.")
    
    print(f"\nTotal execution time: {time.time() - start_time:.2f} seconds")