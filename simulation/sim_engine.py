import simpy

def train_journey(env, train_id, travel_time):
    print(f"{train_id} departed at {env.now}")
    yield env.timeout(travel_time)
    print(f"{train_id} arrived at {env.now}")

def run_simulation():
    env = simpy.Environment()
    env.process(train_journey(env, "TN001", 5))
    env.process(train_journey(env, "TN002", 3))
    env.run()

if __name__ == "__main__":
    run_simulation()