# -*- coding: utf-8 -*-
"""
Created on Sat Jun 28 12:14:12 2025

@author: Sudabeh
"""
import numpy as np
import pandas as pd
from PRPEDMSim.orchestrator import Orchestrator
from collections import defaultdict
from statistics import mean
import matplotlib.pyplot as plt
import os




class QLearningAgent:
    def __init__(self,  action_size, learning_rate=0.01, discount_factor=0.99,
                 exploration_rate=1.0, exploration_decay=0.995, exploration_min=0.01):
        """
        Q-Learning agent for microservice resource allocation

        Args:
            state_size: Size of the state space
            action_size: Number of possible actions (resources)
            learning_rate: How quickly the agent learns (alpha)
            discount_factor: Importance of future rewards (gamma)
            exploration_rate: Initial probability of random exploration
            exploration_decay: Rate at which exploration decreases
            exploration_min: Minimum exploration probability
        """
        #self.state_size = state_size
        self.action_size = action_size
        self.alpha = learning_rate
        self.gamma = discount_factor
        self.epsilon = exploration_rate
        self.exploration_decay = exploration_decay
        self.exploration_min = exploration_min

        # Initialize Q-table with zeros
        #self.q_table = np.zeros((state_size, action_size))
        self.q_table = defaultdict(lambda: np.zeros(self.action_size))

        # For reproducible results
        self.rng = np.random.RandomState(42)


    def choose_action(self, state):
        #Select the action according to the policy (epsilon-greedy)
        if np.random.rand() <= self.epsilon:
            action = np.random.choice(self.action_size)
            #print(f'state: {state} and action: {action} : random action')
        else:
            action = np.argmax(self.q_table[state])
            #print(f'state: {state} and action: {action}: greedy action')
        
        return action

    def choose_valid_action(self, state, valid_actions):

        if not valid_actions:
            return None

        # Exploration
        if np.random.rand() <= self.epsilon:
            return np.random.choice(valid_actions)

        # Exploitation
        q_values = self.q_table[state]

        best_action = max(
            valid_actions,
            key=lambda a: q_values[a]
        )

        return best_action
    def choose_action_with_valid_actions(self, state, valid_actions=None):
        """
        Select action using epsilon-greedy policy with valid action masking

        Args:
            state: Current state (discrete representation)
            valid_actions: List of allowed action IDs (None for all actions)

        Returns:
            action: Selected action ID
        """
        if valid_actions is None:
            valid_actions = range(self.action_size)

        if self.rng.rand() <= self.epsilon:
            # Exploration: random valid action
            return self.rng.choice(valid_actions)
        else:
            # Exploitation: best valid action
            return self._best_valid_action(state, valid_actions)

    def _best_valid_action(self, state, valid_actions):
        """Returns action with highest Q-value among valid actions"""
        state_index = self._state_to_index(state)
        valid_q_values = [self.q_table[state_index, a] for a in valid_actions]
        best_index = np.argmax(valid_q_values)
        return valid_actions[best_index]

    def update_Qtable(self, state, action, reward, next_state, done):
        """
        Q-learning update rule
        """

        current_q = self.q_table[state][action]

        if done or next_state is None:
            max_next_q = 0
        else:
            max_next_q = np.max(self.q_table[next_state])

        target_q = reward + self.gamma * max_next_q

        self.q_table[state][action] += self.alpha * (target_q - current_q)

        # Decay exploration rate
        if done:
            self.epsilon = max(
                self.exploration_min,
                self.epsilon * self.exploration_decay
            )

    def update_Qtable1(self, state, action, reward, next_state, done):
        """
        Update Q-values using the Q-learning update rule

        Args:
            state: Current state
            action: Action taken
            reward: Reward received
            next_state: Resulting state
            done: Whether episode is complete
        """

        # Convert state and next_state tuples to hashable types for indexing
        # Ensure the current state is valid for indexing
        if state is None:
             print("Warning: update_Qtable called with None state. Skipping update.")
             return

        state_index = self._state_to_index(state)
        # If episode is done, the next state has no future rewards
        if done:
            max_next_q = 0
            # No next_state_index is needed for the update rule when done is True
            next_state_index = None # Indicate no valid next state index
        else:
            # Ensure the next state is valid for indexing if not done
            if next_state is None:
                print("Warning: update_Qtable called with done=False but next_state=None. Setting max_next_q = 0.")
                # This scenario might indicate an issue in the environment's step method
                max_next_q = 0
                next_state_index = None # Indicate no valid next state index
            else:
                next_state_index = self._state_to_index(next_state)
                
                # Q-value of best next action
                # Handle case where next_state_index might be out of bounds due to mapping issues
                if next_state_index is not None and 0 <= next_state_index < self.state_size:                    
                     max_next_q = np.max(self.q_table[next_state_index])
                     
                else:
                     # If next_state_index is invalid, treat future reward as 0
                     print(f"Warning: Invalid next_state_index {next_state_index}. Setting max_next_q = 0.")
                     max_next_q = 0


        # Current Q-value estimate
        current_q = self.q_table[state_index, action]

        # Calculate target Q-value
        target_q = reward + self.gamma * max_next_q

        # Update Q-value
        self.q_table[state_index, action] += self.alpha * (target_q - current_q)

        # Decay exploration rate if episode complete
        if done:
            self.epsilon = max(self.exploration_min,
                             self.epsilon * self.exploration_decay)

        # Test q_table changes
        #new_q = self.q_table[state_index, action]
        #if old_q != new_q:
            #print(f"Q[{state_index},{action}] {old_q:.3f} → {new_q:.3f} (R:{reward})")



class QLearningTrainer:
    def __init__(self, agent: QLearningAgent, env, episodes):
        """
        Trainer for the Q-learning agent

        Args:
            agent: Q-learning agent instance
            env: Microservice environment
            episodes: Number of training episodes
        """
        self.agent = agent
        self.env = env
        self.episodes = episodes

        self.orchestrator = env.orchestrator

        # Metrics
        self.episode_rewards = []
        self.avg_microservices_latency = []
        self.exploration_rates = []
        self.avg_microservices_response_time = []       
        self.task_acceptance_rates = []
        self.task_rejection_rates = []
        self.microservice_acceptance_rate = []
        self.microservice_rejection_rate = []
        

    def train(self):
        """Train the agent over multiple episodes"""
        
        number_of_microservices = len(self.orchestrator.microservices)
        number_of_tasks = len(self.orchestrator.tasks)
        
        for episode in range(self.episodes):
            state = self.env.reset() # Reset environment
            self.env.current_time = 0
            done = False
            episode_reward = 0
            #accepted_tasks_count = 0
            rejected_tasks_count = 0
            


            while not done:
                

                ready_microservices = self.env.get_ready_microservices()

                if ready_microservices is None:
                    done = True
                    break

                current_ms = ready_microservices[0]

                current_task = current_ms.get_task_of_microservice(self.orchestrator.topology)

                valid_action = self.env.get_valid_actions(current_ms)
                action = self.agent.choose_valid_action(state , valid_action)

                next_state, reward, done, success = self.env.step(current_ms,action)

                self.agent.update_Qtable(state, action, reward, next_state, done)

                current_task.update_task_status(self.orchestrator.topology)
                
                # Calculate metrics for each task
                episode_reward += reward   
                state = next_state             
                               
            # end of while

            for task in self.orchestrator.topology.tasks:
                task.update_task_status(self.orchestrator.topology)
            
            # ----------------------------------------------
            # Debugging
            #-----------------------------------------------

            # cat3_stats = {
            #     "cloud resource": 0,
            #     "edge resource": 0,
            #     "dependency": 0,
            #     "inedge, deadline": 0,
            #     "incloud, deadline": 0,
            #     "other": 0
            # }

            # for ms in self.orchestrator.microservices:

            #     task = ms.get_task_of_microservice(
            #         self.orchestrator.topology
            #     )

            #     if task.category != 3:
            #         continue

            #     if ms.status == "rejected":

            #         reason = ms.rejection_reason

            #         if reason in cat3_stats:
            #             cat3_stats[reason] += 1
            #         else:
            #             cat3_stats["other"] += 1

            # print("\nCAT3 REJECTION ANALYSIS")
            # print(cat3_stats)

            # Post-episode metrics
            self.episode_rewards.append(round(episode_reward,3))


            # Average of latency f
            accepted_tasks_count = sum(
                1 for task in self.orchestrator.tasks
                if task.status == 'completed'
            )
            accepted_microservices_count = sum(
                1 for ms in self.orchestrator.microservices
                if ms.status == 'completed'
            )
            rejected_tasks_count = number_of_tasks - accepted_tasks_count

            rejected_micro_count = number_of_microservices - accepted_microservices_count

            sum_microservices_latency = sum(ms.latency for ms in self.orchestrator.microservices if ms.status == 'completed' and ms.latency!=0)

            if accepted_microservices_count > 0:
                avg_latency = sum_microservices_latency / accepted_microservices_count
            else:
                avg_latency = np.NaN

            self.avg_microservices_latency.append(avg_latency)

            # Exploration rate
            exploration_rate = self.agent.epsilon
            self.exploration_rates.append(exploration_rate)


            # Average of microservice's response time
            sum_response_time = sum(ms.response_time for ms in self.orchestrator.microservices if ms.status == 'completed' and ms.response_time !=0)
            if accepted_microservices_count > 0: 
                avg_response = sum_response_time / accepted_microservices_count  
            else:
                avg_response = np.NaN              
            self.avg_microservices_response_time.append(avg_response)


            # Acceptance rate and rejection rate of tasks and microservices           
            task_acceptance_rate = accepted_tasks_count / number_of_tasks
            task_rejection_rate = rejected_tasks_count/ number_of_tasks
            self.task_acceptance_rates.append(task_acceptance_rate)
            self.task_rejection_rates.append(task_rejection_rate)


            # Calculate acceptance rate and rejection rate of microservices in this episode            
            self.microservice_acceptance_rate.append(accepted_microservices_count/number_of_microservices)              
            self.microservice_rejection_rate.append(rejected_micro_count/number_of_microservices)

            print(
                f"Episode {episode + 1} Summary:"
                f"  Total Reward: {episode_reward:.2f},"
                f"  Acceptance Rate_Tasks: {task_acceptance_rate:.2f},"
            )

            remaining_pending = [
                ms.microservice_id
                for ms in self.env.microservices
                if ms.status == 'pending'
            ]

            remaining_running = [
                ms.microservice_id
                for ms in self.env.microservices
                if ms.status == 'running'   
            ]

            # print("Remaining pending:", remaining_pending)
            # print("Remaining running:", remaining_running)

            total_preemptions = sum(
                ms.preemption_count
                for ms in self.env.microservices
            )

            max_preemptions = max(
                ms.preemption_count
                for ms in self.env.microservices
            )

            # ------------------------------------
            # Debugging print
            #------------------------------------

            # print(f"total preemptions: {total_preemptions}, max preemptions: {max_preemptions}")

            # print(
            #     f"Victims -> "
            #     f"C1:{self.env.preempted_cat[1]} "
            #     f"C2:{self.env.preempted_cat[2]} "
            #     f"C3:{self.env.preempted_cat[3]}"
            # )

            # print(
            #     f"Benefited -> "
            #     f"C1:{self.env.benefited_cat[1]} "
            #     f"C2:{self.env.benefited_cat[2]} "
            #     f"C3:{self.env.benefited_cat[3]}"
            # )

            # print(
            #     f"Proactive Offloads: "
            #     f"{self.env.proactive_offloads}"
            # )
            # end of episode



    def save_results(self, save_dir=None):
        base_path = os.path.dirname(__file__)  # path of project
        df = pd.DataFrame({
            "episode": list(range(1, self.episodes +1)),
            "avg_latency": self.avg_microservices_latency,
            "avg_response_time": self.avg_microservices_response_time,
            "total_reward": self.episode_rewards,
            'task_reject_rate': self.task_rejection_rates,
            'task_accept_rate': self.task_acceptance_rates,
            'microservice_reject_rate': self.microservice_rejection_rate,
            'microservice_accept_rate': self.microservice_acceptance_rate
            
        })
        final_data = os.path.join(save_dir, 'prpedm_final_results100.csv')
        df.to_csv(final_data, index=False)
        
        
        

    
    
    def plot_results_separate(self, save_dir=None):
        """Plot training metrics in separate figures and optionally save them."""


        if save_dir and not os.path.exists(save_dir):
            os.makedirs(save_dir)

        def save_or_show(fig, filename):
            if save_dir:
                fig.savefig(os.path.join(save_dir, filename))
            else:
                plt.show()
              # 

        # Plot 1: Rewards
        fig1 = plt.figure()
        plt.plot(self.episode_rewards)
        plt.title('Rewards per Episode')
        plt.xlabel('Episode')
        plt.ylabel('Reward')
        plt.grid(True)
        save_or_show(fig1, 'rewards_per_episode.png')
        
        # Plot 2: Exploration Rate
        fig2 = plt.figure()
        plt.plot(self.exploration_rates)
        plt.title('Exploration Rate per Episode')
        plt.xlabel('Episode')
        plt.ylabel('Exploration Rate')
        plt.grid(True)
        save_or_show(fig2, 'exploration_rate_per_episode.png')

                
        # plot 3: average Latency
        fig3 = plt.figure()
        plt.plot(self.avg_microservices_latency)
        plt.title('Average Microservices Latency')
        plt.ylabel('Average Latency')
        plt.grid(True)
        save_or_show(fig3, 'Average_Microservices_Latency.png')
        
        # Plot 4: Average Response Time
        fig4 = plt.figure()
        plt.plot(self.avg_microservices_response_time)
        plt.title('Average Microservices Response Time per Episode')
        plt.xlabel('Episode')
        plt.ylabel('Response Time')
        plt.grid(True)
        save_or_show(fig4, 'Average_Microservices_Response_Time.png')
        
        # Plot 5: Microservice Acceptance Rate
        fig5 = plt.figure()
        plt.plot(self.microservice_acceptance_rate)
        plt.title('Microservice Acceptance Rate per Episode')
        plt.xlabel('Episode')
        plt.ylabel('Acceptance Rate')
        plt.grid(True)
        save_or_show(fig5, 'micro_acceptance_rate_per_episode.png')

        # Plot 6: Microservice Rejection Rate
        fig6 = plt.figure()
        plt.plot(self.microservice_rejection_rate)
        plt.title('Microservice Rejection Rate per Episode')
        plt.xlabel('Episode')
        plt.ylabel('Rejection Rate')
        plt.grid(True)
        save_or_show(fig6, 'micro_rejection_rate_per_episode.png')


        # Plot 7: Task rejection Rate
        fig7 = plt.figure()
        plt.plot(self.task_rejection_rates)
        plt.title('Task Rejection Rate per Episode')
        plt.xlabel('Episode')
        plt.ylabel('Task Rejection Rate')
        plt.grid(True)
        save_or_show(fig7, 'Task_Rejection_rate.png')

        # Plot 8: Task Acceptance Rate
        fig8 = plt.figure()
        plt.plot(self.task_acceptance_rates)
        plt.title('Task Acceptance Rate per Episode')
        plt.xlabel('Episode')
        plt.ylabel('Task Acceptance Rate')
        plt.grid(True)
        save_or_show(fig8, 'Task_Acceptance_Rate.png')    

    def evaluate(self, episodes=20):
        print("starting evaluation...")

        old_epsilon = self.agent.epsilon

        # Disable exploration
        self.agent.epsilon = 0

        category_stats = {
            1: {"completed": 0, "rejected": 0},
            2: {"completed": 0, "rejected": 0},
            3: {"completed": 0, "rejected": 0}
        }

        acceptance_rates = []

        for episode in range(episodes):

            state = self.env.reset()
            done = False
            step_counter = 0

            while not done:

                step_counter += 1

                ready_microservices = (
                    self.env.get_ready_microservices()
                )

                if not ready_microservices:
                    print("No ready microservices")
                    break

                current_ms = ready_microservices[0]

                # print(
                #     state,
                #     self.agent.q_table[state]
                # )
                action = self.agent.choose_action(state)

                # print(
                #     f"MS={current_ms.microservice_id}, "
                #     f"status={current_ms.status}, "
                #     f"arrival={current_ms.arrival_time}"
                # )

                next_state, reward, done, success = (
                    self.env.step(
                        current_ms,
                        action
                    )
                )

                # print(
                #     f"done={done}, "
                #     f"success={success}, "
                #     f"next_state={next_state}"
                # )

                state = next_state

            # Update task status
            for task in self.orchestrator.tasks:
                task.update_task_status(
                    self.orchestrator.topology
                )

            accepted_tasks = 0

           
            for task in self.orchestrator.tasks:

                if task.status == "completed":
                    accepted_tasks += 1
                    category_stats[task.category]["completed"] += 1

                else:
                    category_stats[task.category]["rejected"] += 1

            acceptance_rates.append(
                accepted_tasks /
                len(self.orchestrator.tasks)
            )

        self.agent.epsilon = old_epsilon

        print(
            f"Episode {episode + 1} Summary:"
            f"  Acceptance Rate_Tasks: {accepted_tasks/len(self.orchestrator.tasks):.2f},"
        )
        print("\n========== TEST RESULTS ==========")

        print(
            "Average Acceptance Rate:",
            np.mean(acceptance_rates)
        )

        for cat in [1, 2, 3]:

            total = (
                category_stats[cat]["completed"]
                +
                category_stats[cat]["rejected"]
            )

            rate = (
                category_stats[cat]["completed"]
                /
                total
            )

            print(
                f"Category {cat}: "
                f"{rate:.2%}"
            )

        return category_stats